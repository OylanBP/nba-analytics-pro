import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fetch_official_injuries import parse_lines
from availability import difference, game_key, adjust
from injury_archive import injury_at

class AvailabilityTests(unittest.TestCase):
    def test_row_ownership_and_pending(self):
        sample="""01/15/2026  07:00 (ET)  BOS@WAS  Boston Celtics  Player, One  Out  Injury/Illness
                              Washington Wizards  NOT YET SUBMITTED
Page 1 of 1"""
        url='https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-01-15_05_00PM.pdf'
        teams={'Boston Celtics':{'id':'2'},'Washington Wizards':{'id':'27'}}
        s=parse_lines(sample,url,teams)
        def lookup(t):
            return injury_at('2026-01-16T00:00Z',t,[s],'BOS@WAS','2026-01-15')
        self.assertEqual(lookup('2')['players'][0]['name'],'Player, One')
        self.assertEqual(lookup('27')['status'],'unknown')
        self.assertIsNone(difference(lookup('2'),lookup('27')))
        self.assertEqual(game_key({'date':'2026-01-16T00:00Z','away':'2','home':'27'},{'2':'BOS','27':'WSH'}),('2026-01-15','BOS@WAS'))
        self.assertAlmostEqual(adjust(.64,[.1]*4,[0]*4),.64)
        self.assertGreater(adjust(.64,[.1]*4,[1,0,0,0]),.64)
