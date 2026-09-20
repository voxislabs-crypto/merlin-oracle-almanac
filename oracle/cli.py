import argparse
import json

from .backtest import load_rows, run_backtest
from .binance import BinanceImporter
from .binance.align import scan_spreads
from .crypto.importer import CandleImporter
from .crypto.index_import import IndexImporter
from .crypto.tape import TapeImporter
from .crypto.spread import DEFAULT_THRESHOLD_BPS as CRYPTO_THRESHOLD
from .harvest import OracleHarvester, SourceRegistry
from .kalshi import KalshiDatabase, KalshiImporter
from .kalshi.client import KalshiClient
from .kalshi.models import unix_seconds
from .research.features import compute_feature_rows
from .research.reconstruct import reconstruct_trade
from .spread import DEFAULT_THRESHOLD_BPS


def main() -> None:
    parser = argparse.ArgumentParser(prog="oracle", description="Merlin Oracle public-data research vault")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--database", default="data/kalshi.db")
    commands = parser.add_subparsers(dest="command", required=True)
    markets = commands.add_parser("markets", parents=[shared])
    markets.add_argument("--category")
    markets.add_argument("--all", action="store_true", dest="all_markets")
    import_command = commands.add_parser("import", parents=[shared])
    import_command.add_argument("ticker")
    import_command.add_argument("--start-ts", type=int)
    import_command.add_argument("--end-ts", type=int)
    dossier = commands.add_parser("dossier", parents=[shared])
    dossier.add_argument("question")
    dossier.add_argument("--source", action="append", default=[])
    candles = commands.add_parser("candles", parents=[shared], help="Import public Binance OHLCV")
    candles.add_argument("symbol", nargs="?", default="BTCUSDT")
    candles.add_argument("--interval", default="1m")
    candles.add_argument("--start", help="ISO UTC start")
    candles.add_argument("--end", help="ISO UTC end")
    candles.add_argument("--start-ts", type=int)
    candles.add_argument("--end-ts", type=int)
    candles.add_argument("--reference-source", default="cfbenchmarks")
    candles.add_argument("--threshold-bps", type=float, default=CRYPTO_THRESHOLD)
    index_command = commands.add_parser("index", parents=[shared], help="Import a public CF Benchmarks/BRTI index file")
    index_command.add_argument("path")
    index_command.add_argument("--symbol", default="BTCUSDT")
    index_command.add_argument("--interval", default="1m")
    index_command.add_argument("--source", default="cfbenchmarks")
    index_command.add_argument("--threshold-bps", type=float, default=CRYPTO_THRESHOLD)
    tape = commands.add_parser("tape", parents=[shared], help="Import Binance trade-tape zip/csv as candles")
    tape.add_argument("path")
    tape.add_argument("--symbol")
    tape.add_argument("--interval", default="1m")
    tape.add_argument("--threshold-bps", type=float, default=CRYPTO_THRESHOLD)
    features = commands.add_parser("features", parents=[shared], help="Recompute TA/Fibonacci from stored candles")
    features.add_argument("symbol", nargs="?", default="BTCUSDT")
    features.add_argument("--interval", default="1m")
    features.add_argument("--source", default="binance")
    reconstruct = commands.add_parser("reconstruct", parents=[shared], help="Freeze market state around an entry timestamp")
    reconstruct.add_argument("--timestamp", required=True)
    reconstruct.add_argument("--contract")
    reconstruct.add_argument("--target", type=float)
    reconstruct.add_argument("--expiration")
    reconstruct.add_argument("--symbol", default="BTCUSDT")
    reconstruct.add_argument("--interval", default="1m")
    reconstruct.add_argument("--trade-id")
    backtest = commands.add_parser("backtest", parents=[shared])
    backtest.add_argument("--cutoff", required=True, help="ISO timestamp separating training and test settlements")
    backtest.add_argument("--min-edge", type=float, default=0.05)
    backtest.add_argument("--fee-cents", type=float, default=0.0)
    backtest.add_argument("--max-fraction", type=float, default=0.02)
    binance = commands.add_parser("binance", parents=[shared], help="Import public Binance klines into the vault")
    binance.add_argument("--symbol", default="BTCUSDT")
    binance.add_argument("--interval", default="1m")
    binance.add_argument("--start-ms", type=int)
    binance.add_argument("--end-ms", type=int)
    binance.add_argument("--limit", type=int, default=1000)
    truth = commands.add_parser("truth-tick", parents=[shared], help="Record a settlement-index tick (e.g. BRTI) used as gate truth")
    truth.add_argument("--source", default="brti")
    truth.add_argument("--symbol", default="BTCUSDT")
    truth.add_argument("--timestamp", required=True)
    truth.add_argument("--price", type=float, required=True)
    truth.add_argument("--note")
    spread = commands.add_parser("spread-scan", parents=[shared], help="Align Binance closes to Kalshi observation minutes and freeze the gate")
    spread.add_argument("--symbol", default="BTCUSDT")
    spread.add_argument("--interval", default="1m")
    spread.add_argument("--truth-source", default="brti")
    spread.add_argument("--threshold-bps", type=float, default=DEFAULT_THRESHOLD_BPS)
    commands.add_parser("status", parents=[shared])
    commands.add_parser("database", parents=[shared])
    commands.add_parser("sources", parents=[shared])
    observations = commands.add_parser("observations", parents=[shared])
    observations.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    database = KalshiDatabase(args.database)
    try:
        if args.command == "markets":
            payload = list(KalshiClient().all_markets(category=args.category)) if args.all_markets else KalshiClient().markets(category=args.category)
            print(json.dumps(payload, indent=2))
        elif args.command == "import":
            print(json.dumps(KalshiImporter(database).import_market(args.ticker, args.start_ts, args.end_ts), indent=2))
        elif args.command == "dossier":
            dossier = OracleHarvester(database).create_dossier(args.question, args.source)
            print(json.dumps({"id": dossier.id, "question": dossier.question, "sources": dossier.sources}, indent=2))
        elif args.command == "sources":
            print(json.dumps([source.name for source in SourceRegistry.default_registry().sources], indent=2))
        elif args.command == "candles":
            start = args.start_ts or unix_seconds(args.start)
            end = args.end_ts or unix_seconds(args.end)
            print(json.dumps(
                CandleImporter(database).import_binance(
                    args.symbol,
                    args.interval,
                    start,
                    end,
                    args.reference_source,
                    args.threshold_bps,
                ),
                indent=2,
            ))
        elif args.command == "index":
            print(json.dumps(
                IndexImporter(database).import_file(
                    args.path,
                    symbol=args.symbol,
                    interval=args.interval,
                    source=args.source,
                    threshold_bps=args.threshold_bps,
                ),
                indent=2,
            ))
        elif args.command == "tape":
            print(json.dumps(
                TapeImporter(database).import_path(
                    args.path,
                    symbol=args.symbol,
                    interval=args.interval,
                    threshold_bps=args.threshold_bps,
                ),
                indent=2,
            ))
        elif args.command == "features":
            candles_rows = [dict(row) for row in database.load_candles(args.source, args.symbol.upper(), args.interval)]
            technical, fibonacci = compute_feature_rows(candles_rows, args.source, args.symbol.upper(), args.interval)
            print(json.dumps({
                "source": args.source,
                "symbol": args.symbol.upper(),
                "interval": args.interval,
                "candles": len(candles_rows),
                "technical_written": database.save_technical_features(technical),
                "fibonacci_written": database.save_fibonacci_features(fibonacci),
            }, indent=2))
        elif args.command == "reconstruct":
            print(json.dumps(
                reconstruct_trade(
                    database,
                    timestamp=args.timestamp,
                    contract=args.contract,
                    target=args.target,
                    expiration=args.expiration,
                    symbol=args.symbol,
                    interval=args.interval,
                    trade_id=args.trade_id,
                ),
                indent=2,
            ))
        elif args.command == "binance":
            print(json.dumps(BinanceImporter(database).import_klines(args.symbol, args.interval, args.start_ms, args.end_ms, args.limit), indent=2))
        elif args.command == "truth-tick":
            database.save_truth_tick(args.source, args.symbol, args.timestamp, args.price, args.note)
            print(json.dumps({"saved": True, "source": args.source, "symbol": args.symbol, "timestamp": args.timestamp, "price": args.price}, indent=2))
        elif args.command == "spread-scan":
            print(json.dumps(scan_spreads(database, args.symbol, args.interval, args.truth_source, args.threshold_bps), indent=2))
        elif args.command == "backtest":
            print(json.dumps(run_backtest(load_rows(database.connection), args.cutoff, args.min_edge, args.fee_cents, args.max_fraction), indent=2))
        elif args.command == "observations":
            limit = max(1, min(int(args.limit), 5000))
            rows = database.connection.execute(
                """SELECT ticker, timestamp, yes_price, no_price, yes_bid, yes_ask, volume,
                          open_interest, sky_signal, sky_aspect, sky_orb, sky_direction
                   FROM market_observations ORDER BY timestamp LIMIT ?""",
                (limit,),
            ).fetchall()
            print(json.dumps([dict(row) for row in rows]))
        else:
            print(json.dumps(database.status(), indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()
