from datetime import datetime, timedelta, timezone
from time import time
from typing import Any

from ..kalshi.database import KalshiDatabase
from .binance import BinanceClient, kline_to_row
from .models import Candle
from .index_import import rebuild_spreads
from .spread import DEFAULT_THRESHOLD_BPS
from ..research.features import compute_feature_rows


class CandleImporter:
    def __init__(self, database: KalshiDatabase, client: BinanceClient | None = None) -> None:
        self.database = database
        self.client = client or BinanceClient()

    def import_binance(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_ts: int | None = None,
        end_ts: int | None = None,
        reference_source: str = "cfbenchmarks",
        threshold_bps: float = DEFAULT_THRESHOLD_BPS,
    ) -> dict[str, Any]:
        started = datetime.now(timezone.utc).isoformat()
        symbol = symbol.upper()
        end = end_ts or int(time())
        start = start_ts or end - int(timedelta(hours=12).total_seconds())
        if start >= end:
            end = start + 3600
        klines = list(self.client.iter_klines(symbol, interval, start, end))
        self.database.save_raw(symbol, f"binance/klines/{interval}", {"count": len(klines), "symbol": symbol})
        candles = [Candle(**kline_to_row(symbol, interval, item)) for item in klines]
        imported, duplicates = self.database.save_candles(candles)
        spreads = rebuild_spreads(self.database, symbol, interval, reference_source, threshold_bps)
        history = [dict(row) for row in self.database.load_candles("binance", symbol, interval)]
        technical, fibonacci = compute_feature_rows(history, "binance", symbol, interval)
        technical_written = self.database.save_technical_features(technical)
        fibonacci_written = self.database.save_fibonacci_features(fibonacci)
        self.database.log_import(symbol, started, len(candles), imported, duplicates, 0)
        return {
            "source": "binance",
            "symbol": symbol,
            "interval": interval,
            "records_seen": len(candles),
            "records_imported": imported,
            "duplicates_skipped": duplicates,
            "spreads_written": spreads["spreads_written"],
            "quiet_spreads": spreads["quiet_spreads"],
            "technical_written": technical_written,
            "fibonacci_written": fibonacci_written,
            "reference_source": reference_source,
            "threshold_bps": threshold_bps,
            "gate": spreads["gate"],
        }
