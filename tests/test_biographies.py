import sys
import pathlib
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from update_biographies import parse,draft_text

class Biographies(unittest.TestCase):
    def test_no_inference(self):
        row=parse({'id':'7','birthPlace':{'country':'France'}},{'athlete':{'id':'7','displayName':'Test'}},{},'2026-11-09')
        self.assertIsNone(row['birthday'])
        self.assertIsNone(row['college'])
        self.assertNotIn('nationality',row)
        self.assertEqual(row['birthplace'],{'country':'France'})
    def test_wrong_player_rejected(self):
        with self.assertRaises(ValueError):
            parse({'id':'7'},{'athlete':{'id':'8'}},{},'2026-11-09')
    def test_draft_overall_and_unknown(self):
        self.assertEqual(draft_text('2014: Rd 2, Pk 41 (DEN)')['pick'],41)
        self.assertIsNone(draft_text('unknown'))
        self.assertEqual(draft_text('Undrafted'),'未經 NBA 選秀獲選')

    def test_source_failure_preserves_snapshot(self):
        from unittest.mock import patch
        import tempfile,json
        import update_biographies as module
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'data').mkdir()
            output=root/'data/biographies.json'
            old=json.dumps({'players':{'7':{'name':'previous'}}})
            output.write_text(old)
            (root/'data/rosters.json').write_text(json.dumps({'teams':[{'id':'1','players':[{'id':'7'}]}]}))
            def fetch(url):
                if '/teams/' in url:return {'athletes':[{'id':'7'}]}
                raise OSError('source unavailable')
            with patch.object(module,'ROOT',root),patch.object(module,'OUT',output),patch.object(module,'fetch',fetch):
                with self.assertRaises(ValueError):module.main()
            self.assertEqual(output.read_text(),old)

    def test_former_roster_player_uses_verified_profile_fields(self):
        row=parse({'id':'7'},{'athlete':{'id':'7','displayName':'Test','displayDOB':'31/12/2000','displayBirthPlace':'Paris, France','college':{'name':'School'}}},{},'2026-11-09')
        self.assertEqual(row['birthday'],'2000-12-31')
        self.assertEqual(row['birthplace_text'],'Paris, France')
        self.assertEqual(row['college'],'School')
