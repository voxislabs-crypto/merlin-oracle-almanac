import tempfile
import unittest
from pathlib import Path

from oracle.binance.align import scan_spreads
from oracle.binance.importer import BinanceImporter
from oracle.binance.models import Candle
from oracle.kalshi.database import KalshiDatabase
from oracle.spread import decide_gate, gap_bps, snapshot_at


class FakeBinance:
    def klines(self, symbol="BTCUSDT", interval="1m", start_ms=None, end_ms=None, limit=1000):
        return [
            [1735689600000, "97000.0", "97100.0", "96900.0", "97050.0", "12.5", 1735689659999, "1213000.0", 88, "0", "0", "0"],
            [1735689660000, "97050.0", "97200.0", "97000.0", "97125.0", "8.0", 1735689719999, "777000.0", 40, "0", "0", "0"],
        ]


class BinanceAndGateTests(unittest.TestCase):
    def test_gate_unknown_without_truth(self):
        self.assertEqual(decide_gate(97000.0, None), "unknown")
        snap = snapshot_at("2025-01-01T00:00:00+00:00", "BTCUSDT", "binance", 97000.0, "brti", None)
        self.assertEqual(snap.gate, "unknown")
        self.assertIsNone(snap.gap_bps)

    def test_gate_quiet_when_gap_exceeds_threshold(self):
        self.assertGreater(gap_bps(97100.0, 97000.0), 10.0)
        self.assertEqual(decide_gate(97300.0, 97000.0, threshold_bps=25.0), "quiet")
        self.assertEqual(decide_gate(97010.0, 97000.0, threshold_bps=25.0), "open")

    def test_import_klines_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "kalshi.db")
            importer = BinanceImporter(database, FakeBinance())
            first = importer.import_klines()
            second = importer.import_klines()
            self.assertEqual(first["records_imported"], 2)
            self.assertEqual(second["records_imported"], 0)
            self.assertEqual(second["duplicates_skipped"], 2)
            status = database.status()
            self.assertEqual(status["candles"], 2)
            self.assertTrue(status["earliest_candle"].endswith("+00:00"))
            database.close()

    def test_spread_scan_stays_unknown_until_truth_tick(self):
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "kalshi.db")
            database.connection.execute(
                "INSERT INTO markets(ticker, schema_version) VALUES ('BTC-TEST', 'kalshi-v1')"
            )
            database.connection.execute(
                """INSERT INTO market_observations(ticker, timestamp, yes_price, schema_version)
                   VALUES ('BTC-TEST', '2025-01-01T00:01:12+00:00', 40, 'kalshi-v1')"""
            )
            database.connection.commit()
            BinanceImporter(database, FakeBinance()).import_klines()
            before = scan_spreads(database)
            self.assertEqual(before["unknown"], 1)
            self.assertEqual(before["open"], 0)
            database.save_truth_tick("brti", "BTCUSDT", "2025-01-01T00:01:00+00:00", 97125.0, "manual research tick")
            after = scan_spreads(database)
            row = database.connection.execute("SELECT gate, sight_price, truth_price FROM spread_snapshots").fetchone()
            self.assertEqual(after["unknown"], 0)
            self.assertEqual(row[0], "open")
            self.assertEqual(row[1], 97125.0)
            self.assertEqual(row[2], 97125.0)
            database.close()

    def test_candle_parse(self):
        candle = Candle.from_binance(
            [1735689600000, "1", "2", "0.5", "1.5", "10", 1735689659999, "15", 3, "0", "0", "0"],
            "btcusdt",
            "1m",
        )
        self.assertEqual(candle.source, "binance")
        self.assertEqual(candle.symbol, "BTCUSDT")
        self.assertEqual(candle.close, 1.5)


if __name__ == "__main__":
    unittest.main()
