from datetime import datetime, timezone
from typing import Any

from .client import KalshiClient
from .database import KalshiDatabase
from .models import Market, Observation, utc_timestamp


def _number(value: Any) -> float | None:
    return float(value) if value not in (None, "") else None


class KalshiImporter:
    def __init__(self, database: KalshiDatabase, client: KalshiClient | None = None) -> None:
        self.database = database
        self.client = client or KalshiClient()

    def import_market(self, ticker: str, start_ts: int | None = None, end_ts: int | None = None) -> dict[str, int]:
        started = datetime.now(timezone.utc).isoformat()
        market_payload = self.client.market(ticker)
        market = Market.from_api(market_payload.get("market", market_payload))
        self.database.save_market(market)
        self.database.save_raw(ticker, f"markets/{ticker}", market_payload)
        candle_payload = self.client.candlesticks(ticker, start_ts, end_ts)
        self.database.save_raw(ticker, f"markets/{ticker}/candlesticks", candle_payload)
        observations = [self._observation(ticker, item) for item in candle_payload.get("candlesticks", [])]
        imported, duplicates = self.database.save_observations(observations)
        result = market_payload.get("market", market_payload)
        if result.get("result") is not None or result.get("settlement_value") is not None:
            self.database.save_result(ticker, result.get("result") or result.get("settlement_value"), market.settlement_time, result.get("settlement_source"))
        self.database.log_import(ticker, started, len(observations), imported, duplicates, 0)
        return {"records_seen": len(observations), "records_imported": imported, "duplicates_skipped": duplicates, "errors": 0}

    @staticmethod
    def _observation(ticker: str, payload: dict[str, Any]) -> Observation:
        timestamp = payload.get("end_period_ts") or payload.get("timestamp") or payload.get("ts")
        price = payload.get("price") or payload.get("yes_price")
        return Observation(ticker=ticker, timestamp=utc_timestamp(timestamp), yes_price=_number(payload.get("yes_price", price)), no_price=_number(payload.get("no_price")), yes_bid=_number(payload.get("yes_bid") or payload.get("yes_bid_low")), yes_ask=_number(payload.get("yes_ask") or payload.get("yes_ask_high")), volume=_number(payload.get("volume")), open_interest=_number(payload.get("open_interest")))
