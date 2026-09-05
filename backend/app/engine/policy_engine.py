"""
Stage 3 — DECIDE, and Stage 4 — CHECK (is it safe to act autonomously).

Decisions are driven entirely by the thresholds and toggles stored in the
Policy row, which the Policy Guard page reads and writes. Nothing here is
hardcoded: change a threshold or an autonomy toggle in the UI and the
next transaction routes differently.
"""

from __future__ import annotations
from typing import List, Dict, Any

ACTIONS: Dict[str, Dict[str, Any]] = {
    "monitor": {
        "label": "Continue monitoring",
        "always_autonomous": True,
    },
    "flag_transaction": {
        "label": "Flag transaction",
        "toggle": "autonomy_flag_transaction",
    },
    "request_verification": {
        "label": "Request step-up verification",
        "toggle": "autonomy_request_verification",
    },
    "hold_transaction": {
        "label": "Hold transaction (simulated)",
        "toggle": "autonomy_hold_transaction",
    },
    "freeze_account": {
        "label": "Freeze account",
        "toggle": "autonomy_freeze_account",
    },
}


def level_for_score(score: float, policy) -> str:
    if score >= policy.threshold_high_critical:
        return "critical"
    if score >= policy.threshold_medium_high:
        return "high"
    if score >= policy.threshold_low_medium:
        return "medium"
    return "low"


def decide_action(level: str, signals: List[Dict[str, Any]]) -> str:
    """Stage 3: pick the recommended action for this risk band."""
    if level == "low":
        return "monitor"

    if level == "medium":
        sig = {s["name"]: s["points"] for s in signals}
        if sig.get("Beneficiary anomaly", 0) > 0 or sig.get("Device anomaly", 0) > 0:
            return "request_verification"
        return "flag_transaction"

    if level == "high":
        return "hold_transaction"

    return "freeze_account"  # critical


def is_autonomous(action_key: str, policy) -> bool:
    """Stage 4: is this action within the current autonomous-action allowlist?"""
    action = ACTIONS[action_key]
    if action.get("always_autonomous"):
        return True
    toggle = action.get("toggle")
    return bool(getattr(policy, toggle))


def action_label(action_key: str) -> str:
    return ACTIONS[action_key]["label"]
