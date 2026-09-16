from time import sleep
from typing import Any, Iterator
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json


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
            except (HTTPError, URLError, TimeoutError):
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
        return self.get(f"markets/{ticker}")

    def candlesticks(self, ticker: str, start_ts: int | None = None, end_ts: int | None = None, period_interval: int = 60) -> dict[str, Any]:
        return self.get(f"markets/{ticker}/candlesticks", start_ts=start_ts, end_ts=end_ts, period_interval=period_interval)
