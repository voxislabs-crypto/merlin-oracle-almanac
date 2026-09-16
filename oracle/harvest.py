from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
import json

from .kalshi.database import KalshiDatabase


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    source_type: str
    adapter: str


class SourceRegistry:
    def __init__(self, sources: Iterable[SourceDefinition]) -> None:
        self.sources = list(sources)

    @classmethod
    def default_registry(cls) -> "SourceRegistry":
        return cls(
            [
                SourceDefinition("Kalshi", "prediction_market", "kalshi.py"),
                SourceDefinition("Polymarket", "prediction_market", "polymarket.py"),
                SourceDefinition("Metaculus", "forecasting", "metaculus.py"),
                SourceDefinition("Manifold", "forecasting", "manifold.py"),
                SourceDefinition("FRED", "economic", "fred.py"),
                SourceDefinition("NOAA", "weather", "noaa.py"),
                SourceDefinition("Custom", "user_defined", "generic.py"),
            ]
        )


@dataclass
class EventDossier:
    id: str
    question: str
    sources: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OracleHarvester:
    def __init__(self, database: KalshiDatabase) -> None:
        self.database = database
        self.registry = SourceRegistry.default_registry()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.database.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS event_dossiers (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                sources TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS raw_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dossier_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                market_ticker TEXT,
                observed_at TEXT NOT NULL,
                data_type TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                normalized_value REAL,
                url TEXT,
                FOREIGN KEY(dossier_id) REFERENCES event_dossiers(id)
            );
            """
        )
        self.database.connection.commit()

    def create_dossier(self, question: str, sources: list[str] | None = None) -> EventDossier:
        normalized_sources = list(sources or [])
        dossier_id = "dossier-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        dossier = EventDossier(id=dossier_id, question=question, sources=normalized_sources)
        self.database.connection.execute(
            "INSERT INTO event_dossiers(id, question, sources, created_at) VALUES (?, ?, ?, ?)",
            (dossier.id, dossier.question, json.dumps(dossier.sources), dossier.created_at),
        )
        self.database.connection.commit()
        return dossier

    def record_observation(
        self,
        dossier_id: str,
        source_name: str,
        market_ticker: str | None,
        observed_at: str,
        data_type: str,
        raw_value: Any,
        normalized_value: float | None,
        url: str | None = None,
    ) -> None:
        self.database.connection.execute(
            "INSERT INTO raw_observations(dossier_id, source_name, market_ticker, observed_at, data_type, raw_value, normalized_value, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                dossier_id,
                source_name,
                market_ticker,
                observed_at,
                data_type,
                str(raw_value),
                normalized_value,
                url,
            ),
        )
        self.database.connection.commit()

    def list_sources(self) -> list[str]:
        return [source.name for source in self.registry.sources]
