"""Small, deterministic approximate ephemeris for offline research.

This is not a historical Merlin reconstruction and is not suitable for
precision astrology. It provides reproducible inputs until a verified
ephemeris library/data source is selected.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import fmod

ASTRONOMY_VERSION = "approximate-orbital-v0"
J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

# Mean orbital periods and approximate J2000 ecliptic longitudes.
ORBITAL_BODIES = {
    "Mercury": (87.969, 252.25),
    "Venus": (224.701, 181.98),
    "Earth": (365.256, 100.46),
    "Mars": (686.980, 355.45),
    "Jupiter": (4332.589, 34.40),
    "Saturn": (10759.22, 50.08),
    "Uranus": (30688.5, 314.20),
    "Neptune": (60182.0, 304.35),
    "Pluto": (90560.0, 238.96),
}


@dataclass(frozen=True)
class AstronomicalState:
    timestamp: str
    julian_days_since_j2000: float
    positions: dict[str, float]
    version: str = ASTRONOMY_VERSION


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def calculate_state(timestamp: str | datetime) -> AstronomicalState:
    moment = _utc(timestamp)
    days = (moment - J2000).total_seconds() / 86400
    positions = {
        body: fmod(longitude + days * 360 / period, 360.0) % 360.0
        for body, (period, longitude) in ORBITAL_BODIES.items()
    }
    return AstronomicalState(moment.isoformat(), days, positions)
