import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Market, Observation


SCHEMA_VERSION = "kalshi-v1"


class KalshiDatabase:
    """Small SQLite store that preserves raw payloads and normalized records."""

    def __init__(self, path: str | Path = "data/kalshi.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS markets (
                ticker TEXT PRIMARY KEY, event TEXT, title TEXT, category TEXT,
                created_time TEXT, open_time TEXT, close_time TEXT,
                settlement_time TEXT, status TEXT, rules TEXT,
                schema_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS market_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL, yes_price REAL, no_price REAL,
                yes_bid REAL, yes_ask REAL, volume REAL, open_interest REAL,
                schema_version TEXT NOT NULL,
                UNIQUE(ticker, timestamp), FOREIGN KEY(ticker) REFERENCES markets(ticker)
            );
            CREATE TABLE IF NOT EXISTS market_results (
                ticker TEXT PRIMARY KEY, outcome TEXT, settlement_time TEXT,
                settlement_source TEXT, schema_version TEXT NOT NULL,
                FOREIGN KEY(ticker) REFERENCES markets(ticker)
            );
            CREATE TABLE IF NOT EXISTS raw_api_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, endpoint TEXT NOT NULL,
                fetched_at TEXT NOT NULL, schema_version TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL, records_seen INTEGER NOT NULL,
                records_imported INTEGER NOT NULL, duplicates_skipped INTEGER NOT NULL,
                errors INTEGER NOT NULL, schema_version TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def save_market(self, market: Market) -> None:
        self.connection.execute(
            """INSERT INTO markets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET event=excluded.event, title=excluded.title,
               category=excluded.category, created_time=excluded.created_time, open_time=excluded.open_time,
               close_time=excluded.close_time, settlement_time=excluded.settlement_time,
               status=excluded.status, rules=excluded.rules, schema_version=excluded.schema_version""",
            (*market.__dict__.values(), SCHEMA_VERSION),
        )
        self.connection.commit()

    def save_raw(self, ticker: str | None, endpoint: str, payload: Any) -> None:
        self.connection.execute(
            "INSERT INTO raw_api_responses(ticker, endpoint, fetched_at, schema_version, payload) VALUES (?, ?, ?, ?, ?)",
            (ticker, endpoint, datetime.now(timezone.utc).isoformat(), SCHEMA_VERSION, json.dumps(payload)),
        )
        self.connection.commit()

    def save_observations(self, observations: Iterable[Observation]) -> tuple[int, int]:
        imported = 0
        duplicates = 0
        for observation in observations:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO market_observations
                (ticker, timestamp, yes_price, no_price, yes_bid, yes_ask, volume, open_interest, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*observation.__dict__.values(), SCHEMA_VERSION),
            )
            if cursor.rowcount:
                imported += 1
            else:
                duplicates += 1
        self.connection.commit()
        return imported, duplicates

    def save_result(self, ticker: str, outcome: str | None, settlement_time: str | None, source: str | None) -> None:
        self.connection.execute(
            """INSERT INTO market_results VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET outcome=excluded.outcome,
               settlement_time=excluded.settlement_time, settlement_source=excluded.settlement_source""",
            (ticker, outcome, settlement_time, source, SCHEMA_VERSION),
        )
        self.connection.commit()

    def log_import(self, ticker: str | None, started_at: str, seen: int, imported: int, duplicates: int, errors: int) -> None:
        self.connection.execute(
            "INSERT INTO import_log VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, started_at, datetime.now(timezone.utc).isoformat(), seen, imported, duplicates, errors, SCHEMA_VERSION),
        )
        self.connection.commit()

    def status(self) -> dict[str, Any]:
        def count(table: str) -> int:
            return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        bounds = self.connection.execute("SELECT MIN(timestamp), MAX(timestamp) FROM market_observations").fetchone()
        last = self.connection.execute("SELECT finished_at FROM import_log ORDER BY id DESC LIMIT 1").fetchone()
        return {"markets": count("markets"), "observations": count("market_observations"), "results": count("market_results"), "earliest_timestamp": bounds[0], "latest_timestamp": bounds[1], "last_import": last[0] if last else None}

    def close(self) -> None:
        self.connection.close()
