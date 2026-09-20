"""Align Binance sight candles to Kalshi observation timestamps and freeze the gate."""

from __future__ import annotations

from .models import Candle
from ..kalshi.database import KalshiDatabase
from ..spread import DEFAULT_THRESHOLD_BPS, align_to_minute, snapshot_at


def scan_spreads(
    database: KalshiDatabase,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    truth_source: str = "brti",
    threshold_bps: float = DEFAULT_THRESHOLD_BPS,
) -> dict[str, int]:
    rows = database.connection.execute(
        "SELECT DISTINCT timestamp FROM market_observations ORDER BY timestamp"
    ).fetchall()
    written = unknown = quiet = open_count = 0
    for (timestamp,) in rows:
        minute = align_to_minute(timestamp)
        sight = database.latest_candle_close("binance", symbol, interval, minute)
        truth = database.truth_at(truth_source, symbol, minute)
        snap = snapshot_at(
            timestamp=minute,
            symbol=symbol.upper(),
            sight_source="binance",
            sight_price=sight,
            truth_source=truth_source,
            truth_price=truth,
            threshold_bps=threshold_bps,
        )
        database.save_spread(snap)
        written += 1
        if snap.gate == "unknown":
            unknown += 1
        elif snap.gate == "quiet":
            quiet += 1
        else:
            open_count += 1
    return {"snapshots": written, "open": open_count, "quiet": quiet, "unknown": unknown}
