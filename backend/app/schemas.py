from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: str
    customer_id: Optional[str]
    customer_name: Optional[str] = None
    amount: float
    location: str
    device: str
    velocity: int
    device_known: bool
    location_usual: bool
    beneficiary_new: bool
    time_unusual: bool
    risk_score: float
    risk_level: str
    status: str
    signals: List[Any] = []
    is_simulation: bool
    created_at: datetime

    class Config:
        from_attributes = True


class InvestigationOut(BaseModel):
    id: str
    transaction_id: str
    title: str
    score: float
    level: str
    status: str
    evidence: List[str] = []
    root_cause: str
    recommended_action: str
    action_label: str
    requires_approval: bool
    before_score: Optional[float]
    after_score: Optional[float]
    verification_passed: Optional[bool]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    stage: str
    transaction_id: Optional[str]
    investigation_id: Optional[str]
    actor: str
    action: Optional[str]
    details: str
    before_score: Optional[float]
    after_score: Optional[float]

    class Config:
        from_attributes = True


class PolicyOut(BaseModel):
    threshold_low_medium: float
    threshold_medium_high: float
    threshold_high_critical: float
    autonomy_flag_transaction: bool
    autonomy_request_verification: bool
    autonomy_hold_transaction: bool
    autonomy_freeze_account: bool

    class Config:
        from_attributes = True


class PolicyUpdate(BaseModel):
    threshold_low_medium: Optional[float] = None
    threshold_medium_high: Optional[float] = None
    threshold_high_critical: Optional[float] = None
    autonomy_flag_transaction: Optional[bool] = None
    autonomy_request_verification: Optional[bool] = None
    autonomy_hold_transaction: Optional[bool] = None
    autonomy_freeze_account: Optional[bool] = None


class SimulateRequest(BaseModel):
    amount: float
    velocity: int
    history: str            # normal | mixed | poor
    device: str              # known | new
    location: str             # usual | unusual
    beneficiary: str            # known | new
    time: str                    # normal | unusual


class ApproveRequest(BaseModel):
    approver: Optional[str] = "Compliance Analyst"


class PipelineResult(BaseModel):
    transaction: TransactionOut
    investigation: Optional[InvestigationOut] = None
    audit_trail: List[AuditLogOut] = []
