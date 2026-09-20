from datetime import datetime, timezone
from typing import Any, Iterable

from ..kalshi.models import utc_timestamp
from .binance import INTERVAL_SECONDS


DEFAULT_THRESHOLD_BPS = 25.0


def evaluate_spread(
    underlying: float | None,
    reference: float | None,
    threshold_bps: float = DEFAULT_THRESHOLD_BPS,
) -> dict[str, Any]:
    """Compare underlying market price to a settlement/reference price.

    Quiet unless both prices exist and the gap is within the threshold.
    A missing Kalshi/CF Benchmarks index is not treated as a zero gap.
    """
    if underlying is None:
        return {
            "underlying_price": None,
            "reference_price": reference,
            "spread_abs": None,
            "spread_bps": None,
            "threshold_bps": threshold_bps,
            "quiet": True,
            "reason": "missing_underlying",
        }
    if reference is None:
        return {
            "underlying_price": underlying,
            "reference_price": None,
            "spread_abs": None,
            "spread_bps": None,
            "threshold_bps": threshold_bps,
            "quiet": True,
            "reason": "missing_reference",
        }
    spread_abs = underlying - reference
    spread_bps = (spread_abs / reference) * 10000.0 if reference else None
    gap = spread_bps is not None and abs(spread_bps) > threshold_bps
    return {
        "underlying_price": underlying,
        "reference_price": reference,
        "spread_abs": spread_abs,
        "spread_bps": spread_bps,
        "threshold_bps": threshold_bps,
        "quiet": bool(gap),
        "reason": "gap" if gap else "ok",
    }


def bucket_time(timestamp: str, interval: str) -> str:
    """Floor a UTC timestamp to the candle interval so feeds can join."""
    stamp = utc_timestamp(timestamp)
    if not stamp:
        raise ValueError("timestamp is required")
    parsed = datetime.fromisoformat(stamp)
    step = INTERVAL_SECONDS.get(interval, 60)
    epoch = int(parsed.timestamp())
    floored = epoch - (epoch % step)
    return datetime.fromtimestamp(floored, tz=timezone.utc).isoformat()


def _close_by_bucket(rows: Iterable[Any], source: str, interval: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    for row in rows:
        if str(row["source"]) != source:
            continue
        key = bucket_time(str(row["close_time"] or row["open_time"]), interval)
        prices[key] = float(row["close"])
    return prices


def build_spread_snapshots(
    candles: Iterable[Any],
    symbol: str,
    interval: str,
    underlying_source: str = "binance",
    reference_source: str = "cfbenchmarks",
    threshold_bps: float = DEFAULT_THRESHOLD_BPS,
) -> list[dict[str, Any]]:
    rows = list(candles)
    underlying = _close_by_bucket(rows, underlying_source, interval)
    reference = _close_by_bucket(rows, reference_source, interval)
    timestamps = sorted(set(underlying) | set(reference))
    snapshots = []
    for timestamp in timestamps:
        verdict = evaluate_spread(underlying.get(timestamp), reference.get(timestamp), threshold_bps)
        snapshots.append(
            {
                "timestamp": timestamp,
                "symbol": symbol.upper(),
                "interval": interval,
                "underlying_source": underlying_source,
                "reference_source": reference_source,
                **verdict,
            }
        )
    return snapshots
