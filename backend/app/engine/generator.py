"""
Creates a new, randomized-but-plausible transaction for an existing
customer, persists it, and runs it through the full pipeline. Used by
POST /api/transactions/generate and the live SSE stream.
"""

from __future__ import annotations
import random
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models
from . import pipeline

CITY_POOL = ["Chennai", "Mumbai", "Bengaluru", "Delhi", "Kochi", "Hyderabad", "Pune", "Jaipur"]


def _random_device_id() -> str:
    return "dev-" + "".join(random.choices("abcdef0123456789", k=6))


def generate_and_process(db: Session) -> tuple[models.Transaction, models.Investigation | None]:
    customers = db.query(models.Customer).all()
    if not customers:
        raise RuntimeError("No customers seeded")
    customer = random.choice(customers)

    suspicious = random.random() > 0.72

    if suspicious:
        amount = round(random.uniform(customer.avg_amount * 3, customer.avg_amount * 9) / 500) * 500
        velocity = random.randint(4, 12)
        device_known = random.random() > 0.75
        location_usual = random.random() > 0.55
        beneficiary_new = random.random() > 0.35
        time_unusual = random.random() > 0.4
    else:
        amount = round(random.uniform(customer.avg_amount * 0.4, customer.avg_amount * 1.4) / 100) * 100
        velocity = random.randint(1, 4)
        device_known = random.random() > 0.1
        location_usual = random.random() > 0.1
        beneficiary_new = random.random() > 0.85
        time_unusual = random.random() > 0.9

    device = (
        random.choice(customer.usual_devices) if (device_known and customer.usual_devices)
        else _random_device_id()
    )
    if location_usual and customer.usual_locations:
        location = random.choice(customer.usual_locations)
    else:
        others = [c for c in CITY_POOL if c not in (customer.usual_locations or [])]
        location = random.choice(others or CITY_POOL)

    transaction = models.Transaction(
        id=pipeline.next_transaction_id(db),
        customer_id=customer.id,
        amount=amount,
        location=location,
        device=device,
        velocity=velocity,
        device_known=device_known,
        location_usual=location_usual,
        beneficiary_new=beneficiary_new,
        time_unusual=time_unusual,
        status="new",
        created_at=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    investigation = pipeline.run_full_pipeline(db, transaction, avg_amount=customer.avg_amount)
    db.refresh(transaction)
    return transaction, investigation
