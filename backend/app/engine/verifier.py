"""
Stage 6 — VERIFY.

Closing the loop: after an action executes, re-derive the risk signals to
see whether the specific things that made the transaction risky were
actually resolved (e.g. a step-up verification confirms the device and
beneficiary), or whether the action didn't land and the case needs to be
escalated to a human instead of quietly closed.
"""

from __future__ import annotations
import random
from typing import List, Dict, Any, Tuple

# Which signal categories a given action is capable of resolving, if it
# succeeds. Amount/velocity/history reflect the transaction & customer
# themselves and are not "fixed" by identity-style controls.
RESOLVABLE_SIGNALS = {
    "monitor": [],
    "flag_transaction": ["Device anomaly"],
    "request_verification": ["Device anomaly", "Location anomaly", "Beneficiary anomaly", "Time anomaly"],
    "hold_transaction": ["Device anomaly", "Location anomaly", "Beneficiary anomaly", "Time anomaly"],
    "freeze_account": [
        "Amount anomaly", "Velocity anomaly", "Device anomaly",
        "Location anomaly", "Beneficiary anomaly", "Time anomaly", "Customer history",
    ],
}

# Probability the action actually achieves what it set out to do (a
# verification can fail, a hold can be insufficient, etc). Failure means
# nothing gets mitigated and the case escalates.
SUCCESS_RATE = {
    "monitor": 1.0,
    "flag_transaction": 0.92,
    "request_verification": 0.85,
    "hold_transaction": 0.85,
    "freeze_account": 1.0,
}


def verify(signals: List[Dict[str, Any]], action_key: str) -> Tuple[float, bool, List[Dict[str, Any]]]:
    """Returns (new_score, verification_passed, new_signals)."""
    resolvable = set(RESOLVABLE_SIGNALS.get(action_key, []))
    passed = random.random() < SUCCESS_RATE.get(action_key, 0.8)

    if passed:
        new_signals = [
            {**s, "points": 0.0 if s["name"] in resolvable else s["points"]}
            for s in signals
        ]
    else:
        # Nothing was mitigated; the underlying risk is unchanged.
        new_signals = [dict(s) for s in signals]

    total = sum(s["points"] for s in new_signals)
    new_score = round(max(3.0, min(99.0, total)), 1)
    return new_score, passed, new_signals
