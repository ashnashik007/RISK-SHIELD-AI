"""
Stage 1 — DETECT.

Turns raw transaction features into a risk score plus an explainable
breakdown of contributing signals. This is intentionally a transparent,
rule-based scorer (not a black-box model) so every downstream stage
(investigate/decide/verify) can point at *why* a number is what it is.
"""

from __future__ import annotations
from typing import List, Dict, Any


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def calculate_risk(
    amount: float,
    velocity: int,
    history: str,
    device_known: bool,
    location_usual: bool,
    beneficiary_known: bool,
    time_unusual: bool,
    avg_amount: float = 5000.0,
) -> tuple[float, List[Dict[str, Any]]]:
    """
    Returns (score 0-100, signals).

    Each signal has: name, points (contribution to the score, 0-30ish),
    weight (max possible points, used for normalizing UI bars).
    """
    avg_amount = max(avg_amount, 500.0)

    # 0-30 points, driven by how many multiples of the customer's typical
    # transaction size this one represents (deviation relative to baseline).
    amount_points = _clamp((amount - avg_amount) / (avg_amount * 0.7) * 6, 0, 30)

    velocity_points = _clamp((velocity - 3) * 1.5, 0, 20)
    device_points = 0.0 if device_known else 15.0
    location_points = 0.0 if location_usual else 12.0
    beneficiary_points = 0.0 if beneficiary_known else 11.0
    time_points = 10.0 if time_unusual else 0.0
    history_points = {"normal": 0.0, "mixed": 7.0, "poor": 15.0}.get(history, 0.0)

    signals = [
        {"name": "Amount anomaly", "points": round(amount_points, 1), "weight": 30},
        {"name": "Velocity anomaly", "points": round(velocity_points, 1), "weight": 20},
        {"name": "Device anomaly", "points": round(device_points, 1), "weight": 15},
        {"name": "Location anomaly", "points": round(location_points, 1), "weight": 12},
        {"name": "Beneficiary anomaly", "points": round(beneficiary_points, 1), "weight": 11},
        {"name": "Time anomaly", "points": round(time_points, 1), "weight": 10},
        {"name": "Customer history", "points": round(history_points, 1), "weight": 15},
    ]

    raw_score = sum(s["points"] for s in signals)
    score = round(_clamp(raw_score, 3, 99), 1)
    return score, signals
