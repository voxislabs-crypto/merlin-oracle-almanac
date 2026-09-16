import tempfile
import unittest
from pathlib import Path

from oracle.harvest import SourceRegistry, OracleHarvester
from oracle.kalshi.database import KalshiDatabase


class HarvesterTests(unittest.TestCase):
    def test_default_registry_contains_external_sources(self):
        registry = SourceRegistry.default_registry()
        names = {source.name for source in registry.sources}
        self.assertIn("Kalshi", names)
        self.assertIn("Polymarket", names)
        self.assertIn("Metaculus", names)
        self.assertIn("FRED", names)

    def test_harvester_builds_dossier_with_raw_event_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "kalshi.db")
            harvester = OracleHarvester(database)
            dossier = harvester.create_dossier(
                question="Will the Fed cut rates?",
                sources=["Kalshi", "FRED"],
            )
            harvester.record_observation(
                dossier_id=dossier.id,
                source_name="Kalshi",
                market_ticker="FED-SEP",
                observed_at="2026-09-16T00:00:00Z",
                data_type="price",
                raw_value="0.73",
                normalized_value=0.73,
                url="https://api.kalshi.com/markets/FED-SEP",
            )
            harvester.record_observation(
                dossier_id=dossier.id,
                source_name="FRED",
                market_ticker="FEDFUNDS",
                observed_at="2026-09-16T00:00:00Z",
                data_type="series",
                raw_value="5.25",
                normalized_value=5.25,
                url="https://fred.stlouisfed.org/series/FEDFUNDS",
            )
            stored = database.connection.execute(
                "SELECT question FROM event_dossiers WHERE id = ?",
                (dossier.id,),
            ).fetchone()
            self.assertEqual(stored[0], "Will the Fed cut rates?")
            count = database.connection.execute(
                "SELECT COUNT(*) FROM raw_observations WHERE dossier_id = ?",
                (dossier.id,),
            ).fetchone()[0]
            self.assertEqual(count, 2)
            database.close()


if __name__ == "__main__":
    unittest.main()
