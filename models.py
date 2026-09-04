from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from .database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)          # e.g. CUST-1028
    name = Column(String, nullable=False)
    avg_amount = Column(Float, nullable=False)      # typical transaction size (INR)
    usual_devices = Column(JSON, default=list)      # list[str] of known device fingerprints
    usual_locations = Column(JSON, default=list)    # list[str] of known cities
    risk_history = Column(String, default="normal") # normal | mixed | poor

    transactions = relationship("Transaction", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)           # e.g. TX-10492
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    amount = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    device = Column(String, nullable=False)
    velocity = Column(Integer, default=1)
    device_known = Column(Boolean, default=True)
    location_usual = Column(Boolean, default=True)
    beneficiary_new = Column(Boolean, default=False)
    time_unusual = Column(Boolean, default=False)
    history_override = Column(String, nullable=True)  # used when there's no linked customer (simulations)

    risk_score = Column(Float, default=0)
    risk_level = Column(String, default="low")      # low | medium | high | critical
    status = Column(String, default="new")
    signals = Column(JSON, default=list)             # last computed signal breakdown
    is_simulation = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="transactions")


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True)            # e.g. INC-1042
    transaction_id = Column(String, ForeignKey("transactions.id"))
    title = Column(String, nullable=False)
    score = Column(Float, default=0)
    level = Column(String, default="low")
    status = Column(String, default="Investigating")
    evidence = Column(JSON, default=list)             # list[str]
    root_cause = Column(Text, default="")
    recommended_action = Column(String, default="monitor")
    action_label = Column(String, default="Continue monitoring")
    requires_approval = Column(Boolean, default=False)

    before_score = Column(Float, nullable=True)
    after_score = Column(Float, nullable=True)
    verification_passed = Column(Boolean, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    stage = Column(String)          # detect | investigate | decide | check | execute | verify | approve
    transaction_id = Column(String, nullable=True)
    investigation_id = Column(String, nullable=True)
    actor = Column(String, default="AI Agent")
    action = Column(String, nullable=True)
    details = Column(Text, default="")
    before_score = Column(Float, nullable=True)
    after_score = Column(Float, nullable=True)


class Policy(Base):
    __tablename__ = "policy"

    id = Column(Integer, primary_key=True, default=1)
    threshold_low_medium = Column(Float, default=30)
    threshold_medium_high = Column(Float, default=60)
    threshold_high_critical = Column(Float, default=80)

    autonomy_flag_transaction = Column(Boolean, default=True)
    autonomy_request_verification = Column(Boolean, default=True)
    autonomy_hold_transaction = Column(Boolean, default=True)
    autonomy_freeze_account = Column(Boolean, default=False)
