import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import json
import tempfile
import unittest
from lighthouse_summary import summarize


class LighthouseTests(unittest.TestCase):
    def test_failure_keeps_saved_results_and_records_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            saved = root / 'performance.json'
            saved.write_text('{"generated_at":"old"}')
            for raw in ({'runtimeError': {'code': 'FAILED_DOCUMENT_REQUEST'}},
                        {'finalUrl': 'https://petrajewelryfactory.com/', 'fetchTime': '2026-11-16', 'categories': {'seo': {'score': None}}}):
                (root / 'lhr-one.json').write_text(json.dumps(raw))
                self.assertEqual(summarize(root, root)['status'], 'failed')
                self.assertEqual(json.loads(saved.read_text())['generated_at'], 'old')
            (root / 'lhr-one.json').unlink()
            self.assertEqual(summarize(root, root)['status'], 'failed')

    def test_required_coverage_and_collection_failure_prevent_partial_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            url = 'https://petrajewelryfactory.com/'
            raw = {'requestedUrl': url, 'finalUrl': url, 'fetchTime': '2026-11-16T00:00:00Z',
                   'categories': {'performance': {'score': .9}, 'seo': {'score': .8}}}
            (root / 'lhr-one.json').write_text(json.dumps(raw))
            self.assertEqual(summarize(root, root, [url + 'missing/'])['status'], 'failed')
            self.assertFalse((root / 'performance.json').exists())
            self.assertEqual(summarize(root, root, [url], True)['status'], 'failed')
            self.assertEqual(summarize(root, root, [url])['status'], 'passed')
            self.assertEqual(json.loads((root / 'performance.json').read_text())['reports'][0]['scores']['performance'], 90)
