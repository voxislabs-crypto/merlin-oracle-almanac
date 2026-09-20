import csv
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..kalshi.database import KalshiDatabase
from .binance import INTERVAL_SECONDS
from .index_import import rebuild_spreads
from .models import Candle
from .spread import DEFAULT_THRESHOLD_BPS
from ..research.features import compute_feature_rows


def is_real_zip(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(4)
        return header == b"PK\x03\x04"
    except OSError:
        return False


def infer_symbol(path: Path) -> str | None:
    name = path.name.upper()
    for symbol in ("ETHUSDT", "ETHUSD", "BTCUSDT", "BTCUSD"):
        if name.startswith(symbol):
            return symbol
    return None


def _open_csv(path: Path):
    if path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)
        inner = archive.namelist()[0]
        return archive, io.TextIOWrapper(archive.open(inner), encoding="utf-8", newline="")
    return None, path.open("r", encoding="utf-8", newline="")


def iter_trades(path: Path) -> Iterable[tuple[int, float, float, float]]:
    archive, handle = _open_csv(path)
    try:
        reader = csv.DictReader(handle)
        for row in reader:
            stamp = row.get("time") or row.get("timestamp") or row.get("T")
            price = row.get("price") or row.get("p")
            qty = row.get("qty") or row.get("q") or "0"
            quote = row.get("quote_qty") or row.get("quoteQty") or "0"
            if stamp in (None, "") or price in (None, ""):
                continue
            time_ms = int(float(stamp))
            if time_ms < 10**12:
                time_ms *= 1000
            yield time_ms, float(price), float(qty or 0), float(quote or 0)
    finally:
        handle.close()
        if archive is not None:
            archive.close()


def trades_to_candles(
    trades: Iterable[tuple[int, float, float, float]],
    symbol: str,
    interval: str,
    source: str = "binance",
) -> list[Candle]:
    step = INTERVAL_SECONDS.get(interval)
    if not step:
        raise ValueError(f"Unsupported interval {interval!r}")
    buckets: dict[int, dict[str, Any]] = {}
    for time_ms, price, qty, quote in trades:
        epoch = time_ms // 1000
        open_epoch = epoch - (epoch % step)
        bucket = buckets.get(open_epoch)
        if bucket is None:
            buckets[open_epoch] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": qty,
                "quote": quote,
                "trades": 1,
            }
        else:
            bucket["high"] = max(bucket["high"], price)
            bucket["low"] = min(bucket["low"], price)
            bucket["close"] = price
            bucket["volume"] += qty
            bucket["quote"] += quote
            bucket["trades"] += 1
    candles = []
    for open_epoch, bucket in sorted(buckets.items()):
        open_dt = datetime.fromtimestamp(open_epoch, tz=timezone.utc)
        close_dt = datetime.fromtimestamp(open_epoch + step - 1, tz=timezone.utc)
        candles.append(
            Candle(
                source=source,
                symbol=symbol.upper(),
                interval=interval,
                open_time=open_dt.isoformat(),
                close_time=close_dt.isoformat(),
                open=bucket["open"],
                high=bucket["high"],
                low=bucket["low"],
                close=bucket["close"],
                volume=bucket["volume"],
                quote_volume=bucket["quote"],
                trades=bucket["trades"],
            )
        )
    return candles


class TapeImporter:
    def __init__(self, database: KalshiDatabase) -> None:
        self.database = database

    def import_path(
        self,
        path: str | Path,
        symbol: str | None = None,
        interval: str = "1m",
        threshold_bps: float = DEFAULT_THRESHOLD_BPS,
    ) -> dict[str, Any]:
        started = datetime.now(timezone.utc).isoformat()
        target = Path(path)
        if target.is_dir():
            reports = []
            skipped = []
            for child in sorted(target.iterdir()):
                if child.suffix.lower() not in {".zip", ".csv"}:
                    continue
                if child.suffix.lower() == ".zip" and not is_real_zip(child):
                    skipped.append({"path": str(child), "reason": "empty_or_corrupt_zip"})
                    continue
                reports.append(self.import_path(child, symbol=symbol or infer_symbol(child), interval=interval, threshold_bps=threshold_bps))
            return {"source": "binance", "kind": "tape_folder", "imports": reports, "skipped": skipped}
        if not target.exists():
            raise FileNotFoundError(str(target))
        if target.suffix.lower() == ".zip" and not is_real_zip(target):
            raise ValueError(f"{target.name} is not a real zip (empty download)")
        chosen = (symbol or infer_symbol(target) or "ETHUSDT").upper()
        candles = trades_to_candles(iter_trades(target), chosen, interval)
        imported, duplicates = self.database.save_candles(candles)
        self.database.save_raw(chosen, f"binance/tape/{target.name}", {"count": len(candles), "path": str(target)})
        spreads = rebuild_spreads(self.database, chosen, interval, threshold_bps=threshold_bps)
        history = [dict(row) for row in self.database.load_candles("binance", chosen, interval)]
        technical, fibonacci = compute_feature_rows(history, "binance", chosen, interval)
        self.database.log_import(chosen, started, len(candles), imported, duplicates, 0)
        return {
            "source": "binance",
            "kind": "tape",
            "path": str(target),
            "symbol": chosen,
            "interval": interval,
            "records_seen": len(candles),
            "records_imported": imported,
            "duplicates_skipped": duplicates,
            "spreads_written": spreads["spreads_written"],
            "quiet_spreads": spreads["quiet_spreads"],
            "technical_written": self.database.save_technical_features(technical),
            "fibonacci_written": self.database.save_fibonacci_features(fibonacci),
            "gate": spreads["gate"],
        }
