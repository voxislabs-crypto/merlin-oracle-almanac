from os import getenv
from time import sleep
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from ..kalshi.models import utc_timestamp


INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}
DEFAULT_HOSTS = (
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api.binance.us",
)


def interval_seconds(interval: str) -> int:
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"Unsupported interval {interval!r}. Use {', '.join(INTERVAL_SECONDS)}")
    return INTERVAL_SECONDS[interval]


class BinanceClient:
    """Public, read-only Binance market data. No account or order methods exist here."""

    def __init__(self, base_url: str | None = None) -> None:
        preferred = (base_url or getenv("BINANCE_API_URL") or "").rstrip("/")
        hosts = [preferred] if preferred else []
        hosts.extend(host for host in DEFAULT_HOSTS if host not in hosts)
        self.hosts = hosts
        self.base_url = self.hosts[0]

    def get(self, path: str, retries: int = 3, **params: Any) -> Any:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        last_error: Exception | None = None
        for host in list(self.hosts):
            request = Request(
                f"{host}/{path.lstrip('/')}" + (f"?{query}" if query else ""),
                headers={"Accept": "application/json"},
            )
            for attempt in range(retries):
                try:
                    with urlopen(request, timeout=30) as response:
                        self.base_url = host
                        return json.load(response)
                except HTTPError as error:
                    last_error = error
                    if error.code == 429 and attempt < retries - 1:
                        sleep(2 ** attempt)
                        continue
                    if error.code in {403, 418, 451}:
                        break
                    raise
                except (URLError, TimeoutError) as error:
                    last_error = error
                    if attempt == retries - 1:
                        break
                    sleep(2 ** attempt)
        if last_error:
            raise last_error
        raise URLError("Binance public kline hosts were unreachable")

    def klines(
        self,
        symbol: str,
        interval: str = "1m",
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int = 1000,
    ) -> list[list[Any]]:
        interval_seconds(interval)
        payload = self.get(
            "api/v3/klines",
            symbol=symbol.upper(),
            interval=interval,
            startTime=start_ts * 1000 if start_ts is not None else None,
            endTime=end_ts * 1000 if end_ts is not None else None,
            limit=min(max(limit, 1), 1000),
        )
        if not isinstance(payload, list):
            raise ValueError("Binance klines response was not a list")
        return payload

    def iter_klines(
        self,
        symbol: str,
        interval: str = "1m",
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> Iterator[list[Any]]:
        step = interval_seconds(interval)
        cursor = start_ts
        while True:
            batch = self.klines(symbol, interval, start_ts=cursor, end_ts=end_ts, limit=1000)
            if not batch:
                break
            yield from batch
            last_open_ms = int(batch[-1][0])
            next_ts = (last_open_ms // 1000) + step
            if end_ts is not None and next_ts >= end_ts:
                break
            if cursor is not None and next_ts <= cursor:
                break
            cursor = next_ts
            if len(batch) < 1000:
                break


def kline_to_row(symbol: str, interval: str, kline: list[Any], source: str = "binance") -> dict[str, Any]:
    open_ms = int(kline[0])
    close_ms = int(kline[6])
    return {
        "source": source,
        "symbol": symbol.upper(),
        "interval": interval,
        "open_time": utc_timestamp(open_ms / 1000),
        "close_time": utc_timestamp(close_ms / 1000),
        "open": float(kline[1]),
        "high": float(kline[2]),
        "low": float(kline[3]),
        "close": float(kline[4]),
        "volume": float(kline[5]),
        "quote_volume": float(kline[7]),
        "trades": int(kline[8]),
    }
