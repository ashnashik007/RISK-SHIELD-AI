from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _avg_points(signals_lists, name):
    vals = [next((s["points"] for s in sig if s["name"] == name), 0) for sig in signals_lists if sig]
    return sum(vals) / len(vals) if vals else 0


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.is_simulation == False)  # noqa: E712
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
    total = len(txs)
    low = sum(1 for t in txs if t.risk_level == "low")
    medium = sum(1 for t in txs if t.risk_level == "medium")
    high = sum(1 for t in txs if t.risk_level in ("high", "critical"))

    def pct(n):
        return round(n / total * 100, 1) if total else 0.0

    investigations = db.query(models.Investigation).all()
    active = [i for i in investigations if i.status in ("Investigating", "Pending approval")]
    resolved = [i for i in investigations if i.status in ("Resolved", "Escalated")]
    autonomous_actions = db.query(models.AuditLog).filter(
        models.AuditLog.stage == "execute", models.AuditLog.actor == "AI Agent"
    ).count()
    human_approvals = db.query(models.AuditLog).filter(models.AuditLog.stage == "approve").count()
    escalations = sum(1 for i in resolved if i.status == "Escalated")
    verified_ok = sum(1 for i in resolved if i.verification_passed)

    verification_pass_rate = round(verified_ok / len(resolved) * 100, 1) if resolved else 100.0
    escalation_rate = round(escalations / len(resolved) * 100, 1) if resolved else 0.0
    autonomous_rate = (
        round(autonomous_actions / max(1, autonomous_actions + human_approvals) * 100, 1)
    )

    signals_lists = [t.signals for t in txs if t.signals]
    category_bars = {
        "Transaction": round(min(100, (_avg_points(signals_lists, "Amount anomaly") / 30
                                        + _avg_points(signals_lists, "Velocity anomaly") / 20) / 2 * 100), 1),
        "Credit": round(min(100, _avg_points(signals_lists, "Customer history") / 15 * 100), 1),
        "Customer": round(min(100, (_avg_points(signals_lists, "Beneficiary anomaly") / 11
                                     + _avg_points(signals_lists, "Device anomaly") / 15) / 2 * 100), 1),
        "Operational": round(min(100, (_avg_points(signals_lists, "Time anomaly") / 10
                                        + _avg_points(signals_lists, "Location anomaly") / 12) / 2 * 100), 1),
        "Liquidity": round(min(100, sum(1 for t in txs if t.status in ("on_hold", "account_frozen"))
                                / max(1, total) * 100 * 4), 1),
    }

    trend = [
        {"time": t.created_at.isoformat(), "score": t.risk_score}
        for t in list(reversed(txs))[-24:]
    ]

    return {
        "overall_risk": round(sum(t.risk_score for t in txs) / total, 1) if total else 0.0,
        "tx_count": total,
        "high_risk_count": high,
        "active_investigations": len(active),
        "autonomous_actions": autonomous_actions,
        "human_approvals": human_approvals,
        "distribution": {"low": pct(low), "medium": pct(medium), "high": pct(high)},
        "category_bars": category_bars,
        "operational_health": {
            "autonomous_action_rate": autonomous_rate,
            "verification_pass_rate": verification_pass_rate,
            "escalation_rate": escalation_rate,
            "resolved_cases": len(resolved),
        },
        "trend": trend,
    }
