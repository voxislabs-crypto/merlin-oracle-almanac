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


@dataclass(frozen=True)
class Market:
    ticker: str
    event: str | None = None
    title: str | None = None
    category: str | None = None
    created_time: str | None = None
    open_time: str | None = None
    close_time: str | None = None
    settlement_time: str | None = None
    status: str | None = None
    rules: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Market":
        return cls(
            ticker=payload["ticker"],
            event=payload.get("event_ticker") or payload.get("event"),
            title=payload.get("title") or payload.get("subtitle"),
            category=payload.get("category"),
            created_time=utc_timestamp(payload.get("created_time")),
            open_time=utc_timestamp(payload.get("open_time")),
            close_time=utc_timestamp(payload.get("close_time")),
            settlement_time=utc_timestamp(payload.get("settlement_time")),
            status=payload.get("status"),
            rules=payload.get("rules_primary") or payload.get("rules"),
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

    @property
    def natural_key(self) -> tuple[str, str]:
        return self.ticker, self.timestamp
