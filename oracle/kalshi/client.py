from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


class KalshiClient:
    """Public, read-only Kalshi API client. No account or order methods exist here."""

    def __init__(self, base_url: str = "https://api.elections.kalshi.com/trade-api/v2") -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        request = Request(f"{self.base_url}/{path.lstrip('/')}" + (f"?{query}" if query else ""), headers={"Accept": "application/json"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def markets(self, limit: int = 100, cursor: str | None = None, category: str | None = None) -> dict[str, Any]:
        return self.get("markets", limit=limit, cursor=cursor, series_ticker=category)

    def market(self, ticker: str) -> dict[str, Any]:
        return self.get(f"markets/{ticker}")

    def candlesticks(self, ticker: str, start_ts: int | None = None, end_ts: int | None = None, period_interval: int = 60) -> dict[str, Any]:
        return self.get(f"markets/{ticker}/candlesticks", start_ts=start_ts, end_ts=end_ts, period_interval=period_interval)
