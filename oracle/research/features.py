from typing import Any

from .fibonacci import fibonacci_from_swings
from .patterns import candle_pattern
from .swings import confirmed_swings, last_impulse, market_structure, swings_known_at
from .ta import atr, ema, macd, rolling_stdev, rsi, vwap


def _row(candle: Any) -> dict[str, Any]:
    if isinstance(candle, dict):
        return dict(candle)
    return {key: candle[key] for key in candle.keys()}


def compute_feature_rows(candles: list[Any], source: str, symbol: str, interval: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [_row(candle) for candle in candles]
    if not rows:
        return [], []
    closes = [float(row["close"]) for row in rows]
    highs = [float(row["high"]) for row in rows]
    lows = [float(row["low"]) for row in rows]
    volumes = [float(row["volume"] or 0.0) for row in rows]
    sessions = [str(row["close_time"])[:10] for row in rows]
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi_line = rsi(closes)
    macd_line, signal_line, hist = macd(closes)
    atr_line = atr(highs, lows, closes)
    vwap_line = vwap(highs, lows, closes, volumes, sessions)
    vol = rolling_stdev(closes)
    swings = confirmed_swings(rows)
    technical = []
    fibonacci = []
    for index, row in enumerate(rows):
        known = swings_known_at(swings, row["close_time"])
        high, low, direction = last_impulse(known)
        trend, structure = market_structure(known)
        volume_change = None
        if index and volumes[index - 1]:
            volume_change = (volumes[index] - volumes[index - 1]) / volumes[index - 1]
        technical.append(
            {
                "source": source,
                "symbol": symbol,
                "interval": interval,
                "timestamp": row["close_time"],
                "ema_9": ema9[index],
                "ema_21": ema21[index],
                "ema_50": ema50[index],
                "rsi": rsi_line[index],
                "macd": macd_line[index],
                "macd_signal": signal_line[index],
                "macd_hist": hist[index],
                "atr": atr_line[index],
                "vwap": vwap_line[index],
                "volume": volumes[index],
                "volume_change": volume_change,
                "volatility": vol[index],
                "trend_state": trend,
                "market_structure": structure,
                "swing_high": high["price"] if high else None,
                "swing_low": low["price"] if low else None,
                "candle_pattern": candle_pattern(rows[: index + 1]),
            }
        )
        if high and low and direction:
            levels = fibonacci_from_swings(high["price"], low["price"], direction, closes[index])
            if levels:
                fibonacci.append(
                    {
                        "source": source,
                        "symbol": symbol,
                        "interval": interval,
                        "timestamp": row["close_time"],
                        "swing_high": high["price"],
                        "swing_high_time": high["time"],
                        "swing_low": low["price"],
                        "swing_low_time": low["time"],
                        **levels,
                    }
                )
    return technical, fibonacci
