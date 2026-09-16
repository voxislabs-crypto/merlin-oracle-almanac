from datetime import datetime, timezone
from typing import Any

from .client import KalshiClient
from .database import KalshiDatabase
from .models import Market, Observation, utc_timestamp
from ..timetrak import calculate_signal


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
        if not market.ticker or market.ticker != ticker:
            raise ValueError(f"API returned an unexpected ticker for {ticker!r}")
        self.database.save_market(market)
        self.database.save_raw(ticker, f"markets/{ticker}", market_payload)
        candle_payload = self.client.candlesticks(ticker, start_ts, end_ts)
        self.database.save_raw(ticker, f"markets/{ticker}/candlesticks", candle_payload)
        candles = candle_payload.get("candlesticks", [])
        if not isinstance(candles, list):
            raise ValueError("Kalshi candlesticks response did not contain a list")
        observations = [self._observation(ticker, item) for item in candles]
        imported, duplicates = self.database.save_observations(observations)
        result = market_payload.get("market", market_payload)
        if result.get("result") is not None or result.get("settlement_value") is not None:
            self.database.save_result(ticker, result.get("result") or result.get("settlement_value"), market.settlement_time, result.get("settlement_source"))
        self.database.log_import(ticker, started, len(observations), imported, duplicates, 0)
        return {"records_seen": len(observations), "records_imported": imported, "duplicates_skipped": duplicates, "errors": 0}

    @staticmethod
    def _observation(ticker: str, payload: dict[str, Any]) -> Observation:
        timestamp = payload.get("end_period_ts") or payload.get("timestamp") or payload.get("ts")
        if timestamp in (None, ""):
            raise ValueError("Observation is missing a timestamp")
        price = payload.get("price") or payload.get("yes_price")
        normalized_timestamp = utc_timestamp(timestamp)
        signal = calculate_signal(normalized_timestamp)
        return Observation(ticker=ticker, timestamp=normalized_timestamp, yes_price=_number(payload.get("yes_price", price)), no_price=_number(payload.get("no_price")), yes_bid=_number(payload.get("yes_bid") or payload.get("yes_bid_low")), yes_ask=_number(payload.get("yes_ask") or payload.get("yes_ask_high")), volume=_number(payload.get("volume")), open_interest=_number(payload.get("open_interest")), sky_signal=signal.intensity, sky_aspect=f"{signal.object_a} {signal.aspect} {signal.object_b}", sky_orb=signal.orb, sky_direction=signal.direction, sky_onset=signal.onset, sky_peak=signal.peak, sky_duration_hours=signal.duration_hours, astronomy_version=signal.astronomy_version, timetrak_version=signal.calculation_version)
