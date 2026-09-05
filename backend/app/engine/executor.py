"""
Stage 5 — EXECUTE.

Applies the decided action to the transaction. Every action here is a
*simulated* control action (this prototype never touches a real bank or
payment network) but it is genuinely applied to persisted state, not just
displayed, so the rest of the system (status, audit trail, analytics)
reacts to it consistently.
"""

from __future__ import annotations

STATUS_FOR_ACTION = {
    "monitor": "monitoring",
    "flag_transaction": "flagged",
    "request_verification": "verification_requested",
    "hold_transaction": "on_hold",
    "freeze_account": "account_frozen",
}


def execute(transaction, action_key: str) -> str:
    new_status = STATUS_FOR_ACTION.get(action_key, transaction.status)
    transaction.status = new_status
    return new_status
