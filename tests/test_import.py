import copy
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_workspace as importer
from test_workspace import fact


class ImportTests(unittest.TestCase):
    def backup(self):
        return {'version': 2, 'changes': [{'id': 'fixture', 'page': '/private-label/', 'published_at': '2026-10-01',
                'summary': 'Fixture publication', 'owner': 'PRIVATE OWNER', 'hypothesis': 'Fixture hypothesis',
                'evidence_url': 'https://evidence.example/publication', 'verified_at': '2026-10-02'}],
                'tasks': {'/': 'Published'}, 'leads': [{'email': 'PRIVATE'}],
                'review': {'fact_reviews': {'organization_name': fact('Fixture factory')}}}

    def test_private_fields_excluded_and_reviews_require_explicit_opt_in(self):
        result = importer.merge_workspace(self.backup(), {'changes': []})
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('fact_reviews', result)
        self.assertEqual(result['changes'][0]['hypothesis'], 'Fixture hypothesis')
        reviewed = importer.merge_workspace(self.backup(), {'changes': []}, True)
        self.assertEqual(reviewed['fact_reviews']['organization_name']['value'], 'Fixture factory')

    def test_import_is_idempotent_and_does_not_mutate_input(self):
        original = {'changes': []}
        result = importer.merge_workspace(self.backup(), original, True)
        self.assertEqual(original, {'changes': []})
        self.assertEqual(importer.merge_workspace(self.backup(), result, True), result)

    def test_duplicate_ids_and_invalid_verification_are_rejected(self):
        backup = self.backup()
        backup['changes'].append(copy.deepcopy(backup['changes'][0]))
        with self.assertRaises(ValueError):
            importer.merge_workspace(backup, {})
        backup = self.backup()
        backup['changes'][0]['verified_at'] = '2026-09-30'
        with self.assertRaises(ValueError):
            importer.merge_workspace(backup, {})

    def test_reviewed_proof_uses_public_field_allowlist(self):
        backup = self.backup()
        backup['review']['proof_reviews'] = {'sample-note': {
            'status': 'confirmed', 'category': 'qc_edge_case', 'pages': ['/private-label/'],
            'evidence': 'Approved example', 'source_url': 'https://evidence.example/proof',
            'reviewer': 'Quality team', 'reviewed_at': '2026-11-15', 'public_safe': True, 'internal_notes': 'PRIVATE',
        }}
        self.assertNotIn('proof_reviews', importer.merge_workspace(backup, {}))
        reviewed = importer.merge_workspace(backup, {}, True, date(2026, 11, 16))
        self.assertNotIn('PRIVATE', json.dumps(reviewed))
        self.assertEqual(reviewed['proof_reviews']['sample-note']['category'], 'qc_edge_case')

    def test_cli_dry_run_preserves_file_and_apply_requires_public_review(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            base = Path(folder)
            ed, export = base / 'editorial.json', base / 'export.json'
            ed.write_text('{"changes": []}')
            export.write_text(json.dumps(self.backup()))
            args = ['import_workspace.py', str(export), '--editorial', str(ed)]
            with patch.object(sys, 'argv', args):
                importer.main()
            self.assertEqual(ed.read_text(), '{"changes": []}')
            with patch.object(sys, 'argv', args + ['--apply']):
                with self.assertRaises(SystemExit):
                    importer.main()
            with patch.object(sys, 'argv', args + ['--apply', '--public-reviewed', '--include-reviews']):
                importer.main()
            read_back = json.loads(ed.read_text())
            self.assertEqual(read_back['changes'][0]['id'], 'fixture')
            self.assertNotIn('owner', read_back['changes'][0])
            self.assertEqual(read_back['fact_reviews']['organization_name']['value'], 'Fixture factory')


if __name__ == '__main__':
    unittest.main()
