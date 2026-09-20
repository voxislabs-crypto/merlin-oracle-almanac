from __future__ import annotations

from datetime import datetime, timezone

from ..kalshi.database import KalshiDatabase
from .client import BinanceClient
from .models import Candle


class BinanceImporter:
    def __init__(self, database: KalshiDatabase, client: BinanceClient | None = None) -> None:
        self.database = database
        self.client = client or BinanceClient()

    def import_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 1000,
    ) -> dict[str, int]:
        started = datetime.now(timezone.utc).isoformat()
        payload = self.client.klines(symbol, interval, start_ms, end_ms, limit)
        self.database.save_raw(None, f"binance/klines/{symbol}/{interval}", payload)
        candles = [Candle.from_binance(row, symbol, interval) for row in payload]
        imported, duplicates = self.database.save_candles(candles)
        self.database.log_import(
            f"binance:{symbol}:{interval}",
            started,
            len(candles),
            imported,
            duplicates,
            0,
        )
        return {
            "records_seen": len(candles),
            "records_imported": imported,
            "duplicates_skipped": duplicates,
            "errors": 0,
        }
