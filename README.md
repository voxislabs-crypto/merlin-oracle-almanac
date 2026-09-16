# merlin-oracle-almanac
Merlin Oracle: A private offline almanac machine for exploring astronomical/astrological timing patterns and their correlation with real-world events and historical market behavior.

## Kalshi Data Vault

The read-only ingestion layer lives in `oracle/kalshi`. It stores raw API payloads alongside normalized SQLite records and never implements account access, orders, or trading.

```bash
python oracle.py markets
python oracle.py import MARKET_TICKER --database data/kalshi.db
python oracle.py status --database data/kalshi.db
python oracle.py database --database data/kalshi.db
```

The public API base URL is isolated in `oracle/kalshi/client.py` so the current official Kalshi endpoint can be verified or replaced without changing the database/importer boundary. Historical timestamps are normalized to UTC, observations are unique by `(ticker, timestamp)`, and each import is logged. The browser's **Kalshi Data Vault** screen is a local status/import companion; it does not execute Python or connect to trading functionality.
