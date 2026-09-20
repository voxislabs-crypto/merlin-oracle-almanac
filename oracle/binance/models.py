from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_from_ms(value: int | float) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


@dataclass(frozen=True)
class Candle:
    source: str
    symbol: str
    interval: str
    open_time: str
    close_time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    trade_count: int | None = None

    @classmethod
    def from_binance(cls, row: list[Any], symbol: str, interval: str) -> "Candle":
        return cls(
            source="binance",
            symbol=symbol.upper(),
            interval=interval,
            open_time=utc_from_ms(int(row[0])),
            close_time=utc_from_ms(int(row[6])),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            quote_volume=float(row[7]) if row[7] not in (None, "") else None,
            trade_count=int(row[8]) if row[8] not in (None, "") else None,
        )
