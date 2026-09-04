from sqlalchemy.orm import Session

from . import models
from .engine import pipeline

CUSTOMERS = [
    dict(id="CUST-1028", name="A. Subramaniam", avg_amount=9000,
         usual_devices=["dev-a1a1a1"], usual_locations=["Chennai"], risk_history="normal"),
    dict(id="CUST-3314", name="R. Nair", avg_amount=4000,
         usual_devices=["dev-b2b2b2"], usual_locations=["Bengaluru"], risk_history="normal"),
    dict(id="CUST-5521", name="K. Iyer", avg_amount=15000,
         usual_devices=["dev-c3c3c3"], usual_locations=["Mumbai"], risk_history="mixed"),
    dict(id="CUST-1902", name="P. Sharma", avg_amount=20000,
         usual_devices=["dev-d4d4d4"], usual_locations=["Delhi"], risk_history="normal"),
    dict(id="CUST-8722", name="S. Menon", avg_amount=7000,
         usual_devices=["dev-e5e5e5"], usual_locations=["Chennai"], risk_history="normal"),
    dict(id="CUST-4108", name="V. Krishnan", avg_amount=12000,
         usual_devices=["dev-f6f6f6"], usual_locations=["Kochi"], risk_history="normal"),
]

# (customer_id, amount, device_known, location_usual, beneficiary_new, time_unusual, velocity)
# Risk scores/levels below are computed live by the same engine used for every
# other transaction - these are just illustrative starting scenarios (large
# amount + new device + new beneficiary, a velocity spike, ordinary activity).
SEED_TRANSACTIONS = [
    ("CUST-1028", 87500, False, True, True, True, 2),
    ("CUST-3314", 4250, True, True, False, False, 2),
    ("CUST-5521", 18500, True, True, False, False, 7),
    ("CUST-1902", 92000, False, True, True, False, 2),
    ("CUST-8722", 7300, True, True, False, False, 2),
    ("CUST-4108", 31200, True, True, False, False, 8),
]


def seed_if_empty(db: Session) -> None:
    if db.query(models.Policy).first() is None:
        db.add(models.Policy())
        db.commit()

    if db.query(models.Customer).first() is not None:
        return  # already seeded

    for c in CUSTOMERS:
        db.add(models.Customer(**c))
    db.commit()

    customers_by_id = {c.id: c for c in db.query(models.Customer).all()}

    for customer_id, amount, device_known, location_usual, beneficiary_new, time_unusual, velocity in SEED_TRANSACTIONS:
        customer = customers_by_id[customer_id]
        device = (
            customer.usual_devices[0] if device_known and customer.usual_devices
            else "dev-newdevice01"
        )
        location = customer.usual_locations[0] if (location_usual and customer.usual_locations) else "Unusual City"

        tx = models.Transaction(
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
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        pipeline.run_full_pipeline(db, tx, avg_amount=customer.avg_amount)
