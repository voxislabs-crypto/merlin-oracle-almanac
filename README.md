# merlin-oracle-almanac
Merlin Oracle: A private offline almanac machine for exploring astronomical/astrological timing patterns and their correlation with real-world events and historical market behavior.

## Research engine charter

The Almanac is also a research/forensics system for **publicly observable** Kalshi trading behavior. It reconstructs the market state that was knowable at the moment of an observed entry. It does not obtain private account information, and it is not a trading bot.

The system prompt for that engine is `RESEARCH-ENGINE.md`. Hand that file to another AI or developer. The architecture map is `research-path.html`. In the local UI, open **Research engine**.

Standing rule: do not start from why a trade won. Reconstruct everything knowable at timestamp T. Kalshi is settlement truth. Binance is the live chart. The spread between them is the gate.

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

This notebook does not calculate the sky itself. Charts and TimeTraks are requested from a local Merlin engine.

1. In `X:\Merlin` (the Next.js app), start the engine:

```bash
cd X:\Merlin
npm run dev
```

Leave that process on http://localhost:3000. Development mode treats unsigned API callers as trial, which is enough for natal charts and transits.

2. In this repo, start the almanac:

```bash
npm run dev
```

Then open http://localhost:8000. Set another port with `PORT=8080 npm run dev` if 8000 is taken. Point at a different engine with `MERLIN_ENGINE_URL=http://127.0.0.1:3000`. Use `127.0.0.1` rather than `localhost` on Windows so the proxy does not stall on IPv6.

If Merlin is down, the sidebar reads **ENGINE DOWN** and creating a chart or asking for TimeTraks fails out loud. The instrument will not fall back to demonstration windows.

The frontend is served locally by a small npm server. `/api/engine/status`, `/api/engine/chart`, and `/api/engine/transits` proxy to Merlin so the browser never has to speak CORS or Clerk to the engine. Chart calculation uses Merlin's `landing-preview` path so it does not consume the product chart quota.

## Harvester

The **Harvester** screen is a data vacuum, not a Kalshi-only scraper. Browse public Kalshi series in the app, then press **IMPORT**. That button runs `python oracle.py import TICKER` on this machine and writes raw observations to `data/kalshi.db`. Interpretations (TimeTraks, trainer scores) stay separate so a later algorithm can replay the same world.

Open a contract's **DOSSIER** to see what is known so far: Kalshi price, a Polymarket search against the same question, and Merlin TimeTraks if a reference chart has been calculated. Metaculus, Manifold, FRED, NOAA, and news are registered as planned sources and stay blank until an adapter exists.

```bash
python oracle.py markets --category KXBTCY
python oracle.py import KXBTCMAXY-26DEC31-109999.99 --database data/kalshi.db
python oracle.py candles BTCUSDT --interval 1m --database data/kalshi.db
python oracle.py candles ETHUSDT --interval 1m --database data/kalshi.db
python oracle.py tape "Z:\Chart Data" --interval 1m
python oracle.py index path/to/brti.csv --symbol BTCUSDT --interval 1m
python oracle.py reconstruct --timestamp 2026-09-20T14:17:32Z --symbol BTCUSDT --target 68000
python oracle.py status --database data/kalshi.db
```

The source registry lives at `oracle/harvester/registry.json`. SQLite is the prototype store; DuckDB can replace the analytical layer later without mixing raw rows into interpretations.

The public API base URL is isolated in `oracle/kalshi/client.py` so the current official Kalshi endpoint can be verified or replaced without changing the database/importer boundary. Historical timestamps are normalized to UTC, observations are unique by `(ticker, timestamp)`, and each import is logged. The browser's **Kalshi Data Vault** screen is a local status/import companion; it does not execute Python or connect to trading functionality.

When served with `npm run dev`, the app exposes read-only local endpoints at `/api/vault/status` and `/api/vault/observations`. These read `data/kalshi.db` through Node's built-in SQLite support; no cloud service is required. The trainer and Crowd / Sky Divergence views calculate descriptive metrics from imported observations when available and otherwise use clearly labeled demonstration data.

For an installable CLI, use the package entry point:

```bash
python -m pip install -e .
oracle kalshi status
```

The importer does not place orders, access accounts, or modify Kalshi data.

## Calibrated backtesting

```bash
python oracle.py backtest --database data/kalshi.db --cutoff 2025-01-01T00:00:00Z --min-edge 0.05 --fee-cents 1.0 --max-fraction 0.02
```

The cutoff divides markets by settlement time, so the model only trains on outcomes that would have been known before the test set. The report compares market and model Brier scores, log loss, calibration error, paper profit after the supplied per-contract fee, maximum drawdown, and capped Kelly fractions. It uses executable yes asks when available and never places orders. A positive historical result is not evidence of future profitability; use an untouched later period and the exchange's current fee schedule before risking capital.

## Experimental Astronomy

Each imported observation now receives a deterministic local astronomy record and a `TimeTrak_Experimental_Astronomy_v0` result. The current calculator uses mean orbital periods and approximate J2000 longitudes for reproducible research inputs. It is intentionally low precision, is not the historical Merlin algorithm, and must not be treated as a verified ephemeris or predictive model.

Stored fields include the astronomy version, TimeTrak version, Saturn/Pluto aspect, orb, applying/separating direction, signal intensity, onset, peak, and duration. A verified ephemeris library or source dataset can replace `oracle/astronomy.py` later without changing the importer/database contract.

The Charts and TimeTraks screens call the running Merlin engine (`/api/calculate-birth-chart` and `/api/transits`) through this app's `/api/engine/*` proxy. `/api/astronomy` and `/api/vault/observations` still use the local adapter at `oracle/swiss-ephemeris.mjs` for imported Kalshi rows until those observations are stamped with Merlin windows.
