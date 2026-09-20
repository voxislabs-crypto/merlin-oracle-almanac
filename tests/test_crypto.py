import tempfile
import unittest
from pathlib import Path

from oracle.crypto.binance import kline_to_row
from oracle.crypto.importer import CandleImporter
from oracle.crypto.index_import import IndexImporter, parse_index_records
from oracle.crypto.tape import infer_symbol, trades_to_candles
from oracle.crypto.spread import bucket_time, evaluate_spread, build_spread_snapshots
from oracle.kalshi.database import KalshiDatabase
from oracle.research.features import compute_feature_rows
from oracle.research.fibonacci import fibonacci_from_swings
from oracle.research.reconstruct import reconstruct_trade
from oracle.research.swings import confirmed_swings, swings_known_at
from oracle.research.ta import ema, rsi


def kline(open_ms, close, high=None, low=None, volume=10):
    high = close if high is None else high
    low = close if low is None else low
    return [open_ms, str(close), str(high), str(low), str(close), str(volume), open_ms + 59_999, str(volume * close), 3, "0", "0", "0"]


class FakeBinance:
    def __init__(self, rows):
        self.rows = rows

    def iter_klines(self, symbol, interval, start_ts, end_ts):
        return list(self.rows)


class SpreadTests(unittest.TestCase):
    def test_missing_reference_is_quiet(self):
        verdict = evaluate_spread(68000.0, None, 25.0)
        self.assertTrue(verdict["quiet"])
        self.assertEqual(verdict["reason"], "missing_reference")
        self.assertIsNone(verdict["spread_bps"])

    def test_gap_beyond_threshold_is_quiet(self):
        verdict = evaluate_spread(68400.0, 68000.0, 25.0)
        self.assertTrue(verdict["quiet"])
        self.assertEqual(verdict["reason"], "gap")
        self.assertGreater(abs(verdict["spread_bps"]), 25.0)

    def test_tight_gap_is_open(self):
        verdict = evaluate_spread(68001.0, 68000.0, 25.0)
        self.assertFalse(verdict["quiet"])
        self.assertEqual(verdict["reason"], "ok")


class CandleImportTests(unittest.TestCase):
    def test_import_is_idempotent_and_utc(self):
        rows = [kline(1_700_000_000_000 + i * 60_000, 100 + i) for i in range(5)]
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "vault.db")
            importer = CandleImporter(database, FakeBinance(rows))
            first = importer.import_binance("btcusdt", "1m", 1_700_000_000, 1_700_000_400)
            second = importer.import_binance("btcusdt", "1m", 1_700_000_000, 1_700_000_400)
            self.assertEqual(first["records_imported"], 5)
            self.assertEqual(second["records_imported"], 0)
            self.assertEqual(second["duplicates_skipped"], 5)
            self.assertTrue(first["gate"]["quiet"])
            self.assertEqual(first["gate"]["reason"], "missing_reference")
            close_time = database.connection.execute("SELECT close_time FROM candles LIMIT 1").fetchone()[0]
            self.assertTrue(close_time.endswith("+00:00"))
            status = database.status()
            self.assertEqual(status["candles"], 5)
            self.assertTrue(status["gate"]["quiet"])
            database.close()

    def test_spread_aligns_on_close_time(self):
        binance = [{**kline_to_row("BTCUSDT", "1m", kline(1_700_000_000_000, 100)), "source": "binance"}]
        index = [{**kline_to_row("BTCUSDT", "1m", kline(1_700_000_000_000, 100.05)), "source": "cfbenchmarks"}]
        snapshots = build_spread_snapshots(binance + index, "BTCUSDT", "1m", threshold_bps=25.0)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["reason"], "ok")
        self.assertFalse(snapshots[0]["quiet"])

    def test_spread_joins_same_minute_with_different_close_times(self):
        binance = [{**kline_to_row("BTCUSDT", "1m", kline(1_700_000_000_000, 100)), "source": "binance"}]
        index = dict(binance[0])
        index["source"] = "cfbenchmarks"
        index["close"] = 100.05
        index["close_time"] = "2023-11-14T22:13:00+00:00"
        binance[0]["close_time"] = "2023-11-14T22:13:59.999000+00:00"
        self.assertEqual(bucket_time(binance[0]["close_time"], "1m"), bucket_time(index["close_time"], "1m"))
        snapshots = build_spread_snapshots(binance + [index], "BTCUSDT", "1m", threshold_bps=25.0)
        self.assertEqual(snapshots[0]["reason"], "ok")
        self.assertFalse(snapshots[0]["quiet"])


class IndexImportTests(unittest.TestCase):
    def test_parses_csv_and_opens_gate(self):
        csv_text = "timestamp,value\n2023-11-14T22:14:10Z,100.02\n2023-11-14T22:14:40Z,100.04\n"
        self.assertEqual(len(parse_index_records(csv_text)), 2)
        rows = [kline(1_700_000_000_000, 100)]
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "vault.db")
            CandleImporter(database, FakeBinance(rows)).import_binance("BTCUSDT", "1m", 1_700_000_000, 1_700_000_120)
            result = IndexImporter(database).import_records(
                csv_text,
                symbol="BTCUSDT",
                interval="1m",
            )
            self.assertEqual(result["records_imported"], 1)
            self.assertGreaterEqual(result["compared"], 1)
            self.assertEqual(result["gate"]["reason"], "ok")
            self.assertFalse(result["gate"]["quiet"])
            source = database.connection.execute(
                "SELECT source FROM candles WHERE source='cfbenchmarks' LIMIT 1"
            ).fetchone()[0]
            self.assertEqual(source, "cfbenchmarks")
            database.close()

    def test_eth_tape_resamples_to_one_minute_candles(self):
        trades = [
            (1_700_000_000_000, 1573.5, 1.0, 1573.5),
            (1_700_000_010_000, 1574.0, 2.0, 3148.0),
            (1_700_000_070_000, 1572.0, 0.5, 786.0),
        ]
        candles = trades_to_candles(trades, "ETHUSDT", "1m")
        self.assertEqual(infer_symbol(Path("ETHUSDT-trades-2026-07.zip")), "ETHUSDT")
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].symbol, "ETHUSDT")
        self.assertEqual(candles[0].close, 1574.0)
        self.assertEqual(candles[0].high, 1574.0)
        self.assertEqual(candles[0].volume, 3.0)
        self.assertEqual(candles[1].open, 1572.0)

    def test_parses_cf_payload_json(self):
        payload = {
            "payload": [
                {"time": "2026-09-20T02:17:01Z", "value": "81100.12"},
                {"time": "2026-09-20T02:17:59Z", "value": "81110.00"},
            ]
        }
        points = parse_index_records(payload)
        self.assertEqual(len(points), 2)
        self.assertAlmostEqual(points[-1][1], 81110.0)


class FeatureTests(unittest.TestCase):
    def test_ema_and_rsi_on_flat_series(self):
        closes = [100.0] * 30
        self.assertEqual(ema(closes, 9)[-1], 100.0)
        self.assertEqual(rsi(closes)[-1], 100.0)

    def test_fibonacci_up_impulse_618(self):
        levels = fibonacci_from_swings(200.0, 100.0, "up", 138.2)
        self.assertAlmostEqual(levels["fib_618"], 138.2)
        self.assertEqual(levels["nearest_level"], "fib_618")

    def test_swings_are_only_known_after_confirmation(self):
        candles = []
        start = 1_700_000_000
        prices = [10, 11, 12, 20, 12, 11, 10, 11, 12]
        for index, price in enumerate(prices):
            candles.append(
                {
                    "high": price,
                    "low": price - 1,
                    "close_time": f"2023-11-14T22:13:{index:02d}+00:00",
                    "open_time": f"2023-11-14T22:12:{index:02d}+00:00",
                }
            )
        swings = confirmed_swings(candles, strength=2)
        highs = [swing for swing in swings if swing["kind"] == "high"]
        self.assertTrue(highs)
        peak = highs[0]
        self.assertEqual(peak["price"], 20)
        known_early = swings_known_at(swings, peak["time"])
        self.assertFalse(any(item["price"] == 20 for item in known_early))
        known_later = swings_known_at(swings, peak["confirmed_at"])
        self.assertTrue(any(item["price"] == 20 for item in known_later))

    def test_reconstruct_freezes_t_without_settlement(self):
        rows = []
        base = 1_700_000_000_000
        price = 100.0
        for i in range(80):
            if 30 <= i <= 40:
                price = 100 + (i - 30)
            elif i > 40:
                price = 110 - (i - 40) * 0.4
            rows.append(kline(base + i * 60_000, price, price + 1, price - 1))
        with tempfile.TemporaryDirectory() as folder:
            database = KalshiDatabase(Path(folder) / "vault.db")
            CandleImporter(database, FakeBinance(rows)).import_binance("BTCUSDT", "1m", 1_700_000_000, 1_700_005_000)
            entry = database.connection.execute(
                "SELECT close_time FROM candles ORDER BY close_time DESC LIMIT 1 OFFSET 10"
            ).fetchone()[0]
            result = reconstruct_trade(database, entry, contract="TEST-1", target=105.0, symbol="BTCUSDT")
            entry_row = result["entry"]
            self.assertEqual(entry_row["offset"], "T")
            self.assertTrue(entry_row["usable_at_entry"])
            self.assertIsNone(entry_row["final_result"])
            self.assertIn("T-60", result["offsets"])
            self.assertIn("OBSERVATION", result["dossier"])
            self.assertIn("ACTUAL RESULT", result["dossier"])
            leaked = database.connection.execute(
                "SELECT final_result FROM trade_reconstructions WHERE offset='T'"
            ).fetchone()[0]
            self.assertIsNone(leaked)
            plus = database.connection.execute(
                "SELECT usable_at_entry FROM trade_reconstructions WHERE offset='T+5'"
            ).fetchone()[0]
            self.assertEqual(plus, 0)
            technical, fibonacci = compute_feature_rows(
                [dict(row) for row in database.load_candles("binance", "BTCUSDT", "1m")],
                "binance",
                "BTCUSDT",
                "1m",
            )
            self.assertTrue(technical)
            database.close()


if __name__ == "__main__":
    unittest.main()
