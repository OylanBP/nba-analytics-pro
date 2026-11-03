import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from player_roles import name_key,role_features,role_history

class Roles(unittest.TestCase):
    def test_only_prior_same_team_season_and_last_ten(self):
        games=[dict(id=str(d),date=f"2026-01-{d:02d}T00:00Z",season=2026) for d in range(1,14)]
        boxes={str(d):{"8":{"Example Player":[d,d+1]}} for d in range(1,14)}
        roles=role_history(games,boxes)
        target=dict(season=2026,home="2",away="8",date="2026-01-13T22:00Z")
        reports={"away":{"players":[dict(name="Player, Example",status="Out")]},
                 "home":{"players":[dict(name="Player, Example",status="Out")]}}
        values,n=role_features(reports,target,roles)
        self.assertEqual(n,1)
        self.assertEqual(reports["away"]["players"][0]["role"],dict(minutes=7.5,points=8.5,games=10))
        self.assertNotIn("role",reports["home"]["players"][0])
        self.assertAlmostEqual(values[0],7.5/30)
        self.assertAlmostEqual(values[4],8.5/20)
        self.assertEqual(role_features(reports,{**target,"season":2027},roles)[1],0)
        self.assertEqual(name_key("Jokić, Nikola"),name_key("Nikola Jokic"))

    def test_sparse_history_keeps_count_fallback(self):
        g=dict(home="2",away="8",season=2026,date="2026-01-10")
        reports={"away":{"players":[dict(name="B, A",status="Out")]},"home":{"players":[]}}
        self.assertEqual(role_features(reports,g,{(2026,"8","ab"):[("2026-01-01",[15,6])]}),([0.]*8,0))
