def candle_pattern(candles: list[dict]) -> str | None:
    if not candles:
        return None
    current = candles[-1]
    body = abs(current["close"] - current["open"])
    span = current["high"] - current["low"]
    if span <= 0:
        return "doji"
    upper = current["high"] - max(current["open"], current["close"])
    lower = min(current["open"], current["close"]) - current["low"]
    if body / span < 0.1:
        return "doji"
    if lower >= 2 * body and upper <= body:
        return "hammer"
    if upper >= 2 * body and lower <= body:
        return "shooting_star"
    if len(candles) < 2:
        return None
    previous = candles[-2]
    prev_body = abs(previous["close"] - previous["open"])
    bullish = current["close"] > current["open"]
    prev_bear = previous["close"] < previous["open"]
    prev_bull = previous["close"] > previous["open"]
    if (
        bullish
        and prev_bear
        and current["open"] <= previous["close"]
        and current["close"] >= previous["open"]
        and body > prev_body
    ):
        return "bullish_engulfing"
    if (
        (not bullish)
        and prev_bull
        and current["open"] >= previous["close"]
        and current["close"] <= previous["open"]
        and body > prev_body
    ):
        return "bearish_engulfing"
    return None
