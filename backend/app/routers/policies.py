from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..engine.pipeline import get_policy

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("", response_model=schemas.PolicyOut)
def read_policy(db: Session = Depends(get_db)):
    return schemas.PolicyOut.model_validate(get_policy(db))


@router.put("", response_model=schemas.PolicyOut)
def update_policy(body: schemas.PolicyUpdate, db: Session = Depends(get_db)):
    policy = get_policy(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return schemas.PolicyOut.model_validate(policy)
