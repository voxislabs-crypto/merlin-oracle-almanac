import tempfile
import unittest
import hashlib
from pathlib import Path

from oracle.kalshi.database import KalshiDatabase
from oracle.kalshi.importer import KalshiImporter
from oracle.astronomy import ASTRONOMY_VERSION, calculate_state
from oracle.timetrak import TIMETRAK_VERSION, calculate_signal


class FakeClient:
    def market(self, ticker):
        return {"market": {"ticker": ticker, "title": "Test market", "created_time": "2025-01-01T00:00:00Z", "status": "closed", "result": "yes"}}

    def candlesticks(self, ticker, start_ts=None, end_ts=None):
        return {"candlesticks": [{"end_period_ts": 1735689660, "yes_price": 42, "no_price": 58, "volume": 12}, {"end_period_ts": 1735689660, "yes_price": 42, "no_price": 58, "volume": 12}]}


class KalshiImportTests(unittest.TestCase):
    def test_approximate_astronomy_is_deterministic_and_versioned(self):
        first = calculate_state("2000-01-01T12:00:00Z")
        second = calculate_state("2000-01-01T12:00:00Z")
        signal = calculate_signal("2025-01-01T00:00:00Z")
        self.assertEqual(first.positions, second.positions)
        self.assertEqual(first.version, ASTRONOMY_VERSION)
        self.assertEqual(signal.calculation_version, TIMETRAK_VERSION)
        self.assertGreaterEqual(signal.intensity, 0)
        self.assertLessEqual(signal.intensity, 100)

    def test_import_is_idempotent_and_keeps_utc_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "kalshi.db")
            importer = KalshiImporter(database, FakeClient())
            first = importer.import_market("TEST-1")
            second = importer.import_market("TEST-1")
            status = database.status()
            self.assertEqual(first["records_imported"], 1)
            self.assertEqual(second["records_imported"], 0)
            self.assertEqual(second["duplicates_skipped"], 2)
            self.assertEqual(status["observations"], 1)
            self.assertTrue(status["earliest_timestamp"].endswith("+00:00"))
            sky = database.connection.execute("SELECT sky_signal, sky_aspect, astronomy_version, timetrak_version FROM market_observations").fetchone()
            self.assertIsNotNone(sky[0])
            self.assertIn("Saturn", sky[1])
            self.assertTrue(sky[2])
            self.assertTrue(sky[3])
            raw = database.connection.execute("SELECT payload_sha256, payload FROM raw_api_responses ORDER BY id LIMIT 1").fetchone()
            self.assertEqual(raw[0], hashlib.sha256(raw[1].encode()).hexdigest())
            database.close()


if __name__ == "__main__":
    unittest.main()