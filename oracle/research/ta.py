from math import sqrt
from typing import Iterable


def _finite(values: Iterable[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None]


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    multiplier = 2.0 / (period + 1)
    current = seed
    for index in range(period, len(values)):
        current = values[index] * multiplier + current * (1.0 - multiplier)
        result[index] = current
    return result


def rma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    current = sum(values[:period]) / period
    result[period - 1] = current
    for index in range(period, len(values)):
        current = (current * (period - 1) + values[index]) / period
        result[index] = current
    return result


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    if len(closes) < 2:
        return [None] * len(closes)
    gains = [0.0]
    losses = [0.0]
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = rma(gains, period)
    avg_loss = rma(losses, period)
    out: list[float | None] = []
    for gain, loss in zip(avg_gain, avg_loss):
        if gain is None or loss is None:
            out.append(None)
        elif loss == 0:
            out.append(100.0)
        else:
            relative = gain / loss
            out.append(100.0 - (100.0 / (1.0 + relative)))
    return out


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_line = ema(closes, fast)
    slow_line = ema(closes, slow)
    macd_line: list[float | None] = []
    macd_values: list[float] = []
    macd_index: list[int] = []
    for index, (left, right) in enumerate(zip(fast_line, slow_line)):
        if left is None or right is None:
            macd_line.append(None)
        else:
            value = left - right
            macd_line.append(value)
            macd_values.append(value)
            macd_index.append(index)
    signal_line: list[float | None] = [None] * len(closes)
    hist: list[float | None] = [None] * len(closes)
    if macd_values:
        smoothed = ema(macd_values, signal)
        for position, value in zip(macd_index, smoothed):
            signal_line[position] = value
            if value is not None and macd_line[position] is not None:
                hist[position] = macd_line[position] - value
    return macd_line, signal_line, hist


def true_range(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    ranges = [highs[0] - lows[0]]
    for index in range(1, len(closes)):
        ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
    return ranges


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    return rma(true_range(highs, lows, closes), period)


def vwap(highs: list[float], lows: list[float], closes: list[float], volumes: list[float], session_ids: list[str]) -> list[float | None]:
    out: list[float | None] = []
    pv = 0.0
    vol = 0.0
    current = None
    for high, low, close, volume, session in zip(highs, lows, closes, volumes, session_ids):
        if session != current:
            pv = 0.0
            vol = 0.0
            current = session
        typical = (high + low + close) / 3.0
        pv += typical * volume
        vol += volume
        out.append(pv / vol if vol else None)
    return out


def stdev(window: list[float]) -> float | None:
    if len(window) < 2:
        return None
    mean = sum(window) / len(window)
    variance = sum((value - mean) ** 2 for value in window) / (len(window) - 1)
    return sqrt(variance)


def rolling_stdev(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = []
    for index in range(len(values)):
        start = max(0, index + 1 - period)
        out.append(stdev(values[start : index + 1]) if index + 1 >= period else None)
    return out
