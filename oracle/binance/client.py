"""Public, read-only Binance REST client for OHLCV klines."""

from __future__ import annotations

from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


class BinanceClient:
    """Spot klines only. No signed endpoints, keys, or orders."""

    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, retries: int = 3, **params: Any) -> Any:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        request = Request(
            f"{self.base_url}/{path.lstrip('/')}" + (f"?{query}" if query else ""),
            headers={"Accept": "application/json"},
        )
        for attempt in range(retries):
            try:
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except (HTTPError, URLError, TimeoutError):
                if attempt == retries - 1:
                    raise
                sleep(2 ** attempt)

    def klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 1000,
    ) -> list[list[Any]]:
        payload = self.get(
            "api/v3/klines",
            symbol=symbol.upper(),
            interval=interval,
            startTime=start_ms,
            endTime=end_ms,
            limit=min(limit, 1000),
        )
        if not isinstance(payload, list):
            raise ValueError("Binance klines response was not a list")
        return payload
