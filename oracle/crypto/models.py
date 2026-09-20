from dataclasses import dataclass


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
    volume: float | None = None
    quote_volume: float | None = None
    trades: int | None = None
