import tempfile
import unittest
from pathlib import Path

from oracle.kalshi.database import KalshiDatabase
from oracle.kalshi.importer import KalshiImporter


class FakeClient:
    def market(self, ticker):
        return {"market": {"ticker": ticker, "title": "Test market", "created_time": "2025-01-01T00:00:00Z", "status": "closed", "result": "yes"}}

    def candlesticks(self, ticker, start_ts=None, end_ts=None):
        return {"candlesticks": [{"end_period_ts": 1735689660, "yes_price": 42, "no_price": 58, "volume": 12}, {"end_period_ts": 1735689660, "yes_price": 42, "no_price": 58, "volume": 12}]}


class KalshiImportTests(unittest.TestCase):
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
            database.close()


if __name__ == "__main__":
    unittest.main()