"""Spread gate between a sight feed (Binance) and a truth feed (Kalshi settlement index).

Kalshi crypto contracts settle on CF Benchmarks RTIs (BRTI for BTC), not Binance spot.
Until a truth tick is stored, the gate is UNKNOWN and live signals stay quiet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


DEFAULT_THRESHOLD_BPS = 25.0


def gap_bps(sight: float, truth: float) -> float:
    if truth == 0:
        raise ValueError("truth price cannot be zero")
    return abs(sight - truth) / truth * 10_000.0


def decide_gate(sight: float | None, truth: float | None, threshold_bps: float = DEFAULT_THRESHOLD_BPS) -> str:
    if sight is None or truth is None:
        return "unknown"
    return "quiet" if gap_bps(sight, truth) > threshold_bps else "open"
