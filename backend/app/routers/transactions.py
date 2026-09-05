from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..engine import generator

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _to_out(tx: models.Transaction) -> schemas.TransactionOut:
    data = schemas.TransactionOut.model_validate(tx)
    data.customer_name = tx.customer.name if tx.customer else None
    return data


@router.get("", response_model=List[schemas.TransactionOut])
def list_transactions(
    q: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(models.Transaction).filter(models.Transaction.is_simulation == False)  # noqa: E712
    if level and level != "all":
        query = query.filter(models.Transaction.risk_level == level)
    query = query.order_by(models.Transaction.created_at.desc()).limit(limit)
    rows = query.all()
    if q:
        ql = q.lower()
        rows = [
            t for t in rows
            if ql in t.id.lower()
            or ql in (t.customer.name.lower() if t.customer else "")
            or ql in (t.customer_id or "").lower()
            or ql in t.location.lower()
        ]
    return [_to_out(t) for t in rows]


@router.get("/{transaction_id}", response_model=schemas.TransactionOut)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    tx = db.query(models.Transaction).get(transaction_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return _to_out(tx)


@router.post("/generate", response_model=schemas.PipelineResult)
def generate_transaction(db: Session = Depends(get_db)):
    tx, investigation = generator.generate_and_process(db)
    audit = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.transaction_id == tx.id)
        .order_by(models.AuditLog.id.asc())
        .all()
    )
    return schemas.PipelineResult(
        transaction=_to_out(tx),
        investigation=schemas.InvestigationOut.model_validate(investigation) if investigation else None,
        audit_trail=[schemas.AuditLogOut.model_validate(a) for a in audit],
    )
