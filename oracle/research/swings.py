from typing import Any


def confirmed_swings(candles: list[dict[str, Any]], strength: int = 2) -> list[dict[str, Any]]:
    """Swing highs/lows that are known only after `strength` bars have closed on the right."""
    found: list[dict[str, Any]] = []
    if len(candles) < strength * 2 + 1:
        return found
    for index in range(strength, len(candles) - strength):
        high = candles[index]["high"]
        low = candles[index]["low"]
        left = candles[index - strength : index]
        right = candles[index + 1 : index + 1 + strength]
        if all(high > bar["high"] for bar in left + right):
            found.append(
                {
                    "kind": "high",
                    "index": index,
                    "price": high,
                    "time": candles[index]["close_time"],
                    "confirmed_at": candles[index + strength]["close_time"],
                }
            )
        if all(low < bar["low"] for bar in left + right):
            found.append(
                {
                    "kind": "low",
                    "index": index,
                    "price": low,
                    "time": candles[index]["close_time"],
                    "confirmed_at": candles[index + strength]["close_time"],
                }
            )
    return found


def swings_known_at(swings: list[dict[str, Any]], timestamp: str) -> list[dict[str, Any]]:
    return [swing for swing in swings if swing["confirmed_at"] <= timestamp]


def last_impulse(swings: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    highs = [swing for swing in swings if swing["kind"] == "high"]
    lows = [swing for swing in swings if swing["kind"] == "low"]
    if not highs or not lows:
        return None, None, None
    last_high = highs[-1]
    last_low = lows[-1]
    if last_low["time"] <= last_high["time"]:
        return last_high, last_low, "up"
    return last_high, last_low, "down"


def market_structure(swings: list[dict[str, Any]]) -> tuple[str, str]:
    highs = [swing["price"] for swing in swings if swing["kind"] == "high"]
    lows = [swing["price"] for swing in swings if swing["kind"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "unknown", "insufficient_swings"
    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]
    if hh and hl:
        return "up", "higher_highs_higher_lows"
    if (not hh) and (not hl):
        return "down", "lower_highs_lower_lows"
    return "range", "mixed_swings"
