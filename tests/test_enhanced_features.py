import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from enhanced_features import build
from enhanced_model import vector

class EnhancedFeatureTests(unittest.TestCase):
    def test_no_same_day_leakage(self):
        games = [
            {"id":"1","date":"2026-10-01T20:00:00Z","season":2027,"home":"1","away":"2","h":120,"a":90},
            {"id":"2","date":"2026-10-01T23:00:00Z","season":2027,"home":"1","away":"3","h":130,"a":80},
            {"id":"3","date":"2026-10-03T20:00:00Z","season":2027,"home":"1","away":"2","h":90,"a":100},
        ]
        rows = build(games)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["home_elo"], 1500)
        self.assertEqual(rows[1]["home_elo"], 1500)
        self.assertEqual(rows[0]["home_last10_win_pct"], .5)
        self.assertEqual(rows[1]["home_last10_win_pct"], .5)
        self.assertGreater(rows[2]["home_elo"], 1500)
        self.assertEqual(rows[2]["home_last10_win_pct"], 1)
        self.assertEqual(len(vector(rows[2], True)), 10)

if __name__ == "__main__":
    unittest.main()
