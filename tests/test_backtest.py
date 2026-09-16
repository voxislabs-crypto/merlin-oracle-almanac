import math
import unittest

from oracle.backtest import BacktestRow, load_rows, run_backtest


def row(ticker, settlement_time, outcome, market_probability, sky_signal, timestamp):
    return BacktestRow(
        ticker=ticker,
        timestamp=timestamp,
        settlement_time=settlement_time,
        outcome=outcome,
        market_probability=market_probability,
        entry_price_cents=market_probability * 100,
        spread_cents=2.0,
        sky_signal=sky_signal,
        sky_orb=1.0,
        applying=1.0,
        volume=20.0,
    )


class BacktestTests(unittest.TestCase):
    def test_backtest_uses_settlement_cutoff_and_returns_metrics(self):
        rows = [
            row("TRAIN-YES", "2025-01-02T00:00:00+00:00", 1, 0.70, 80, "2025-01-01T00:00:00+00:00"),
            row("TRAIN-NO", "2025-01-03T00:00:00+00:00", 0, 0.30, 20, "2025-01-01T00:00:00+00:00"),
            row("TEST-YES", "2025-02-02T00:00:00+00:00", 1, 0.45, 90, "2025-02-01T00:00:00+00:00"),
            row("TEST-NO", "2025-02-03T00:00:00+00:00", 0, 0.55, 10, "2025-02-01T00:00:00+00:00"),
        ]

        report = run_backtest(rows, "2025-01-31T00:00:00Z", min_edge=0.0)

        self.assertEqual(report["training_observations"], 2)
        self.assertEqual(report["test_observations"], 2)
        self.assertEqual(len(report["predictions"]), 2)
        self.assertTrue(math.isfinite(report["model_brier"]))
        self.assertGreaterEqual(report["trades"], 0)

    def test_edge_threshold_and_fees_control_paper_trades(self):
        rows = [
            row("TRAIN-YES", "2025-01-02T00:00:00+00:00", 1, 0.70, 80, "2025-01-01T00:00:00+00:00"),
            row("TRAIN-NO", "2025-01-03T00:00:00+00:00", 0, 0.30, 20, "2025-01-01T00:00:00+00:00"),
            row("TEST-YES", "2025-02-02T00:00:00+00:00", 1, 0.20, 95, "2025-02-01T00:00:00+00:00"),
        ]

        no_trades = run_backtest(rows, "2025-01-31T00:00:00Z", min_edge=1.0)
        with_trades = run_backtest(rows, "2025-01-31T00:00:00Z", min_edge=0.0, fee_cents=5.0)

        self.assertEqual(no_trades["trades"], 0)
        self.assertEqual(with_trades["trades"], 1)
        self.assertLess(with_trades["paper_profit_cents_per_contract"], 80)

    def test_load_rows_joins_settlement_and_skips_unknown_outcomes(self):
        import sqlite3

        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE market_observations (
                ticker TEXT, timestamp TEXT, yes_price REAL, yes_bid REAL, yes_ask REAL,
                sky_signal REAL, sky_orb REAL, sky_direction TEXT, volume REAL
            );
            CREATE TABLE market_results (ticker TEXT, settlement_time TEXT, outcome TEXT);
            CREATE TABLE markets (ticker TEXT, category TEXT);
            INSERT INTO market_observations VALUES ('A', '2025-01-01T00:00:00+00:00', 40, 39, 41, 70, 2, 'applying', 10);
            INSERT INTO market_observations VALUES ('B', '2025-01-01T00:00:00+00:00', 40, 39, 41, 70, 2, 'applying', 10);
            INSERT INTO market_results VALUES ('A', '2025-01-02T00:00:00+00:00', 'yes');
            INSERT INTO market_results VALUES ('B', '2025-01-02T00:00:00+00:00', 'void');
            INSERT INTO markets VALUES ('A', 'economics');
            INSERT INTO markets VALUES ('B', 'politics');
            """
        )

        rows = load_rows(connection)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].outcome, 1)
        self.assertEqual(rows[0].entry_price_cents, 41)
        self.assertEqual(rows[0].category, "economics")


if __name__ == "__main__":
    unittest.main()