import csv
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

from ..kalshi.database import KalshiDatabase
from ..kalshi.models import utc_timestamp
from .binance import INTERVAL_SECONDS
from .models import Candle
from .spread import DEFAULT_THRESHOLD_BPS, build_spread_snapshots


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _coerce_time(value: Any) -> str | None:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, (int, float)) and value > 1e12:
        value = value / 1000.0
    return utc_timestamp(value)


def _timestamp(row: dict[str, Any]) -> str | None:
    for key in ("timestamp", "time", "ts", "datetime", "date", "open_time"):
        if row.get(key) not in (None, ""):
            return _coerce_time(row[key])
    return None


def _price(row: dict[str, Any]) -> float | None:
    for key in ("value", "close", "price", "index", "brti", "close_price"):
        if row.get(key) not in (None, ""):
            return _number(row[key])
    return None


def parse_index_records(payload: Any) -> list[tuple[str, float]]:
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return []
        if text[0] in "[{":
            payload = json.loads(text)
        else:
            reader = csv.DictReader(StringIO(text))
            payload = list(reader)
    if isinstance(payload, dict):
        payload = payload.get("payload") or payload.get("records") or payload.get("data") or payload.get("values") or []
    if not isinstance(payload, list):
        raise ValueError("Index payload must be a JSON list, CSV table, or an object with records")
    points = []
    for item in payload:
        if isinstance(item, dict):
            stamp = _timestamp(item)
            price = _price(item)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            stamp = _coerce_time(item[0])
            price = _number(item[1])
        else:
            continue
        if stamp and price is not None:
            points.append((stamp, price))
    points.sort()
    return points


def resample_points(points: Iterable[tuple[str, float]], interval: str, source: str, symbol: str) -> list[Candle]:
    step = INTERVAL_SECONDS.get(interval)
    if not step:
        raise ValueError(f"Unsupported interval {interval!r}")
    buckets: dict[int, list[float]] = {}
    for stamp, price in points:
        parsed = datetime.fromisoformat(stamp)
        epoch = int(parsed.timestamp())
        open_epoch = epoch - (epoch % step)
        buckets.setdefault(open_epoch, []).append(price)
    candles = []
    for open_epoch, values in sorted(buckets.items()):
        open_dt = datetime.fromtimestamp(open_epoch, tz=timezone.utc)
        close_dt = datetime.fromtimestamp(open_epoch + step - 1, tz=timezone.utc)
        candles.append(
            Candle(
                source=source,
                symbol=symbol.upper(),
                interval=interval,
                open_time=open_dt.isoformat(),
                close_time=close_dt.isoformat(),
                open=values[0],
                high=max(values),
                low=min(values),
                close=values[-1],
                volume=float(len(values)),
                quote_volume=None,
                trades=len(values),
            )
        )
    return candles


def rebuild_spreads(
    database: KalshiDatabase,
    symbol: str,
    interval: str,
    reference_source: str = "cfbenchmarks",
    threshold_bps: float = DEFAULT_THRESHOLD_BPS,
) -> dict[str, Any]:
    underlying = list(database.load_candles("binance", symbol, interval))
    reference = list(database.load_candles(reference_source, symbol, interval))
    snapshots = build_spread_snapshots(
        underlying + reference,
        symbol=symbol,
        interval=interval,
        reference_source=reference_source,
        threshold_bps=threshold_bps,
    )
    written, _ = database.save_spreads(snapshots)
    compared = [row for row in snapshots if row["reason"] in {"ok", "gap"}]
    quiet = sum(1 for row in snapshots if row["quiet"])
    return {
        "spreads_written": written,
        "compared": len(compared),
        "quiet_spreads": quiet,
        "gate": snapshots[-1] if snapshots else {"quiet": True, "reason": "missing_reference"},
    }


class IndexImporter:
    def __init__(self, database: KalshiDatabase) -> None:
        self.database = database

    def import_records(
        self,
        payload: Any,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        source: str = "cfbenchmarks",
        threshold_bps: float = DEFAULT_THRESHOLD_BPS,
    ) -> dict[str, Any]:
        started = datetime.now(timezone.utc).isoformat()
        points = parse_index_records(payload)
        candles = resample_points(points, interval, source, symbol)
        imported, duplicates = self.database.save_candles(candles)
        self.database.save_raw(symbol, f"{source}/index/{interval}", {"count": len(points), "symbol": symbol})
        spreads = rebuild_spreads(self.database, symbol, interval, source, threshold_bps)
        self.database.log_import(f"{source}:{symbol}", started, len(points), imported, duplicates, 0)
        return {
            "source": source,
            "symbol": symbol.upper(),
            "interval": interval,
            "records_seen": len(points),
            "records_imported": imported,
            "duplicates_skipped": duplicates,
            "candles": len(candles),
            **spreads,
        }

    def import_file(self, path: str | Path, **kwargs: Any) -> dict[str, Any]:
        text = Path(path).read_text(encoding="utf-8")
        return self.import_records(text, **kwargs)
