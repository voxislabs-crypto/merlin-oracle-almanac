# merlin-oracle-almanac
Merlin Oracle: A private offline almanac machine for exploring astronomical/astrological timing patterns and their correlation with real-world events and historical market behavior.

## Kalshi Data Vault

The read-only ingestion layer lives in `oracle/kalshi`. It stores raw API payloads alongside normalized SQLite records and never implements account access, orders, or trading.

## Run The Oracle

```bash
npm run dev
```

Then open http://localhost:8000. Set another port with `PORT=3000 npm run dev`.

The frontend is served locally by a small npm server and works offline after dependencies are installed. The Python Kalshi importer remains separate from the npm app.
```bash
python oracle.py markets
python oracle.py import MARKET_TICKER --database data/kalshi.db
python oracle.py status --database data/kalshi.db
python oracle.py database --database data/kalshi.db
```

The public API base URL is isolated in `oracle/kalshi/client.py` so the current official Kalshi endpoint can be verified or replaced without changing the database/importer boundary. Historical timestamps are normalized to UTC, observations are unique by `(ticker, timestamp)`, and each import is logged. The browser's **Kalshi Data Vault** screen is a local status/import companion; it does not execute Python or connect to trading functionality.

When served with `npm run dev`, the app exposes read-only local endpoints at `/api/vault/status` and `/api/vault/observations`. These read `data/kalshi.db` through Node's built-in SQLite support; no cloud service is required. The trainer and Crowd / Sky Divergence views calculate descriptive metrics from imported observations when available and otherwise use clearly labeled demonstration data.

For an installable CLI, use the package entry point:

```bash
python -m pip install -e .
oracle kalshi status
```

The importer does not place orders, access accounts, or modify Kalshi data.

## Calibrated backtesting

Once the database contains settled markets, run a time-split, read-only paper backtest:

```bash
python oracle.py backtest --database data/kalshi.db --cutoff 2025-01-01T00:00:00Z \
	--min-edge 0.05 --fee-cents 1.0 --max-fraction 0.02
```

The cutoff divides markets by settlement time, so the model only trains on outcomes that would have been known before the test set. The report compares market and model Brier scores, log loss, calibration error, paper profit after the supplied per-contract fee, maximum drawdown, and capped Kelly fractions. It uses executable yes asks when available and never places orders. A positive historical result is not evidence of future profitability; use an untouched later period and the exchange's current fee schedule before risking capital.

## Experimental Astronomy

Each imported observation now receives a deterministic local astronomy record and a `TimeTrak_Experimental_Astronomy_v0` result. The current calculator uses mean orbital periods and approximate J2000 longitudes for reproducible research inputs. It is intentionally low precision, is not the historical Merlin algorithm, and must not be treated as a verified ephemeris or predictive model.

Stored fields include the astronomy version, TimeTrak version, Saturn/Pluto aspect, orb, applying/separating direction, signal intensity, onset, peak, and duration. A verified ephemeris library or source dataset can replace `oracle/astronomy.py` later without changing the importer/database contract.

When the npm server is running, `/api/astronomy` and `/api/vault/observations` use the separate Oracle adapter at `oracle/swiss-ephemeris.mjs`. It follows the production Merlin engine's Swiss Ephemeris `calc_ut` boundary but does not import production Merlin code. The adapter is pinned to the `sweph` package version used by the referenced Merlin repository.
