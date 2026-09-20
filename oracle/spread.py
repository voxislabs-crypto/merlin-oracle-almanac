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


@dataclass(frozen=True)
class SpreadSnapshot:
    timestamp: str
    symbol: str
    sight_source: str
    sight_price: float | None
    truth_source: str
    truth_price: float | None
    abs_gap: float | None
    gap_bps: float | None
    threshold_bps: float
    gate: str


def snapshot_at(
    timestamp: str,
    symbol: str,
    sight_source: str,
    sight_price: float | None,
    truth_source: str,
    truth_price: float | None,
    threshold_bps: float = DEFAULT_THRESHOLD_BPS,
) -> SpreadSnapshot:
    gate = decide_gate(sight_price, truth_price, threshold_bps)
    abs_gap = None
    bps = None
    if sight_price is not None and truth_price is not None:
        abs_gap = abs(sight_price - truth_price)
        bps = gap_bps(sight_price, truth_price)
    return SpreadSnapshot(
        timestamp=timestamp,
        symbol=symbol,
        sight_source=sight_source,
        sight_price=sight_price,
        truth_source=truth_source,
        truth_price=truth_price,
        abs_gap=abs_gap,
        gap_bps=bps,
        threshold_bps=threshold_bps,
        gate=gate,
    )


def align_to_minute(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return parsed.isoformat()
