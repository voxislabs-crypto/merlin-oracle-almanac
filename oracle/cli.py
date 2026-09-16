import argparse
import json

from .kalshi import KalshiDatabase, KalshiImporter
from .kalshi.client import KalshiClient


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
    commands.add_parser("status")
    commands.add_parser("database")
    args = parser.parse_args()
    database = KalshiDatabase(args.database)
    try:
        if args.command == "markets":
            payload = list(KalshiClient().all_markets(category=args.category)) if args.all_markets else KalshiClient().markets(category=args.category)
            print(json.dumps(payload, indent=2))
        elif args.command == "import":
            print(json.dumps(KalshiImporter(database).import_market(args.ticker, args.start_ts, args.end_ts), indent=2))
        else:
            print(json.dumps(database.status(), indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()