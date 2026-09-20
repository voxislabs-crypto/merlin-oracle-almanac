from datetime import datetime, timezone
from time import time
from typing import Any
from urllib.error import HTTPError

from .client import KalshiClient
from .database import KalshiDatabase
from .models import Market, Observation, price_cents, unix_seconds, utc_timestamp
from ..timetrak import calculate_signal


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return _number(value.get("close_dollars") or value.get("close") or value.get("mean_dollars"))
    return float(value)


class KalshiImporter:
    def __init__(self, database: KalshiDatabase, client: KalshiClient | None = None) -> None:
        self.database = database
        self.client = client or KalshiClient()

    def import_market(self, ticker: str, start_ts: int | None = None, end_ts: int | None = None) -> dict[str, int]:
        started = datetime.now(timezone.utc).isoformat()
        market_payload = self.client.market(ticker)
        raw_market = market_payload.get("market", market_payload)
        market = Market.from_api(raw_market)
        if not market.ticker or market.ticker != ticker:
            raise ValueError(f"API returned an unexpected ticker for {ticker!r}")
        self.database.save_market(market)
        self.database.save_raw(ticker, f"markets/{ticker}", market_payload)
        series_ticker = self._series_ticker(market.event)
        start = start_ts or unix_seconds(market.open_time or market.created_time)
        end = end_ts or unix_seconds(market.close_time) or int(time())
        if start is None:
            raise ValueError(f"Market {ticker!r} is missing an open time, so candlesticks cannot be requested")
        if start >= end:
            end = start + 3600
        candle_warning = None
        try:
            candle_payload = self.client.candlesticks(ticker, start, end, series_ticker=series_ticker)
        except (HTTPError, ValueError) as error:
            candle_payload = {"candlesticks": [], "error": str(error)}
            candle_warning = str(error)
        self.database.save_raw(ticker, f"markets/{ticker}/candlesticks", candle_payload)
        candles = candle_payload.get("candlesticks", [])
        if not isinstance(candles, list):
            raise ValueError("Kalshi candlesticks response did not contain a list")
        observations = [self._observation(ticker, item) for item in candles]
        imported, duplicates = self.database.save_observations(observations)
        if raw_market.get("result") not in (None, "") or raw_market.get("settlement_value") is not None:
            self.database.save_result(ticker, raw_market.get("result") or raw_market.get("settlement_value"), market.settlement_time, raw_market.get("settlement_source"))
        errors = 1 if candle_warning else 0
        self.database.log_import(ticker, started, len(observations), imported, duplicates, errors)
        result = {
            "ticker": ticker,
            "series_ticker": series_ticker,
            "period_interval": candle_payload.get("period_interval"),
            "records_seen": len(observations),
            "records_imported": imported,
            "duplicates_skipped": duplicates,
            "errors": errors,
        }
        if candle_warning:
            result["warning"] = candle_warning
        return result

    def _series_ticker(self, event_ticker: str | None) -> str | None:
        if not event_ticker:
            return None
        try:
            payload = self.client.event(event_ticker)
        except (HTTPError, AttributeError):
            return None
        event = payload.get("event", payload)
        series = event.get("series_ticker") if isinstance(event, dict) else None
        if series:
            self.database.save_raw(event_ticker, f"events/{event_ticker}", payload)
        return series

    @staticmethod
    def _observation(ticker: str, payload: dict[str, Any]) -> Observation:
        timestamp = payload.get("end_period_ts") or payload.get("timestamp") or payload.get("ts")
        if timestamp in (None, ""):
            raise ValueError("Observation is missing a timestamp")
        yes_price = price_cents(payload.get("price") or payload.get("yes_price"))
        yes_bid = price_cents(payload.get("yes_bid") or payload.get("yes_bid_low"))
        yes_ask = price_cents(payload.get("yes_ask") or payload.get("yes_ask_high"))
        no_price = price_cents(payload.get("no_price"))
        if no_price is None and yes_price is not None:
            no_price = round(100.0 - yes_price, 4)
        normalized_timestamp = utc_timestamp(timestamp)
        signal = calculate_signal(normalized_timestamp)
        return Observation(
            ticker=ticker,
            timestamp=normalized_timestamp,
            yes_price=yes_price,
            no_price=no_price,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            volume=_number(payload.get("volume_fp", payload.get("volume"))),
            open_interest=_number(payload.get("open_interest_fp", payload.get("open_interest"))),
            sky_signal=signal.intensity,
            sky_aspect=f"{signal.object_a} {signal.aspect} {signal.object_b}",
            sky_orb=signal.orb,
            sky_direction=signal.direction,
            sky_onset=signal.onset,
            sky_peak=signal.peak,
            sky_duration_hours=signal.duration_hours,
            astronomy_version=signal.astronomy_version,
            timetrak_version=signal.calculation_version,
        )
