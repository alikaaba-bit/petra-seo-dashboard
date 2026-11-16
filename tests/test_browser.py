import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import unittest
from browser_check import decode_result, evaluate_page

class BrowserTests(unittest.TestCase):
    def test_structured_wrapper_output_and_demo_failure(self):
        self.assertEqual(decode_result('result: "{\\"url\\":\\"https://petrajewelryfactory.com/\\"}"\nhelp[1]:' )['url'], 'https://petrajewelryfactory.com/')
        raw = {'url':'https://petrajewelryfactory.com/', 'title':'Fixture','h1':['Fixture'], 'description':'Fixture',
               'canonical':'https://petrajewelryfactory.com/', 'visible_characters':300, 'raw_matches':['sophie moore'], 'visible_matches':[]}
        self.assertIn('raw_matches: sophie moore',evaluate_page(raw,raw['url'])['findings'])
        raw['raw_matches']=[]
        self.assertEqual(evaluate_page(raw,raw['url'])['findings'],[])
        self.assertTrue(evaluate_page(raw,raw['url']+'#/private-label')['findings'])
    def test_missing_result_never_passes(self):
        with self.assertRaises(ValueError): decode_result('Browser unavailable')
