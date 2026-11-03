import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from injury_archive import injury_at, validate_snapshot

class InjuryArchiveTests(unittest.TestCase):
    def test_no_source_rejected(self):
        with self.assertRaises(ValueError):
            validate_snapshot({"observed_utc": "2026-10-01T12:00:00Z", "players": []})

    def test_historical_snapshot_is_not_inferred_from_future(self):
        snapshot = {"observed_utc": "2026-10-02T12:00:00Z",
                    "source_url": "https://example.org/archived-report",
                    "players": [{"team_id": "1", "name": "Test Player", "status": "Out"}]}
        self.assertEqual(injury_at("2026-10-01T20:00:00Z", "1", [snapshot])["status"], "unknown")
        self.assertEqual(injury_at("2026-10-03T12:00:00Z", "1", [snapshot])["players"][0]["status"], "Out")
        self.assertEqual(injury_at("2026-10-06T12:00:00Z", "1", [snapshot])["status"], "unknown")

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):
            validate_snapshot({"observed_utc": "2026-10-01T12:00:00Z",
                               "source_url": "https://example.org/archived-report",
                               "players": [{"team_id": "1", "name": "Test Player", "status": "Guess"}]})

if __name__ == "__main__":
    unittest.main()
