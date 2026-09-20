# merlin-oracle-almanac
Merlin Oracle: A private offline almanac machine for exploring astronomical/astrological timing patterns and their correlation with real-world events and historical market behavior.

## Kalshi Data Vault

The read-only ingestion layer lives in `oracle/kalshi`. It stores raw API payloads alongside normalized SQLite records and never implements account access, orders, or trading.

## Binance sight feed and spread gate

Kalshi is settlement truth. For BTC that truth is CF Benchmarks BRTI, not Binance spot. Binance is the live chart.

```bash
python oracle.py binance --symbol BTCUSDT --interval 1m --database data/kalshi.db
python oracle.py truth-tick --source brti --symbol BTCUSDT --timestamp 2026-09-20T12:00:00Z --price 97500 --database data/kalshi.db
python oracle.py spread-scan --threshold-bps 25 --database data/kalshi.db
python oracle.py status --database data/kalshi.db
```

Without a truth tick the gate stays `unknown` and live signals stay quiet. Fibonacci comes after this alignment, not before.

## Run The Oracle

```bash
npm run dev
python oracle.py import MARKET_TICKER --database data/kalshi.db
python oracle.py status --database data/kalshi.db
```

The importer does not place orders, access accounts, or modify Kalshi data.

## Calibrated backtesting

```bash
python oracle.py backtest --database data/kalshi.db --cutoff 2025-01-01T00:00:00Z --min-edge 0.05 --fee-cents 1.0 --max-fraction 0.02
```
