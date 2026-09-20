from typing import Any


LEVELS = (
    ("fib_236", 0.236),
    ("fib_382", 0.382),
    ("fib_50", 0.5),
    ("fib_618", 0.618),
    ("fib_786", 0.786),
)
EXTENSIONS = (
    ("ext_1272", 1.272),
    ("ext_1618", 1.618),
)


def fibonacci_from_swings(high: float, low: float, direction: str, price: float) -> dict[str, Any]:
    span = high - low
    if span <= 0:
        return {}
    if direction == "up":
        retrace = {name: high - span * ratio for name, ratio in LEVELS}
        extend = {name: high + span * (ratio - 1.0) for name, ratio in EXTENSIONS}
    else:
        retrace = {name: low + span * ratio for name, ratio in LEVELS}
        extend = {name: low - span * (ratio - 1.0) for name, ratio in EXTENSIONS}
    levels = {**retrace, **extend}
    nearest = min(levels, key=lambda name: abs(levels[name] - price))
    return {
        **levels,
        "direction": direction,
        "nearest_level": nearest,
        "distance_to_nearest": price - levels[nearest],
    }
