"""Experimental TimeTrak calculation over the local approximate ephemeris."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .astronomy import AstronomicalState, calculate_state

TIMETRAK_VERSION = "TimeTrak_Experimental_Astronomy_v0"
ASPECTS = ((0.0, "conjunction"), (60.0, "sextile"), (90.0, "square"), (120.0, "trine"), (180.0, "opposition"))


@dataclass(frozen=True)
class TimeTrakSignal:
    timestamp: str
    object_a: str
    object_b: str
    aspect: str
    orb: float
    direction: str
    intensity: float
    onset: str
    peak: str
    duration_hours: float
    astronomy_version: str
    calculation_version: str = TIMETRAK_VERSION


def _separation(first: float, second: float) -> float:
    distance = abs(first - second) % 360
    return min(distance, 360 - distance)


def _aspect(separation: float) -> tuple[str, float]:
    target, name = min(ASPECTS, key=lambda item: abs(separation - item[0]))
    return name, abs(separation - target)


def calculate_signal(timestamp: str | datetime, object_a: str = "Saturn", object_b: str = "Pluto", max_orb: float = 8.0) -> TimeTrakSignal:
    state = calculate_state(timestamp)
    separation = _separation(state.positions[object_a], state.positions[object_b])
    aspect, orb = _aspect(separation)
    intensity = round(max(0.0, min(100.0, (1 - orb / max_orb) * 100)), 2)
    moment = datetime.fromisoformat(state.timestamp)
    duration_hours = round(max(1.0, (max_orb - orb) * 6), 2)
    onset = (moment - timedelta(hours=duration_hours / 2)).isoformat()
    peak = moment.isoformat()
    direction = "applying" if orb < max_orb / 2 else "separating"
    return TimeTrakSignal(state.timestamp, object_a, object_b, aspect, round(orb, 4), direction, intensity, onset, peak, duration_hours, state.version)
