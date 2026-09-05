from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=List[schemas.AuditLogOut])
def list_audit(limit: int = 150, db: Session = Depends(get_db)):
    rows = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [schemas.AuditLogOut.model_validate(r) for r in rows]
