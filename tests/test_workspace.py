import copy
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import seo_workspace as workspace
from seo_pipeline import SITE
from update_data import ALL_KEYWORDS

TODAY = date(2026, 11, 16)


def fact(value, supported=True):
    return {'status': 'confirmed', 'value': value, 'supported': supported, 'source_url': 'https://evidence.example/factory',
            'reviewer': 'Fixture reviewer', 'reviewed_at': '2026-11-15', 'public_safe': True}


def checked(path='/private-label/'):
    return {'url': SITE.rstrip('/') + path, 'path': path, 'final_url': SITE.rstrip('/') + path,
            'crawl_status': 'checked', 'http_status': 200, 'issues': [], 'title': 'Fixture title',
            'description': 'Fixture description', 'canonical': SITE.rstrip('/') + path,
            'headings': [{'level': 'h1', 'text': 'Fixture H1'}], 'robots': [], 'schema_types': ['Organization'], 'schema_hash': 'one'}


class WorkspaceTests(unittest.TestCase):
    def test_all_targets_have_proposals_but_no_invented_approval(self):
        terms = workspace.term_map({}, TODAY)
        self.assertEqual(len(terms), 50)
        self.assertEqual({x['keyword'] for x in terms}, set(ALL_KEYWORDS))
        self.assertFalse(any(x['status'] == 'approved' for x in terms))
        self.assertTrue(all(x['approved_page'] is None for x in terms))
        self.assertEqual(next(x for x in terms if 'lifetime warranty' in x['keyword'])['status'], 'hold')

    def test_confirmed_facts_require_source_review_and_public_approval(self):
        for key in ('source_url', 'reviewer', 'reviewed_at', 'public_safe'):
            candidate = fact('Fixture name')
            candidate.pop(key)
            with self.assertRaises(ValueError):
                workspace.validate_fact('organization_name', candidate, TODAY)
        self.assertIsNone(workspace.confirmed_facts({'business_facts': {'moq': '999'}}).get('moq'))

    def test_private_references_and_bad_paths_are_rejected(self):
        for url in ('https://127.0.0.1/a', 'https://user:password@example.com/a', 'https://example.com/?token=x', 'file:///private/a'):
            self.assertFalse(workspace.public_url(url))
        for path in ('//evil.com/', '/#/services', '/a/../b', '/%2e%2e/b', '/x?token=a'):
            self.assertFalse(workspace.canonical_path(path))

    def test_term_approval_requires_serp_evidence_and_review(self):
        term = workspace.term_map({}, TODAY)[0]
        term.update(status='approved', approved_page='/services/')
        with self.assertRaises(ValueError):
            workspace.validate_term(term['keyword'], term, TODAY)

    def test_unknown_facts_never_emit_schema_or_llms_copy(self):
        draft = workspace.draft_pack({}, [], [], TODAY)
        self.assertIsNone(draft['organization_schema'])
        self.assertIsNone(draft['llms_txt'])
        self.assertTrue(draft['unknown_facts'])

    def test_schema_uses_only_confirmed_fields_and_omits_unknown_contact_data(self):
        ed = {'fact_reviews': {'organization_name': fact('Fixture factory')}}
        draft = workspace.draft_pack(ed, [], [], TODAY)
        self.assertEqual(draft['organization_schema']['name'], 'Fixture factory')
        for key in ('telephone', 'email', 'address', 'aggregateRating', 'offers'):
            self.assertNotIn(key, draft['organization_schema'])
        self.assertIn('draft', draft['status'])

    def test_negative_capability_does_not_clear_a_term_hold(self):
        term = next(t for t in workspace.term_map({}, TODAY) if t['keyword'] == 'waterproof jewelry manufacturer')
        missing = workspace.missing_facts(term, {'waterproof': fact('Not supported', supported=False)})
        self.assertIn('waterproof', missing)

    def test_reviewed_intent_facts_and_first_hand_evidence_produce_one_grouped_draft(self):
        term = workspace.term_map({}, TODAY)[0]
        keyword = 'private label jewelry manufacturer'
        approval = {'status': 'approved', 'reason': 'Fixture intent review', 'approved_page': '/private-label/',
                    'intent': 'commercial', 'page_type': 'supplier_landing', 'reviewer': 'Fixture reviewer', 'reviewed_at': '2026-11-15',
                    'serp': {'urls': ['https://evidence.example/supplier'], 'market': 'Fixture market', 'device': 'desktop',
                             'checked_at': '2026-11-15', 'page_type': 'supplier_landing'}}
        ed = {'term_reviews': {keyword: approval}, 'fact_reviews': {'organization_name': fact('Fixture factory'),
              'manufacturing_summary': fact('Fixture supported manufacturing scope')},
              'page_reviews': {'/private-label/': {'buyer_problem': 'Fixture problem', 'first_hand_evidence': 'Fixture process record',
                  'working_title': 'Fixture manufacturing', 'source_url': 'https://evidence.example/process', 'hypothesis': 'Fixture hypothesis', 'reviewer': 'Fixture reviewer',
                  'reviewed_at': '2026-11-15', 'public_safe': True}}}
        pack = workspace.draft_pack(ed, workspace.term_map(ed, TODAY), [checked()], TODAY)
        ready = [p for p in pack['packets'] if p['status'] == 'draft_for_human_review']
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]['eligible_terms'], [keyword])
        self.assertIn('Fixture factory', ready[0]['suggested_title'])
        self.assertNotIn('/services/', pack['llms_txt'])

    def test_schema_parser_records_types_but_does_not_treat_schema_claims_as_facts(self):
        from seo_pipeline import PageHTML
        parser = PageHTML(SITE)
        parser.feed('<script type="application/ld+json">{"@graph":[{"@type":"Organization","name":"Unverified"}]}</script><script type="application/ld+json">invalid</script>')
        self.assertEqual(parser.schema_summary()['schema_types'], ['Organization'])
        self.assertEqual(parser.schema_errors, 1)
        self.assertNotIn('Unverified', parser.text)

    def test_followup_collection_limit_is_visible_after_record_fifty(self):
        from seo_pipeline import change_results
        from unittest.mock import MagicMock
        service = MagicMock()
        changes = [{'id': str(i), 'page': '/private-label/', 'published_at': '2026-08-01'} for i in range(51)]
        results = change_results(service, changes, TODAY, limit=0)
        self.assertEqual(len(results), 51)
        self.assertEqual(results[-1]['windows'][0]['status'], 'Deferred: follow-up request limit')
        service.searchanalytics.assert_not_called()

    def test_drift_does_not_call_a_failed_baseline_good_or_missing_coverage_removed(self):
        before = {'attempted_at': '2026-11-15T00:00:00Z', 'pages': [checked()]}
        after = {'attempted_at': '2026-11-16T00:00:00Z', 'pages': []}
        result = workspace.compare_drift(before, after)
        self.assertEqual(result['findings'][0]['kind'], 'not_checked')
        broken = copy.deepcopy(before)
        broken['pages'][0].update(crawl_status='error', http_status=200)
        self.assertEqual(workspace.baseline_snapshot(broken)['quality'], 'observed_problems')

    def test_drift_flags_canonical_schema_and_noindex_changes_for_review(self):
        before = {'generated_at': '2026-11-15T00:00:00Z', 'pages': [checked()]}
        after = copy.deepcopy(before)
        after['generated_at'] = '2026-11-16T00:00:00Z'
        after['pages'][0].update(canonical=SITE, schema_hash='two', robots=['noindex'])
        changes = workspace.compare_drift(before, after)['findings']
        self.assertTrue({'canonical', 'schema_hash', 'robots'} <= {x['field'] for x in changes})
        self.assertTrue(any(x['severity'] == 'critical' for x in changes))

    def test_all_changes_get_followups_and_stale_cutoff_stays_visible(self):
        changes = [{'id': str(i), 'page': '/private-label/', 'published_at': '2026-10-01', 'summary': 'Fixture change'} for i in range(51)]
        queue = workspace.followups(changes, {'period': {'end': '2026-10-20'}, 'change_results': []}, TODAY)
        self.assertEqual(len(queue), 102)
        self.assertEqual(queue[0]['window_end'], '2026-10-28')
        self.assertEqual(queue[0]['earliest_check_on'], '2026-10-31')
        self.assertEqual(queue[0]['status'], 'Awaiting finalized GSC refresh')
        self.assertEqual(queue[1]['status'], 'Collecting data')

    def test_old_result_cannot_complete_an_edited_publication_date(self):
        change = {'id': 'a', 'page': '/private-label/', 'published_at': '2026-09-01'}
        search = {'period': {'end': '2026-11-13'}, 'change_results': [{'change': {**change, 'published_at': '2026-08-01'}, 'windows': [{'days': 28, 'status': 'Observed change; not causal proof'}]}]}
        self.assertEqual(workspace.followups([change], search, TODAY)[0]['status'], 'Due for calculation')

    def test_report_build_keeps_sources_dated_and_missing_metrics_unknown(self):
        report = workspace.build_workspace({}, {}, {}, {}, today=TODAY)
        self.assertEqual(report['sources']['search'], None)
        self.assertEqual(len(report['terms']), 50)
        self.assertTrue(report['alerts'])
        self.assertEqual(report['opportunities'], [])
        self.assertFalse(report['publication_ready'])


if __name__ == '__main__':
    unittest.main()

class WorkspaceFreshnessTests(unittest.TestCase):
    def test_stale_crawl_cannot_clear_draft_gate(self):
        from unittest.mock import patch
        with patch.object(workspace, 'draft_pack', wraps=workspace.draft_pack) as build:
            workspace.build_workspace({}, {}, {'generated_at':'2026-09-01T00:00:00Z','pages':[checked()]}, {}, today=TODAY)
            self.assertEqual(build.call_args.args[2], [])

    def test_reverse_chronology_does_not_report_canonical_change(self):
        before = {'generated_at':'2026-11-16T00:00:00Z','pages':[checked()]}
        after = {'generated_at':'2026-11-15T00:00:00Z','pages':[checked()]}
        self.assertEqual(workspace.compare_drift(before, after)['findings'][0]['field'],'chronology')


class PlanningEvidenceTests(unittest.TestCase):
    def test_search_queries_do_not_become_approved_title_claims(self):
        from seo_pipeline import enrich_briefs
        page = {'url':SITE+'private-label/', 'path':'/private-label/', 'audit':checked(), 'topic':'Unassigned',
                'queries':[{'query':'unsupported lifetime warranty manufacturer','branded':False}], 'business_value':3}
        enrich_briefs([page])
        self.assertEqual(page['brief']['status'],'planning')
        self.assertIsNone(page['brief']['suggested_title'])
        self.assertIsNone(page['brief']['suggested_h1'])
