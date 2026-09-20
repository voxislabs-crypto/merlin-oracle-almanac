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
RESEARCH_SCHEMA = "research-v1"


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
            CREATE TABLE IF NOT EXISTS technical_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                ema_9 REAL, ema_21 REAL, ema_50 REAL,
                rsi REAL, macd REAL, macd_signal REAL, macd_hist REAL,
                atr REAL, vwap REAL, volume REAL, volume_change REAL, volatility REAL,
                trend_state TEXT, market_structure TEXT,
                swing_high REAL, swing_low REAL, candle_pattern TEXT,
                schema_version TEXT NOT NULL,
                UNIQUE(source, symbol, interval, timestamp)
            );
            CREATE TABLE IF NOT EXISTS fibonacci_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                swing_high REAL, swing_high_time TEXT, swing_low REAL, swing_low_time TEXT,
                direction TEXT,
                fib_236 REAL, fib_382 REAL, fib_50 REAL, fib_618 REAL, fib_786 REAL,
                ext_1272 REAL, ext_1618 REAL,
                nearest_level TEXT, distance_to_nearest REAL,
                schema_version TEXT NOT NULL,
                UNIQUE(source, symbol, interval, timestamp)
            );
            CREATE TABLE IF NOT EXISTS trade_reconstructions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL, offset TEXT NOT NULL, timestamp TEXT NOT NULL,
                contract TEXT, target REAL, expiration TEXT,
                btc_price REAL, distance_to_target REAL, time_to_expiration_seconds INTEGER,
                rsi REAL, macd REAL, atr REAL, ema_9 REAL, ema_21 REAL, ema_50 REAL, vwap REAL,
                volume REAL, volatility REAL, trend_state TEXT, market_structure TEXT,
                fib_236 REAL, fib_382 REAL, fib_50 REAL, fib_618 REAL, fib_786 REAL,
                kalshi_yes_price REAL, kalshi_no_price REAL, implied_probability REAL,
                quiet INTEGER, spread_bps REAL, usable_at_entry INTEGER NOT NULL,
                final_result TEXT, source TEXT NOT NULL, schema_version TEXT NOT NULL,
                UNIQUE(trade_id, offset)
            );
            CREATE INDEX IF NOT EXISTS idx_candles_lookup
                ON candles(source, symbol, interval, close_time);
            CREATE INDEX IF NOT EXISTS idx_reconstructions_trade
                ON trade_reconstructions(trade_id, timestamp);
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
        candle_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(candles)")}
        if "trades" not in candle_columns:
            try:
                self.connection.execute("ALTER TABLE candles ADD COLUMN trades INTEGER")
            except sqlite3.Error:
                pass
        if "trade_count" not in candle_columns:
            try:
                self.connection.execute("ALTER TABLE candles ADD COLUMN trade_count INTEGER")
            except sqlite3.Error:
                pass
        self.connection.commit()

    def save_candles(self, candles: Iterable[Any]) -> tuple[int, int]:
        imported = 0
        duplicates = 0
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(candles)")}
        trade_col = "trade_count" if "trade_count" in columns else "trades"
        for candle in candles:
            trade_count = getattr(candle, "trade_count", None)
            if trade_count is None:
                trade_count = getattr(candle, "trades", None)
            cursor = self.connection.execute(
                f"""INSERT OR IGNORE INTO candles
                (source, symbol, interval, open_time, close_time, open, high, low, close,
                 volume, quote_volume, {trade_col}, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    candle.source, candle.symbol, candle.interval, candle.open_time, candle.close_time,
                    candle.open, candle.high, candle.low, candle.close, candle.volume,
                    candle.quote_volume, trade_count, SCHEMA_VERSION,
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

    def save_spreads(self, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
        imported = 0
        duplicates = 0
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(spread_snapshots)")}
        sight_schema = "sight_source" in columns
        for row in rows:
            reason = row.get("reason") or "missing_reference"
            quiet = bool(row.get("quiet"))
            if reason == "ok":
                gate = "open"
            elif reason == "gap":
                gate = "quiet"
            else:
                gate = "unknown"
            if sight_schema:
                cursor = self.connection.execute(
                    """INSERT INTO spread_snapshots
                       (timestamp, symbol, sight_source, sight_price, truth_source, truth_price,
                        abs_gap, gap_bps, threshold_bps, gate, schema_version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(timestamp, symbol, sight_source, truth_source) DO UPDATE SET
                       sight_price=excluded.sight_price, truth_price=excluded.truth_price,
                       abs_gap=excluded.abs_gap, gap_bps=excluded.gap_bps,
                       threshold_bps=excluded.threshold_bps, gate=excluded.gate""",
                    (
                        row["timestamp"], row["symbol"],
                        row.get("underlying_source") or "binance",
                        row.get("underlying_price"),
                        row.get("reference_source") or "cfbenchmarks",
                        row.get("reference_price"),
                        row.get("spread_abs"), row.get("spread_bps"),
                        row["threshold_bps"], gate, RESEARCH_SCHEMA,
                    ),
                )
            else:
                cursor = self.connection.execute(
                    """INSERT OR REPLACE INTO spread_snapshots
                    (timestamp, symbol, interval, underlying_source, underlying_price,
                     reference_source, reference_price, spread_abs, spread_bps, threshold_bps,
                     quiet, reason, schema_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["timestamp"], row["symbol"], row["interval"], row["underlying_source"],
                        row.get("underlying_price"), row.get("reference_source") or "",
                        row.get("reference_price"), row.get("spread_abs"), row.get("spread_bps"),
                        row["threshold_bps"], int(quiet), reason, RESEARCH_SCHEMA,
                    ),
                )
            if cursor.rowcount:
                imported += 1
            else:
                duplicates += 1
        self.connection.commit()
        return imported, duplicates

    def save_technical_features(self, rows: Iterable[dict[str, Any]]) -> int:
        written = 0
        for row in rows:
            self.connection.execute(
                """INSERT OR REPLACE INTO technical_features
                (source, symbol, interval, timestamp, ema_9, ema_21, ema_50, rsi, macd,
                 macd_signal, macd_hist, atr, vwap, volume, volume_change, volatility,
                 trend_state, market_structure, swing_high, swing_low, candle_pattern, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["source"], row["symbol"], row["interval"], row["timestamp"],
                    row.get("ema_9"), row.get("ema_21"), row.get("ema_50"), row.get("rsi"),
                    row.get("macd"), row.get("macd_signal"), row.get("macd_hist"), row.get("atr"),
                    row.get("vwap"), row.get("volume"), row.get("volume_change"), row.get("volatility"),
                    row.get("trend_state"), row.get("market_structure"), row.get("swing_high"),
                    row.get("swing_low"), row.get("candle_pattern"), RESEARCH_SCHEMA,
                ),
            )
            written += 1
        self.connection.commit()
        return written

    def save_fibonacci_features(self, rows: Iterable[dict[str, Any]]) -> int:
        written = 0
        for row in rows:
            self.connection.execute(
                """INSERT OR REPLACE INTO fibonacci_features
                (source, symbol, interval, timestamp, swing_high, swing_high_time, swing_low,
                 swing_low_time, direction, fib_236, fib_382, fib_50, fib_618, fib_786,
                 ext_1272, ext_1618, nearest_level, distance_to_nearest, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["source"], row["symbol"], row["interval"], row["timestamp"],
                    row.get("swing_high"), row.get("swing_high_time"), row.get("swing_low"),
                    row.get("swing_low_time"), row.get("direction"), row.get("fib_236"),
                    row.get("fib_382"), row.get("fib_50"), row.get("fib_618"), row.get("fib_786"),
                    row.get("ext_1272"), row.get("ext_1618"), row.get("nearest_level"),
                    row.get("distance_to_nearest"), RESEARCH_SCHEMA,
                ),
            )
            written += 1
        self.connection.commit()
        return written

    def save_reconstructions(self, rows: Iterable[dict[str, Any]]) -> int:
        written = 0
        for row in rows:
            self.connection.execute(
                """INSERT OR REPLACE INTO trade_reconstructions
                (trade_id, offset, timestamp, contract, target, expiration, btc_price,
                 distance_to_target, time_to_expiration_seconds, rsi, macd, atr, ema_9,
                 ema_21, ema_50, vwap, volume, volatility, trend_state, market_structure,
                 fib_236, fib_382, fib_50, fib_618, fib_786, kalshi_yes_price, kalshi_no_price,
                 implied_probability, quiet, spread_bps, usable_at_entry, final_result,
                 source, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["trade_id"], row["offset"], row["timestamp"], row.get("contract"),
                    row.get("target"), row.get("expiration"), row.get("btc_price"),
                    row.get("distance_to_target"), row.get("time_to_expiration_seconds"),
                    row.get("rsi"), row.get("macd"), row.get("atr"), row.get("ema_9"),
                    row.get("ema_21"), row.get("ema_50"), row.get("vwap"), row.get("volume"),
                    row.get("volatility"), row.get("trend_state"), row.get("market_structure"),
                    row.get("fib_236"), row.get("fib_382"), row.get("fib_50"), row.get("fib_618"),
                    row.get("fib_786"), row.get("kalshi_yes_price"), row.get("kalshi_no_price"),
                    row.get("implied_probability"), row.get("quiet"), row.get("spread_bps"),
                    int(bool(row.get("usable_at_entry"))), row.get("final_result"),
                    row.get("source") or "reconstruction", RESEARCH_SCHEMA,
                ),
            )
            written += 1
        self.connection.commit()
        return written

    def load_candles(self, source: str, symbol: str, interval: str, end_time: str | None = None) -> list[sqlite3.Row]:
        if end_time:
            return list(
                self.connection.execute(
                    """SELECT * FROM candles WHERE source=? AND symbol=? AND interval=? AND close_time<=?
                       ORDER BY open_time""",
                    (source, symbol, interval, end_time),
                )
            )
        return list(
            self.connection.execute(
                """SELECT * FROM candles WHERE source=? AND symbol=? AND interval=? ORDER BY open_time""",
                (source, symbol, interval),
            )
        )

    def status(self) -> dict[str, Any]:
        def count(table: str) -> int:
            try:
                return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                return 0

        bounds = self.connection.execute("SELECT MIN(timestamp), MAX(timestamp) FROM market_observations").fetchone()
        last = self.connection.execute("SELECT finished_at FROM import_log ORDER BY id DESC LIMIT 1").fetchone()
        candle_bounds = self.connection.execute("SELECT MIN(open_time), MAX(close_time) FROM candles").fetchone()
        spread_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(spread_snapshots)")}
        last_spread = None
        quiet_open = 0
        gates = []
        try:
            if "gate" in spread_columns:
                last_spread = self.connection.execute(
                    "SELECT timestamp, gate, gap_bps AS spread_bps FROM spread_snapshots ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
                gates = self.connection.execute("SELECT gate, COUNT(*) FROM spread_snapshots GROUP BY gate").fetchall()
                quiet_open = self.connection.execute(
                    "SELECT COUNT(*) FROM spread_snapshots WHERE gate IN ('quiet', 'unknown')"
                ).fetchone()[0]
            else:
                last_spread = self.connection.execute(
                    "SELECT timestamp, quiet, reason, spread_bps FROM spread_snapshots ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
                quiet_open = self.connection.execute("SELECT COUNT(*) FROM spread_snapshots WHERE quiet=1").fetchone()[0]
        except sqlite3.Error:
            last_spread = None
        pairs: dict[str, Any] = {}
        try:
            for row in self.connection.execute(
                """SELECT symbol, COUNT(*) AS candles, MIN(open_time) AS start, MAX(close_time) AS end
                   FROM candles GROUP BY symbol"""
            ):
                if "gate" in spread_columns:
                    gate_row = self.connection.execute(
                        """SELECT timestamp, gate, gap_bps AS spread_bps FROM spread_snapshots
                           WHERE symbol=? ORDER BY timestamp DESC LIMIT 1""",
                        (row["symbol"],),
                    ).fetchone()
                    mapped = None
                    if gate_row:
                        mapped = {
                            "timestamp": gate_row["timestamp"],
                            "quiet": gate_row["gate"] != "open",
                            "reason": "missing_reference" if gate_row["gate"] == "unknown" else ("gap" if gate_row["gate"] == "quiet" else "ok"),
                            "spread_bps": gate_row["spread_bps"],
                        }
                else:
                    gate_row = self.connection.execute(
                        """SELECT timestamp, quiet, reason, spread_bps FROM spread_snapshots
                           WHERE symbol=? ORDER BY timestamp DESC LIMIT 1""",
                        (row["symbol"],),
                    ).fetchone()
                    mapped = (
                        {
                            "timestamp": gate_row["timestamp"],
                            "quiet": bool(gate_row["quiet"]),
                            "reason": gate_row["reason"],
                            "spread_bps": gate_row["spread_bps"],
                        }
                        if gate_row
                        else None
                    )
                tech = self.connection.execute(
                    "SELECT COUNT(*) FROM technical_features WHERE symbol=?",
                    (row["symbol"],),
                ).fetchone()[0]
                fib = self.connection.execute(
                    "SELECT COUNT(*) FROM fibonacci_features WHERE symbol=?",
                    (row["symbol"],),
                ).fetchone()[0]
                pairs[row["symbol"]] = {
                    "candles": row["candles"],
                    "candle_start": row["start"],
                    "candle_end": row["end"],
                    "technical_features": tech,
                    "fibonacci_features": fib,
                    "gate": mapped or {"quiet": True, "reason": "missing_reference", "spread_bps": None, "timestamp": None},
                }
        except sqlite3.Error:
            pairs = {}
        mapped_last = None
        if last_spread:
            if "gate" in last_spread.keys():
                mapped_last = {
                    "timestamp": last_spread["timestamp"],
                    "quiet": last_spread["gate"] != "open",
                    "reason": "missing_reference" if last_spread["gate"] == "unknown" else ("gap" if last_spread["gate"] == "quiet" else "ok"),
                    "spread_bps": last_spread["spread_bps"],
                }
            else:
                mapped_last = {
                    "timestamp": last_spread["timestamp"],
                    "quiet": bool(last_spread["quiet"]),
                    "reason": last_spread["reason"],
                    "spread_bps": last_spread["spread_bps"],
                }
        return {
            "markets": count("markets"),
            "observations": count("market_observations"),
            "results": count("market_results"),
            "candles": count("candles"),
            "truth_ticks": count("truth_ticks"),
            "spread_snapshots": count("spread_snapshots"),
            "spreads": count("spread_snapshots"),
            "spread_gates": {row[0]: row[1] for row in gates},
            "technical_features": count("technical_features"),
            "fibonacci_features": count("fibonacci_features"),
            "reconstructions": count("trade_reconstructions"),
            "quiet_spreads": quiet_open,
            "earliest_timestamp": bounds[0],
            "latest_timestamp": bounds[1],
            "earliest_candle": candle_bounds[0],
            "latest_candle": candle_bounds[1],
            "candle_start": candle_bounds[0],
            "candle_end": candle_bounds[1],
            "pairs": pairs,
            "last_import": last[0] if last else None,
            "gate": mapped_last or {"quiet": True, "reason": "missing_reference", "spread_bps": None, "timestamp": None},
        }

    def close(self) -> None:
        self.connection.close()
