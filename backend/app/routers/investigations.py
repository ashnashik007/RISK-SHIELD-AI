from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..engine import pipeline

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.get("", response_model=List[schemas.InvestigationOut])
def list_investigations(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Investigation)
    if status:
        query = query.filter(models.Investigation.status == status)
    rows = query.order_by(models.Investigation.created_at.desc()).all()
    return [schemas.InvestigationOut.model_validate(r) for r in rows]


@router.get("/{investigation_id}", response_model=schemas.InvestigationOut)
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.query(models.Investigation).get(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    return schemas.InvestigationOut.model_validate(inv)


@router.post("/{investigation_id}/approve")
def approve_investigation(
    investigation_id: str,
    body: schemas.ApproveRequest,
    db: Session = Depends(get_db),
):
    inv = db.query(models.Investigation).get(investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    if inv.status != "Pending approval":
        raise HTTPException(400, f"Investigation is '{inv.status}', not pending approval")

    result = pipeline.approve_and_run(db, inv, body.approver or "Compliance Analyst")
    db.refresh(inv)

    audit = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.investigation_id == inv.id)
        .order_by(models.AuditLog.id.asc())
        .all()
    )
    return {
        "investigation": schemas.InvestigationOut.model_validate(inv),
        "result": result,
        "audit_trail": [schemas.AuditLogOut.model_validate(a) for a in audit],
    }
