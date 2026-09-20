from time import sleep
from typing import Any, Iterator
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

MAX_CANDLES = 5000
CANDLE_INTERVALS = (1, 60, 1440)


def candle_period_interval(start_ts: int, end_ts: int) -> int:
    """Hourly bars when they fit under Kalshi's 5000-bar cap; otherwise daily."""
    minutes = max((end_ts - start_ts) / 60.0, 1.0)
    if minutes / 60 <= MAX_CANDLES:
        return 60
    return 1440


def _error_body(error: HTTPError) -> str:
    try:
        return error.read().decode("utf-8", "replace")
    except Exception:
        return error.reason or ""


class KalshiClient:
    """Public, read-only Kalshi API client. No account or order methods exist here."""

    def __init__(self, base_url: str = "https://api.elections.kalshi.com/trade-api/v2") -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, retries: int = 3, **params: Any) -> dict[str, Any]:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        request = Request(f"{self.base_url}/{path.lstrip('/')}" + (f"?{query}" if query else ""), headers={"Accept": "application/json"})
        for attempt in range(retries):
            try:
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError:
                raise
            except (URLError, TimeoutError):
                if attempt == retries - 1:
                    raise
                sleep(2 ** attempt)

    def markets(self, limit: int = 100, cursor: str | None = None, category: str | None = None) -> dict[str, Any]:
        return self.get("markets", limit=limit, cursor=cursor, series_ticker=category)

    def all_markets(self, category: str | None = None, page_size: int = 100) -> Iterator[dict[str, Any]]:
        cursor = None
        while True:
            payload = self.markets(limit=page_size, cursor=cursor, category=category)
            yield from payload.get("markets", [])
            cursor = payload.get("cursor")
            if not cursor:
                break

    def market(self, ticker: str) -> dict[str, Any]:
        try:
            return self.get(f"markets/{ticker}")
        except HTTPError as error:
            if error.code != 404:
                raise
            return self.get(f"historical/markets/{ticker}")

    def event(self, event_ticker: str) -> dict[str, Any]:
        return self.get(f"events/{event_ticker}")

    def candlesticks(
        self,
        ticker: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        period_interval: int | None = None,
        series_ticker: str | None = None,
    ) -> dict[str, Any]:
        if start_ts is None or end_ts is None:
            raise ValueError("Kalshi candlesticks require start_ts and end_ts")
        chosen = period_interval or candle_period_interval(start_ts, end_ts)
        intervals: list[int] = []
        for interval in (chosen, 60, 1440):
            if interval not in intervals:
                intervals.append(interval)
        paths = []
        if series_ticker:
            paths.append(f"series/{series_ticker}/markets/{ticker}/candlesticks")
        paths.append(f"historical/markets/{ticker}/candlesticks")
        last_error = "Kalshi candlesticks failed"
        for interval in intervals:
            for path in paths:
                try:
                    payload = self.get(
                        path,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        period_interval=interval,
                    )
                    if isinstance(payload, dict):
                        payload.setdefault("period_interval", interval)
                    return payload
                except HTTPError as error:
                    last_error = f"HTTP {error.code} {path} interval={interval}: {_error_body(error)}"
                    if error.code not in {400, 404}:
                        raise ValueError(f"Kalshi candlesticks failed: {last_error}") from error
        raise ValueError(f"Kalshi candlesticks failed: {last_error}")
