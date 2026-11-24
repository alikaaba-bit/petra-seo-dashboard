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
from seo_pipeline import SITE, crawl_health
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
        self.assertEqual(len(terms), len(ALL_KEYWORDS))
        self.assertEqual({x['keyword'] for x in terms}, set(ALL_KEYWORDS))
        self.assertFalse(any(x['status'] == 'approved' for x in terms))
        self.assertTrue(all(x['approved_page'] is None for x in terms))
        self.assertEqual(workspace.seed_term('lifetime warranty jewelry manufacturer', 'durability')['status'], 'hold')

    def test_retired_reviews_are_preserved_without_becoming_active_targets(self):
        editorial = {'term_reviews': {'waterproof jewelry manufacturer': {'status': 'hold', 'reason': 'Historical review'}}}
        original = copy.deepcopy(editorial)
        terms = workspace.term_map(editorial, TODAY)
        self.assertEqual(editorial, original)
        self.assertNotIn('waterproof jewelry manufacturer', [term['keyword'] for term in terms])
        with self.assertRaises(ValueError):
            workspace.term_map({'term_reviews': {'unknown target': {}}}, TODAY)

    def test_target_proposals_group_variants_and_keep_guide_intent_unapproved(self):
        terms = {term['keyword']: term for term in workspace.term_map({}, TODAY)}
        core = terms['stainless steel jewelry manufacturer']['proposed_page']
        for keyword in ('custom stainless steel jewelry manufacturer', 'stainless steel jewellery manufacturer',
                        'stainless steel jewelry OEM manufacturer'):
            self.assertEqual(terms[keyword]['proposed_page'], core)
        brief = terms['jewelry manufacturing brief template']
        self.assertEqual((brief['intent'], brief['page_type']), ('informational', 'guide'))
        self.assertIsNone(brief['approved_page'])
        self.assertNotEqual(brief['status'], 'approved')

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
        term = workspace.seed_term('waterproof jewelry manufacturer', 'durability')
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
        self.assertEqual(ready[0]['suggested_h1'], 'Fixture manufacturing')
        self.assertNotIn('/services/', pack['llms_txt'])

    def test_scoped_proof_cites_only_confirmed_public_receipts_and_does_not_clear_fact_holds(self):
        receipt = {'status': 'confirmed', 'category': 'process_test', 'pages': ['/private-label/'],
                   'evidence': 'Reviewed sample inspection record', 'source_url': 'https://evidence.example/test',
                   'reviewer': 'Operations review', 'reviewed_at': '2026-11-15', 'public_safe': True}
        ed = {'proof_reviews': {'sample-check': receipt, 'photo': {'status': 'unknown', 'evidence': 'Draft note'}}}
        report = workspace.build_workspace(ed, {}, {'attempted_at': '2026-11-16', 'pages': [checked()]}, {}, today=TODAY)
        self.assertEqual([r['id'] for r in report['proof_kb']['records']], ['sample-check'])
        private_label = next(p for p in report['draft_pack']['packets'] if p['page'] == '/private-label/')
        self.assertEqual(private_label['proof'][0]['source_url'], receipt['source_url'])
        self.assertEqual(private_label['status'], 'hold')
        self.assertIsNone(private_label['suggested_h1'])
        self.assertTrue(all(not p['proof'] for p in report['draft_pack']['packets'] if p is not private_label))
        for change in ({'public_safe': False}, {'reviewed_at': '2026-11-17'}, {'pages': ['/#/private-label']}):
            with self.assertRaises(ValueError):
                workspace.validate_proof('sample-check', {**receipt, **change}, TODAY)

    def test_roadmap_reopens_the_checklist_on_failure_and_keeps_measurement_separate(self):
        from seo_method import CHECKLIST, TIERS
        checklist = checked(CHECKLIST)
        search = {'generated_at': '2026-11-05T12:00:00Z', 'period': {'end': '2026-11-02'}}
        attempted = {'status': 'failed', 'attempted_at': '2026-11-16T01:00:00Z', 'error': {'http_status': 403}}
        for code, state in ((404, 'Open'), (200, 'Verified')):
            with self.subTest(code=code):
                crawl = {'attempted_at': '2026-11-16T02:00:00Z',
                         'pages': [checked('/'), checked(), {**checklist, 'http_status': code}]}
                report = workspace.build_workspace({}, search, crawl, {}, today=TODAY, search_attempt=attempted)
                road = report['roadmap']
                self.assertEqual(list(dict.fromkeys(row['tier'] for row in road)), list(TIERS))
                self.assertIn('403', road[0]['evidence'])
                self.assertEqual(next(row for row in road if row['page'] == CHECKLIST)['status'], state)
                self.assertEqual(report['sources']['search_through'], '2026-11-02')
                self.assertEqual(report['sources']['crawl'], '2026-11-16T02:00:00Z')
                self.assertEqual(report['blitz']['page'], '/private-label/')
                self.assertTrue(report['blitz']['live_verified'])
                self.assertEqual(report['blitz']['status'], 'Held')

    def test_internal_link_graph_excludes_failed_and_unchecked_routes_and_avoids_body_duplicates(self):
        from seo_method import CHECKLIST
        target = checked()
        guide = {**checked(CHECKLIST), 'links': [target['url']], 'body_links': []}
        inventory = {'generated_at': '2026-11-15', 'pages': [guide, target]}
        for latest, suggested, node_count in (
            ([guide, target], True, 2),
            ([guide, {**target, 'http_status': 404}], False, 1),
            ([target], False, 1),
            ([{**guide, 'body_links': [target['url']]}, target], False, 2),
        ):
            with self.subTest(latest=latest):
                report = workspace.build_workspace({}, {}, {'attempted_at': '2026-11-16', 'pages': latest}, {},
                                                   today=TODAY, inventory=inventory)
                self.assertEqual(len(report['internal_links']['graph']), node_count)
                self.assertEqual(bool(report['internal_links']['suggestions']), suggested)
        self.assertEqual(len(workspace.build_workspace({}, {}, {'attempted_at': '2026-11-10', 'pages': [guide, target]}, {},
                                                       today=TODAY, inventory=inventory)['internal_links']['graph']), 0)

    def test_weekly_checkpoint_uses_last_completed_week_and_shows_observed_coverage(self):
        page = checked('/contract-manufacturing/')
        inspection = {'verdict': 'NEUTRAL', 'lastCrawlTime': '2026-11-05T18:34:02Z'}
        search = {'overall': {'clicks': 0, 'impressions': 9},
                  'pages': [{**page, 'index_status': 'Not found (404)', 'inspection': inspection},
                            {'url': SITE + '#/services', 'path': '/#/services', 'inspection': inspection}]}
        crawl = {'attempted_at': '2026-11-16', 'pages': [page]}
        report = workspace.build_workspace({}, {}, crawl, {}, today=TODAY)
        report['alerts'] = []
        result = workspace.checkpoint_markdown(report, search, crawl, {'id': 123, 'conclusion': 'success'}, TODAY)
        self.assertIn('2026-11-09 through 2026-11-15', result)
        self.assertIn('clicks 0 · impressions 9', result)
        self.assertIn('/contract-manufacturing/ · saved crawl HTTP 200', result)
        self.assertIn('2026-11-05T18:34:02Z', result)
        self.assertNotIn('/#/services', result)
        self.assertIn('Reconcile received quote and catalogue requests', result)

    def test_weekly_checkpoint_preserves_missing_counts_and_collector_alerts(self):
        report = workspace.build_workspace({}, {}, {}, {}, today=TODAY)
        result = workspace.checkpoint_markdown(report, {}, {}, {}, TODAY)
        self.assertIn('clicks unknown · impressions unknown', result)
        self.assertIn('Latest completed collector run · unknown', result)
        self.assertIn('Account owner', result)
        report['alerts'] = []
        failed = workspace.checkpoint_markdown(report, {}, {}, {'conclusion': 'failure'}, TODAY)
        self.assertIn('Review the latest collector run before using the saved figures', failed)

    def test_manual_ai_observation_separates_absent_from_unobserved_and_rejects_raw_text(self):
        observation = {'provider': 'ChatGPT', 'prompt_id': 'brief-ready', 'checked_at': '2026-11-16',
                       'market': 'GB', 'result': 'absent'}
        report = workspace.ai_observations({'observations': [observation]}, TODAY)
        self.assertNotIn('brief-ready', report['unobserved_prompts'])
        self.assertEqual(len(report['unobserved_prompts']), 4)
        self.assertIsNone(report['observations'][0]['cited_url'])
        for rows in ([observation, observation], [{**observation, 'answer': 'Example answer'}],
                     [{**observation, 'result': 'cited', 'cited_url': 'https://elsewhere.example/'}]):
            with self.assertRaises(ValueError):
                workspace.ai_observations({'observations': rows}, TODAY)

    def test_sprint_can_clear_review_gates_with_live_evidence_and_four_categories(self):
        from seo_method import PROOF_CATEGORIES, PRIVATE_LABEL, blitz_plan
        page = checked(PRIVATE_LABEL)
        packet = {'page': PRIVATE_LABEL, 'blockers': [], 'eligible_terms': ['private label jewelry manufacturer']}
        dates = {'crawl': '2026-11-16', 'search_through': '2026-11-13'}
        proof = {key: {'category': key, 'pages': [PRIVATE_LABEL]} for key in list(PROOF_CATEGORIES)[:4]}
        result = blitz_plan({page['url']: page}, dates, {'packets': [packet]}, [], proof)
        self.assertEqual(result['status'], 'Ready for human review')
        self.assertEqual(result['proof_categories'], 4)
        self.assertEqual(result['blockers'], [])

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
        self.assertEqual(len(report['terms']), len(ALL_KEYWORDS))
        self.assertTrue(report['alerts'])
        self.assertEqual(report['opportunities'], [])
        self.assertFalse(report['publication_ready'])

    def test_nonrequired_article_404_is_a_warning_and_its_draft_stays_blocked(self):
        path = '/how-to-evaluate-jewelry-manufacturing-partners-a-quality-checklist/'
        retired = checked(path)
        retired.update(http_status=404, issues=['HTTP 404'])
        pages = [checked('/'), retired]
        for include_health in (True, False):
            with self.subTest(include_health=include_health):
                crawl = {'attempted_at': '2026-11-16T00:00:00Z', 'pages': pages}
                if include_health:
                    crawl.update(crawl_health(pages, [], [SITE]))
                report = workspace.build_workspace({}, {}, crawl, {}, today=TODAY)
                alerts = {a['id']: a for a in report['alerts']}
                self.assertNotIn('crawl-blockers', alerts)
                self.assertEqual(alerts['crawl-warnings']['severity'], 'warning')
                packet = next(p for p in report['draft_pack']['packets'] if p['page'] == path)
                self.assertNotEqual(packet['status'], 'draft_for_human_review')
                self.assertTrue(any('crawl' in b.lower() for b in packet['blockers']))
                self.assertFalse(report['publication_ready'])

    def test_required_page_failure_and_optional_request_error_stay_critical(self):
        core = checked('/')
        core.update(http_status=404, issues=['HTTP 404'])
        error = checked('/retired/')
        error.update(crawl_status='error', issues=['Crawl failed: request failed'])
        for pages in ([core], [checked('/'), error]):
            for include_health in (True, False):
                with self.subTest(pages=pages, include_health=include_health):
                    crawl = {'attempted_at': '2026-11-16T00:00:00Z', 'pages': pages}
                    if include_health:
                        crawl.update(crawl_health(pages, [], [SITE]))
                    report = workspace.build_workspace({}, {}, crawl, {}, today=TODAY)
                    alerts = {a['id']: a for a in report['alerts']}
                    self.assertEqual(alerts['crawl-blockers']['severity'], 'critical')


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
