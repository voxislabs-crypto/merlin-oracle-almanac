from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_timestamp(value: Any) -> str | None:
    """Return an ISO-8601 UTC timestamp without changing missing values."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def unix_seconds(value: Any) -> int | None:
    stamp = utc_timestamp(value)
    if stamp is None:
        return None
    return int(datetime.fromisoformat(stamp).timestamp())


def price_cents(value: Any) -> float | None:
    """Normalize Kalshi dollars or legacy cents into contract cents."""
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        for key in (
            "close_dollars",
            "close",
            "mean_dollars",
            "mean",
            "open_dollars",
            "open",
            "yes_price",
        ):
            if value.get(key) not in (None, ""):
                return price_cents(value[key])
        return None
    number = float(value)
    if 0 <= number <= 1.5:
        return round(number * 100.0, 4)
    return number


@dataclass(frozen=True)
class Market:
    ticker: str
    event: str | None = None
    title: str | None = None
    question: str | None = None
    category: str | None = None
    created_time: str | None = None
    open_time: str | None = None
    close_time: str | None = None
    settlement_time: str | None = None
    status: str | None = None
    rules: str | None = None
    settlement_source: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Market":
        return cls(
            ticker=payload["ticker"],
            event=payload.get("event_ticker") or payload.get("event"),
            title=payload.get("title") or payload.get("subtitle"),
            question=payload.get("question") or payload.get("title") or payload.get("subtitle"),
            category=payload.get("category"),
            created_time=utc_timestamp(payload.get("created_time")),
            open_time=utc_timestamp(payload.get("open_time")),
            close_time=utc_timestamp(payload.get("close_time")),
            settlement_time=utc_timestamp(payload.get("settlement_time") or payload.get("close_time")),
            status=payload.get("status"),
            rules=payload.get("rules_primary") or payload.get("rules"),
            settlement_source=payload.get("settlement_source") or payload.get("official_source"),
        )


@dataclass(frozen=True)
class Observation:
    ticker: str
    timestamp: str
    yes_price: float | None = None
    no_price: float | None = None
    yes_bid: float | None = None
    yes_ask: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    sky_signal: float | None = None
    sky_aspect: str | None = None
    sky_orb: float | None = None
    sky_direction: str | None = None
    sky_onset: str | None = None
    sky_peak: str | None = None
    sky_duration_hours: float | None = None
    astronomy_version: str | None = None
    timetrak_version: str | None = None

    @property
    def natural_key(self) -> tuple[str, str]:
        return self.ticker, self.timestamp
