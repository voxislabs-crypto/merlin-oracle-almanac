from datetime import datetime, timedelta, timezone
from typing import Any

from ..kalshi.database import KalshiDatabase
from ..kalshi.models import utc_timestamp
from .features import compute_feature_rows


OFFSETS = (
    ("T-60", timedelta(minutes=-60)),
    ("T-30", timedelta(minutes=-30)),
    ("T-15", timedelta(minutes=-15)),
    ("T-10", timedelta(minutes=-10)),
    ("T-5", timedelta(minutes=-5)),
    ("T-1", timedelta(minutes=-1)),
    ("T", timedelta(0)),
    ("T+1", timedelta(minutes=1)),
    ("T+5", timedelta(minutes=5)),
    ("T+15", timedelta(minutes=15)),
)


def _parse(timestamp: str) -> datetime:
    normalized = utc_timestamp(timestamp)
    if not normalized:
        raise ValueError("timestamp is required")
    return datetime.fromisoformat(normalized)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _lookup(rows: list[dict[str, Any]], timestamp: str) -> dict[str, Any] | None:
    chosen = None
    for row in rows:
        if row["timestamp"] <= timestamp:
            chosen = row
        else:
            break
    return chosen


def _observation(database: KalshiDatabase, contract: str | None, timestamp: str) -> dict[str, Any] | None:
    if not contract:
        return None
    row = database.connection.execute(
        """SELECT timestamp, yes_price, no_price FROM market_observations
           WHERE ticker=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1""",
        (contract, timestamp),
    ).fetchone()
    return dict(row) if row else None


def _settlement(database: KalshiDatabase, contract: str | None) -> dict[str, Any] | None:
    if not contract:
        return None
    row = database.connection.execute(
        "SELECT outcome, settlement_time FROM market_results WHERE ticker=?",
        (contract,),
    ).fetchone()
    return dict(row) if row else None


def _spread(database: KalshiDatabase, symbol: str, interval: str, timestamp: str) -> dict[str, Any] | None:
    row = database.connection.execute(
        """SELECT * FROM spread_snapshots
           WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1""",
        (symbol, timestamp),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    if "gate" in data:
        gate = data.get("gate")
        return {
            "quiet": gate != "open",
            "spread_bps": data.get("gap_bps") if data.get("gap_bps") is not None else data.get("spread_bps"),
            "reason": "missing_reference" if gate == "unknown" else ("gap" if gate == "quiet" else "ok"),
        }
    return data


def reconstruct_trade(
    database: KalshiDatabase,
    timestamp: str,
    contract: str | None = None,
    target: float | None = None,
    expiration: str | None = None,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    source: str = "binance",
    trade_id: str | None = None,
) -> dict[str, Any]:
    entry = _parse(timestamp)
    entry_iso = _iso(entry)
    trade_id = trade_id or f"public:{contract or symbol}:{entry_iso}"
    candles = [dict(row) for row in database.load_candles(source, symbol, interval)]
    if not candles:
        raise ValueError(f"No {source} {symbol} {interval} candles in the vault")
    technical_all, fib_all = compute_feature_rows(candles, source, symbol, interval)
    settlement = _settlement(database, contract)
    snapshots = []
    for name, delta in OFFSETS:
        moment = entry + delta
        moment_iso = _iso(moment)
        tech = _lookup(technical_all, moment_iso)
        fib = _lookup(fib_all, moment_iso)
        price = tech.get("vwap") if tech else None
        # Prefer the last completed candle close at or before this moment.
        candle = None
        for row in candles:
            if row["close_time"] <= moment_iso:
                candle = row
            else:
                break
        btc_price = float(candle["close"]) if candle else None
        observation = _observation(database, contract, moment_iso)
        spread = _spread(database, symbol, interval, moment_iso)
        yes = observation["yes_price"] if observation else None
        implied = (yes / 100.0) if yes is not None else None
        distance = (btc_price - target) if btc_price is not None and target is not None else None
        remaining = None
        if expiration:
            remaining = int((_parse(expiration) - moment).total_seconds())
        usable = delta.total_seconds() <= 0
        snapshots.append(
            {
                "trade_id": trade_id,
                "offset": name,
                "timestamp": moment_iso,
                "contract": contract,
                "target": target,
                "expiration": utc_timestamp(expiration) if expiration else None,
                "btc_price": btc_price,
                "distance_to_target": distance,
                "time_to_expiration_seconds": remaining,
                "rsi": tech.get("rsi") if tech else None,
                "macd": tech.get("macd") if tech else None,
                "atr": tech.get("atr") if tech else None,
                "ema_9": tech.get("ema_9") if tech else None,
                "ema_21": tech.get("ema_21") if tech else None,
                "ema_50": tech.get("ema_50") if tech else None,
                "vwap": price,
                "volume": tech.get("volume") if tech else None,
                "volatility": tech.get("volatility") if tech else None,
                "trend_state": tech.get("trend_state") if tech else None,
                "market_structure": tech.get("market_structure") if tech else None,
                "fib_236": fib.get("fib_236") if fib else None,
                "fib_382": fib.get("fib_382") if fib else None,
                "fib_50": fib.get("fib_50") if fib else None,
                "fib_618": fib.get("fib_618") if fib else None,
                "fib_786": fib.get("fib_786") if fib else None,
                "kalshi_yes_price": yes,
                "kalshi_no_price": observation["no_price"] if observation else None,
                "implied_probability": implied,
                "quiet": None if not spread else bool(spread["quiet"]),
                "spread_bps": None if not spread else spread["spread_bps"],
                "usable_at_entry": usable,
                "final_result": None,
                "source": source,
            }
        )
    if settlement and settlement.get("settlement_time"):
        settle_time = utc_timestamp(settlement["settlement_time"])
        snapshots.append(
            {
                **{key: None for key in snapshots[-1]},
                "trade_id": trade_id,
                "offset": "SETTLEMENT",
                "timestamp": settle_time,
                "contract": contract,
                "target": target,
                "expiration": utc_timestamp(expiration) if expiration else settle_time,
                "usable_at_entry": False,
                "final_result": settlement.get("outcome"),
                "source": source,
            }
        )
    written = database.save_reconstructions(snapshots)
    entry_row = next(row for row in snapshots if row["offset"] == "T")
    return {
        "trade_id": trade_id,
        "snapshots_written": written,
        "entry": entry_row,
        "dossier": format_dossier(entry_row, snapshots, symbol),
        "offsets": [row["offset"] for row in snapshots],
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def format_dossier(entry: dict[str, Any], snapshots: list[dict[str, Any]], symbol: str = "BTCUSDT") -> str:
    quiet = entry.get("quiet")
    gate = "QUIET" if quiet else "OPEN" if quiet is False else "UNCOMPARED"
    upper = symbol.upper()
    asset = "ETH" if upper.startswith("ETH") else "BTC" if upper.startswith("BTC") else symbol
    return (
        f"OBSERVATION: At {entry['timestamp']}, {asset} was trading at {_fmt(entry.get('btc_price'))}.\n"
        f"CALCULATION: Distance to target {_fmt(entry.get('target'))} was {_fmt(entry.get('distance_to_target'))}. "
        f"Time to expiration {_fmt(entry.get('time_to_expiration_seconds'), 0)} seconds.\n"
        f"CALCULATION: RSI {_fmt(entry.get('rsi'))}; ATR {_fmt(entry.get('atr'))}; MACD {_fmt(entry.get('macd'))}; "
        f"VWAP {_fmt(entry.get('vwap'))}; volume {_fmt(entry.get('volume'), 4)}.\n"
        f"CALCULATION: Fibonacci 61.8 was {_fmt(entry.get('fib_618'))}. Trend {entry.get('trend_state') or '—'} / {entry.get('market_structure') or '—'}.\n"
        f"OBSERVATION: Kalshi YES {_fmt(entry.get('kalshi_yes_price'))}; implied probability {_fmt(entry.get('implied_probability'), 4)}.\n"
        f"HYPOTHESIS: Spread gate {gate} (bps {_fmt(entry.get('spread_bps'))}). This is not a trading instruction.\n"
        f"EXPERIMENTAL SIGNAL: Merlin features are not mixed into this snapshot.\n"
        f"ACTUAL RESULT: reserved for SETTLEMENT offset; not used at T. "
        f"Offsets stored: {', '.join(row['offset'] for row in snapshots)}."
    )
