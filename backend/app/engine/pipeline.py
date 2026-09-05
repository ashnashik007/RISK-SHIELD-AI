"""
The orchestrator. This is where the six stages actually chain together
into one closed loop, and where every stage transition is written to the
audit trail so the whole decision is reconstructable after the fact.
"""

from __future__ import annotations
import random
import string
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from . import risk_engine, investigator, policy_engine, executor, verifier


# ----------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------

def _rand_suffix(n=4) -> str:
    return "".join(random.choices(string.digits, k=n))


def next_transaction_id(db: Session) -> str:
    count = db.query(models.Transaction).count()
    return f"TX-{10493 + count}-{_rand_suffix(3)}"


def next_investigation_id(db: Session) -> str:
    count = db.query(models.Investigation).count()
    return f"INC-{1043 + count}-{_rand_suffix(3)}"


def get_policy(db: Session) -> models.Policy:
    policy = db.query(models.Policy).first()
    if not policy:
        policy = models.Policy()
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


def log_audit(
    db: Session,
    stage: str,
    transaction_id: Optional[str] = None,
    investigation_id: Optional[str] = None,
    actor: str = "AI Agent",
    action: Optional[str] = None,
    details: str = "",
    before_score: Optional[float] = None,
    after_score: Optional[float] = None,
) -> models.AuditLog:
    entry = models.AuditLog(
        timestamp=datetime.utcnow(),
        stage=stage,
        transaction_id=transaction_id,
        investigation_id=investigation_id,
        actor=actor,
        action=action,
        details=details,
        before_score=before_score,
        after_score=after_score,
    )
    db.add(entry)
    db.commit()
    return entry


# ----------------------------------------------------------------------
# stages 1-4: detect -> investigate -> decide -> check
# ----------------------------------------------------------------------

def score_transaction(db: Session, transaction: models.Transaction, avg_amount: float) -> None:
    """Stage 1: DETECT."""
    history = (
        transaction.customer.risk_history if transaction.customer
        else (transaction.history_override or "normal")
    )
    score, signals = risk_engine.calculate_risk(
        amount=transaction.amount,
        velocity=transaction.velocity,
        history=history,
        device_known=transaction.device_known,
        location_usual=transaction.location_usual,
        beneficiary_known=not transaction.beneficiary_new,
        time_unusual=transaction.time_unusual,
        avg_amount=avg_amount,
    )
    policy = get_policy(db)
    transaction.risk_score = score
    transaction.risk_level = policy_engine.level_for_score(score, policy)
    transaction.signals = signals
    db.commit()
    log_audit(
        db, "detect", transaction_id=transaction.id,
        details=f"Scored {score}/100 ({transaction.risk_level}) across {len(signals)} signals",
        after_score=score,
    )


def run_full_pipeline(
    db: Session,
    transaction: models.Transaction,
    avg_amount: float,
    auto_execute: bool = True,
    force_investigation: bool = False,
) -> Optional[models.Investigation]:
    """
    Runs stages 1-4 (and 5-6 if the resulting action is autonomous).
    Returns the Investigation row if one was opened, else None.

    force_investigation=True always opens an investigation (recommending
    "Continue monitoring" for low risk) — used by the simulator so every
    scenario, including low-risk ones, produces a reviewable/executable
    result.
    """
    # Stage 1: detect
    score_transaction(db, transaction, avg_amount)

    if transaction.risk_level == "low" and not force_investigation:
        transaction.status = "cleared"
        db.commit()
        return None

    # Stage 2: investigate
    evidence, root_cause = investigator.investigate(
        amount=transaction.amount,
        avg_amount=avg_amount,
        velocity=transaction.velocity,
        signals=transaction.signals,
    )
    log_audit(
        db, "investigate", transaction_id=transaction.id,
        details=f"Gathered {len(evidence)} evidence points; root cause identified",
    )

    # Stage 3: decide
    action_key = policy_engine.decide_action(transaction.risk_level, transaction.signals)
    label = policy_engine.action_label(action_key)
    log_audit(
        db, "decide", transaction_id=transaction.id, action=action_key,
        details=f"Recommended action: {label}",
    )

    # Stage 4: check (is it safe to act autonomously under current policy?)
    policy = get_policy(db)
    autonomous = policy_engine.is_autonomous(action_key, policy)
    log_audit(
        db, "check", transaction_id=transaction.id, action=action_key,
        details=(
            f"'{label}' is on the autonomous allowlist — proceeding without human approval"
            if autonomous else
            f"'{label}' is a high-impact action outside the autonomous allowlist — human approval required"
        ),
    )

    investigation = models.Investigation(
        id=next_investigation_id(db),
        transaction_id=transaction.id,
        title=_investigation_title(transaction.signals),
        score=transaction.risk_score,
        level=transaction.risk_level,
        status="Pending approval" if not autonomous else "Investigating",
        evidence=evidence,
        root_cause=root_cause,
        recommended_action=action_key,
        action_label=label,
        requires_approval=not autonomous,
        before_score=transaction.risk_score,
    )
    db.add(investigation)
    if not autonomous:
        transaction.status = "pending_review"
    db.commit()
    db.refresh(investigation)

    if autonomous and auto_execute:
        execute_and_verify(db, transaction, investigation, action_key, actor="AI Agent")

    return investigation


def _investigation_title(signals) -> str:
    fired = sorted([s for s in signals if s["points"] > 0], key=lambda s: -s["points"])
    if not fired:
        return "Elevated risk event"
    top = fired[0]["name"]
    titles = {
        "Amount anomaly": "Unusual transaction amount",
        "Velocity anomaly": "Transaction velocity spike",
        "Device anomaly": "Unrecognized device activity",
        "Location anomaly": "Unusual transaction location",
        "Beneficiary anomaly": "New beneficiary anomaly",
        "Time anomaly": "Off-hours transaction activity",
        "Customer history": "High-risk customer profile event",
    }
    return titles.get(top, "Elevated risk event")


# ----------------------------------------------------------------------
# stages 5-6: execute -> verify
# ----------------------------------------------------------------------

def execute_and_verify(
    db: Session,
    transaction: models.Transaction,
    investigation: models.Investigation,
    action_key: str,
    actor: str = "AI Agent",
) -> dict:
    before_score = transaction.risk_score

    # Stage 5: execute
    new_status = executor.execute(transaction, action_key)
    db.commit()
    log_audit(
        db, "execute", transaction_id=transaction.id, investigation_id=investigation.id,
        actor=actor, action=action_key,
        details=f"Executed '{policy_engine.action_label(action_key)}' -> status={new_status}",
        before_score=before_score,
    )

    # Stage 6: verify
    new_score, passed, new_signals = verifier.verify(transaction.signals, action_key)
    transaction.risk_score = new_score
    transaction.signals = new_signals
    policy = get_policy(db)
    transaction.risk_level = policy_engine.level_for_score(new_score, policy)

    investigation.after_score = new_score
    investigation.verification_passed = passed
    investigation.resolved_at = datetime.utcnow()

    if passed:
        investigation.status = "Resolved"
        transaction.status = f"{transaction.status}_verified"
    else:
        investigation.status = "Escalated"
        transaction.status = "escalated"

    db.commit()

    log_audit(
        db, "verify", transaction_id=transaction.id, investigation_id=investigation.id,
        actor=actor,
        details=(
            f"Verification passed — risk reduced {before_score} -> {new_score}"
            if passed else
            f"Verification failed — risk unchanged at {new_score}, escalated to human review"
        ),
        before_score=before_score, after_score=new_score,
    )

    return {
        "before_score": before_score,
        "after_score": new_score,
        "passed": passed,
        "status": investigation.status,
    }


def approve_and_run(db: Session, investigation: models.Investigation, approver: str) -> dict:
    transaction = db.query(models.Transaction).get(investigation.transaction_id)
    log_audit(
        db, "approve", transaction_id=transaction.id, investigation_id=investigation.id,
        actor=f"Human ({approver})", action=investigation.recommended_action,
        details=f"Action '{investigation.action_label}' approved by {approver}",
    )
    investigation.requires_approval = False
    investigation.status = "Investigating"
    db.commit()
    return execute_and_verify(
        db, transaction, investigation, investigation.recommended_action,
        actor=f"Human ({approver})",
    )
