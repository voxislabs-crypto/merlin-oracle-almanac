import argparse
import json

from .backtest import load_rows, run_backtest
from .binance import BinanceImporter
from .binance.align import scan_spreads
from .harvest import OracleHarvester, SourceRegistry
from .kalshi import KalshiDatabase, KalshiImporter
from .kalshi.client import KalshiClient
from .spread import DEFAULT_THRESHOLD_BPS


def main() -> None:
    parser = argparse.ArgumentParser(prog="oracle", description="Merlin Oracle read-only Kalshi data vault")
    parser.add_argument("--database", default="data/kalshi.db")
    commands = parser.add_subparsers(dest="command", required=True)
    markets = commands.add_parser("markets")
    markets.add_argument("--category")
    markets.add_argument("--all", action="store_true", dest="all_markets")
    import_command = commands.add_parser("import")
    import_command.add_argument("ticker")
    import_command.add_argument("--start-ts", type=int)
    import_command.add_argument("--end-ts", type=int)
    dossier = commands.add_parser("dossier")
    dossier.add_argument("question")
    dossier.add_argument("--source", action="append", default=[])
    backtest = commands.add_parser("backtest")
    backtest.add_argument("--cutoff", required=True, help="ISO timestamp separating training and test settlements")
    backtest.add_argument("--min-edge", type=float, default=0.05)
    backtest.add_argument("--fee-cents", type=float, default=0.0)
    backtest.add_argument("--max-fraction", type=float, default=0.02)
    binance = commands.add_parser("binance", help="Import public Binance klines into the vault")
    binance.add_argument("--symbol", default="BTCUSDT")
    binance.add_argument("--interval", default="1m")
    binance.add_argument("--start-ms", type=int)
    binance.add_argument("--end-ms", type=int)
    binance.add_argument("--limit", type=int, default=1000)
    truth = commands.add_parser("truth-tick", help="Record a settlement-index tick (e.g. BRTI) used as gate truth")
    truth.add_argument("--source", default="brti")
    truth.add_argument("--symbol", default="BTCUSDT")
    truth.add_argument("--timestamp", required=True)
    truth.add_argument("--price", type=float, required=True)
    truth.add_argument("--note")
    spread = commands.add_parser("spread-scan", help="Align Binance closes to Kalshi observation minutes and freeze the gate")
    spread.add_argument("--symbol", default="BTCUSDT")
    spread.add_argument("--interval", default="1m")
    spread.add_argument("--truth-source", default="brti")
    spread.add_argument("--threshold-bps", type=float, default=DEFAULT_THRESHOLD_BPS)
    commands.add_parser("status")
    commands.add_parser("database")
    commands.add_parser("sources")
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
        elif args.command == "backtest":
            print(json.dumps(run_backtest(load_rows(database.connection), args.cutoff, args.min_edge, args.fee_cents, args.max_fraction), indent=2))
        elif args.command == "binance":
            print(json.dumps(BinanceImporter(database).import_klines(args.symbol, args.interval, args.start_ms, args.end_ms, args.limit), indent=2))
        elif args.command == "truth-tick":
            database.save_truth_tick(args.source, args.symbol, args.timestamp, args.price, args.note)
            print(json.dumps({"saved": True, "source": args.source, "symbol": args.symbol, "timestamp": args.timestamp, "price": args.price}, indent=2))
        elif args.command == "spread-scan":
            print(json.dumps(scan_spreads(database, args.symbol, args.interval, args.truth_source, args.threshold_bps), indent=2))
        else:
            print(json.dumps(database.status(), indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()
