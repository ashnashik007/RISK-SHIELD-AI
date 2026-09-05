from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..engine import pipeline

router = APIRouter(prefix="/api/simulate", tags=["simulator"])

SIM_BASELINE_AMOUNT = 5000.0  # the simulator has no real customer, so it scores
                               # against a representative baseline, same as the
                               # amount slider's own scale.


@router.post("", response_model=schemas.PipelineResult)
def simulate(body: schemas.SimulateRequest, db: Session = Depends(get_db)):
    transaction = models.Transaction(
        id=pipeline.next_transaction_id(db),
        customer_id=None,
        amount=body.amount,
        location="Simulated" if body.location == "unusual" else "Usual location",
        device="new-simulated-device" if body.device == "new" else "known-simulated-device",
        velocity=body.velocity,
        device_known=(body.device == "known"),
        location_usual=(body.location == "usual"),
        beneficiary_new=(body.beneficiary == "new"),
        time_unusual=(body.time == "unusual"),
        history_override=body.history,
        status="new",
        is_simulation=True,
        created_at=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    investigation = pipeline.run_full_pipeline(
        db, transaction, avg_amount=SIM_BASELINE_AMOUNT,
        auto_execute=False, force_investigation=True,
    )
    db.refresh(transaction)

    audit = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.transaction_id == transaction.id)
        .order_by(models.AuditLog.id.asc())
        .all()
    )
    return schemas.PipelineResult(
        transaction=schemas.TransactionOut.model_validate(transaction),
        investigation=schemas.InvestigationOut.model_validate(investigation) if investigation else None,
        audit_trail=[schemas.AuditLogOut.model_validate(a) for a in audit],
    )


@router.post("/{transaction_id}/execute")
def execute_simulation(transaction_id: str, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).get(transaction_id)
    if not transaction or not transaction.is_simulation:
        raise HTTPException(404, "Simulated transaction not found")

    investigation = (
        db.query(models.Investigation)
        .filter(models.Investigation.transaction_id == transaction_id)
        .order_by(models.Investigation.created_at.desc())
        .first()
    )
    if not investigation:
        raise HTTPException(400, "No decision to execute for this scenario")
    if investigation.status not in ("Investigating", "Pending approval"):
        raise HTTPException(400, f"Scenario already {investigation.status.lower()}")

    result = pipeline.execute_and_verify(
        db, transaction, investigation, investigation.recommended_action,
        actor="Simulation",
    )
    db.refresh(transaction)
    db.refresh(investigation)

    audit = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.transaction_id == transaction.id)
        .order_by(models.AuditLog.id.asc())
        .all()
    )
    return {
        "transaction": schemas.TransactionOut.model_validate(transaction),
        "investigation": schemas.InvestigationOut.model_validate(investigation),
        "result": result,
        "audit_trail": [schemas.AuditLogOut.model_validate(a) for a in audit],
    }
