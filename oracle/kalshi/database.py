import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING

from .models import Market, Observation

if TYPE_CHECKING:
    from ..binance.models import Candle
    from ..spread import SpreadSnapshot


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
                ticker TEXT PRIMARY KEY, event TEXT, title TEXT, question TEXT,
                category TEXT, created_time TEXT, open_time TEXT, close_time TEXT,
                settlement_time TEXT, status TEXT, rules TEXT,
                settlement_source TEXT, schema_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS market_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL, yes_price REAL, no_price REAL,
                yes_bid REAL, yes_ask REAL, volume REAL, open_interest REAL,
                sky_signal REAL, sky_aspect TEXT, sky_orb REAL, sky_direction TEXT,
                sky_onset TEXT, sky_peak TEXT, sky_duration_hours REAL,
                astronomy_version TEXT, timetrak_version TEXT,
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
                fetched_at TEXT NOT NULL, schema_version TEXT NOT NULL, payload_sha256 TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL, records_seen INTEGER NOT NULL,
                records_imported INTEGER NOT NULL, duplicates_skipped INTEGER NOT NULL,
                errors INTEGER NOT NULL, schema_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS candles (
                source TEXT NOT NULL,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                open_time TEXT NOT NULL,
                close_time TEXT,
                open REAL, high REAL, low REAL, close REAL,
                volume REAL, quote_volume REAL, trade_count INTEGER,
                schema_version TEXT NOT NULL,
                UNIQUE(source, symbol, interval, open_time)
            );
            CREATE TABLE IF NOT EXISTS truth_ticks (
                source TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                note TEXT,
                schema_version TEXT NOT NULL,
                UNIQUE(source, symbol, timestamp)
            );
            CREATE TABLE IF NOT EXISTS spread_snapshots (
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                sight_source TEXT NOT NULL,
                sight_price REAL,
                truth_source TEXT NOT NULL,
                truth_price REAL,
                abs_gap REAL,
                gap_bps REAL,
                threshold_bps REAL NOT NULL,
                gate TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                UNIQUE(timestamp, symbol, sight_source, truth_source)
            );
            """
        )
        market_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(markets)")}
        for name, column_type in {
            "question": "TEXT",
            "settlement_source": "TEXT",
        }.items():
            if name not in market_columns:
                self.connection.execute(f"ALTER TABLE markets ADD COLUMN {name} {column_type}")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(raw_api_responses)")}
        if "payload_sha256" not in columns:
            self.connection.execute("ALTER TABLE raw_api_responses ADD COLUMN payload_sha256 TEXT NOT NULL DEFAULT ''")
        observation_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(market_observations)")}
        for name, column_type in {
            "sky_signal": "REAL", "sky_aspect": "TEXT", "sky_orb": "REAL", "sky_direction": "TEXT",
            "sky_onset": "TEXT", "sky_peak": "TEXT", "sky_duration_hours": "REAL",
            "astronomy_version": "TEXT", "timetrak_version": "TEXT",
        }.items():
            if name not in observation_columns:
                self.connection.execute(f"ALTER TABLE market_observations ADD COLUMN {name} {column_type}")
        self.connection.commit()

    def save_candles(self, candles: Iterable["Candle"]) -> tuple[int, int]:
        imported = 0
        duplicates = 0
        for candle in candles:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO candles
                (source, symbol, interval, open_time, close_time, open, high, low, close,
                 volume, quote_volume, trade_count, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    candle.source, candle.symbol, candle.interval, candle.open_time, candle.close_time,
                    candle.open, candle.high, candle.low, candle.close, candle.volume,
                    candle.quote_volume, candle.trade_count, SCHEMA_VERSION,
                ),
            )
            if cursor.rowcount:
                imported += 1
            else:
                duplicates += 1
        self.connection.commit()
        return imported, duplicates

    def save_truth_tick(self, source: str, symbol: str, timestamp: str, price: float, note: str | None = None) -> None:
        self.connection.execute(
            """INSERT INTO truth_ticks(source, symbol, timestamp, price, note, schema_version)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source, symbol, timestamp) DO UPDATE SET
               price=excluded.price, note=excluded.note""",
            (source, symbol.upper(), timestamp, price, note, SCHEMA_VERSION),
        )
        self.connection.commit()

    def save_spread(self, snap: "SpreadSnapshot") -> None:
        self.connection.execute(
            """INSERT INTO spread_snapshots
               (timestamp, symbol, sight_source, sight_price, truth_source, truth_price,
                abs_gap, gap_bps, threshold_bps, gate, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(timestamp, symbol, sight_source, truth_source) DO UPDATE SET
               sight_price=excluded.sight_price, truth_price=excluded.truth_price,
               abs_gap=excluded.abs_gap, gap_bps=excluded.gap_bps,
               threshold_bps=excluded.threshold_bps, gate=excluded.gate""",
            (
                snap.timestamp, snap.symbol, snap.sight_source, snap.sight_price,
                snap.truth_source, snap.truth_price, snap.abs_gap, snap.gap_bps,
                snap.threshold_bps, snap.gate, SCHEMA_VERSION,
            ),
        )
        self.connection.commit()

    def latest_candle_close(self, source: str, symbol: str, interval: str, at_or_before: str) -> float | None:
        row = self.connection.execute(
            """SELECT close FROM candles
               WHERE source = ? AND symbol = ? AND interval = ? AND open_time <= ?
               ORDER BY open_time DESC LIMIT 1""",
            (source, symbol.upper(), interval, at_or_before),
        ).fetchone()
        return None if row is None else float(row[0])

    def truth_at(self, source: str, symbol: str, at_or_before: str) -> float | None:
        row = self.connection.execute(
            """SELECT price FROM truth_ticks
               WHERE source = ? AND symbol = ? AND timestamp <= ?
               ORDER BY timestamp DESC LIMIT 1""",
            (source, symbol.upper(), at_or_before),
        ).fetchone()
        return None if row is None else float(row[0])

    def save_market(self, market: Market) -> None:
        self.connection.execute(
            """INSERT INTO markets (ticker, event, title, question, category, created_time, open_time, close_time,
            settlement_time, status, rules, settlement_source, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET event=excluded.event, title=excluded.title,
               question=excluded.question, category=excluded.category, created_time=excluded.created_time,
               open_time=excluded.open_time, close_time=excluded.close_time, settlement_time=excluded.settlement_time,
               status=excluded.status, rules=excluded.rules, settlement_source=excluded.settlement_source,
               schema_version=excluded.schema_version""",
            (
                market.ticker, market.event, market.title, market.question, market.category,
                market.created_time, market.open_time, market.close_time, market.settlement_time,
                market.status, market.rules, market.settlement_source, SCHEMA_VERSION,
            ),
        )
        self.connection.commit()

    def save_raw(self, ticker: str | None, endpoint: str, payload: Any) -> None:
        serialized = json.dumps(payload, sort_keys=True)
        self.connection.execute(
            "INSERT INTO raw_api_responses(ticker, endpoint, fetched_at, schema_version, payload_sha256, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, endpoint, datetime.now(timezone.utc).isoformat(), SCHEMA_VERSION, hashlib.sha256(serialized.encode()).hexdigest(), serialized),
        )
        self.connection.commit()

    def save_observations(self, observations: Iterable[Observation]) -> tuple[int, int]:
        imported = 0
        duplicates = 0
        for observation in observations:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO market_observations
                (ticker, timestamp, yes_price, no_price, yes_bid, yes_ask, volume, open_interest,
                 sky_signal, sky_aspect, sky_orb, sky_direction, sky_onset, sky_peak,
                 sky_duration_hours, astronomy_version, timetrak_version, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
        candle_bounds = self.connection.execute("SELECT MIN(open_time), MAX(open_time) FROM candles").fetchone()
        gates = self.connection.execute("SELECT gate, COUNT(*) FROM spread_snapshots GROUP BY gate").fetchall()
        return {
            "markets": count("markets"),
            "observations": count("market_observations"),
            "results": count("market_results"),
            "candles": count("candles"),
            "truth_ticks": count("truth_ticks"),
            "spread_snapshots": count("spread_snapshots"),
            "spread_gates": {row[0]: row[1] for row in gates},
            "earliest_timestamp": bounds[0],
            "latest_timestamp": bounds[1],
            "earliest_candle": candle_bounds[0],
            "latest_candle": candle_bounds[1],
            "last_import": last[0] if last else None,
        }

    def close(self) -> None:
        self.connection.close()
