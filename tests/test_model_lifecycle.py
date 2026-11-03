import unittest
from scripts.build_model_history import make_features
from scripts.model_lifecycle import train, score

class LifecycleTests(unittest.TestCase):
    def test_same_day_results_are_not_leaked(self):
        games=[
            dict(id="1",date="2026-10-01T01:00Z",season=2027,home="A",away="B",h=110,a=90),
            dict(id="2",date="2026-10-01T23:00Z",season=2027,home="A",away="C",h=90,a=100),
            dict(id="3",date="2026-10-03T01:00Z",season=2027,home="A",away="B",h=110,a=90)]
        rows=make_features(games)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]["home_win_pct_before"],0.5)
        self.assertEqual(rows[1]["home_win_pct_before"],0.5)
        self.assertEqual(rows[2]["home_win_pct_before"],0.5)
        self.assertEqual(rows[2]["home_rest_days"],1)

    def test_model_score_bounds(self):
        rows=[("2026-10-01",[0.5,0.4,2.0,1.0],i%2) for i in range(120)]
        weights=train(rows,steps=20)
        result=score(weights,rows)
        self.assertGreaterEqual(result["brier"],0)
        self.assertLessEqual(result["brier"],1)
        self.assertEqual(result["n"],120)

if __name__=="__main__":
    unittest.main()
