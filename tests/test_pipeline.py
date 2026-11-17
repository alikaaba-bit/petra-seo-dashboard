import io
import json
import sys
import tempfile
import traceback
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from seo_pipeline import period, metrics, fetch_rows, build_pages, overlap_candidates, PageHTML, safe_url, change_results, SITE, main
import update_data


def row(keys, impressions=100, clicks=5, position=10):
    return {'keys': keys, 'impressions': impressions, 'clicks': clicks, 'position': position}


class PipelineTests(unittest.TestCase):
    def test_inclusive_periods_do_not_overlap(self):
        current = period(28, date(2026, 9, 4))
        previous = period(28, date(2026, 8, 7))
        self.assertEqual(current['start'], '2026-08-08')
        self.assertEqual(previous['end'], '2026-08-07')
        self.assertEqual(period(7, date(2026, 9, 4))['start'], '2026-08-29')

    def test_metrics_are_weighted_not_daily_averages(self):
        result = metrics([row([], 100, 10, 2), row([], 1, 0, 100)])
        self.assertEqual(result['position'], 2.97)
        self.assertEqual(result['ctr'], 9.901)
        self.assertIsNone(metrics([])['position'])

    def test_pagination_and_final_data(self):
        service = MagicMock()
        service.searchanalytics().query().execute.side_effect = [{'rows': [row(['x'])] * 25000}, {'rows': [row(['last'])]}]
        rows = fetch_rows(service, ['query'], period(28, date(2026, 9, 4)))
        self.assertEqual(len(rows), 25001)
        bodies = [c.kwargs['body'] for c in service.searchanalytics().query.call_args_list if 'body' in c.kwargs]
        self.assertEqual([b['startRow'] for b in bodies], [0, 25000])
        self.assertEqual(bodies[0]['dataState'], 'final')

    def test_api_failure_does_not_become_zero_metrics(self):
        service = MagicMock()
        service.searchanalytics().query().execute.side_effect = RuntimeError('API unavailable')
        with self.assertRaises(RuntimeError):
            fetch_rows(service, ['query'], period(28, date(2026, 9, 4)))

    def test_active_targets_exclude_claims_and_keep_historical_configuration(self):
        active = update_data.ALL_KEYWORDS
        self.assertEqual(len(active), len(set(active)))
        self.assertTrue(set(update_data.HIGH_PRIORITY).issubset(active))
        self.assertEqual(len(update_data.HIGH_PRIORITY), 6)
        historical = [term for terms in update_data.HISTORICAL_TARGET_KEYWORDS.values() for term in terms]
        self.assertEqual(len(historical), 50)
        for pattern in ('hard jewelry', '316l', 'waterproof', 'tarnish free', 'lifetime warranty',
                        'hypoallergenic', 'nickel free', 'surgical steel', 'sterling', '925', 'pvd'):
            self.assertFalse(any(pattern in term.lower() for term in active), pattern)
        self.assertIn('316L stainless steel jewelry supplier', historical)
        self.assertIn('stainless steel jewellery manufacturer', active)

    def test_failed_refresh_records_sanitized_health_without_overwriting_observations(self):
        class FakeHttpError(Exception):
            resp = type('Response', (), {'status': 403})()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            saved = {'generated_at': '2026-11-05T00:00:00+00:00',
                     'period': {'start': '2026-10-06', 'end': '2026-11-02', 'days': 28},
                     'queries': [{'query': 'old observed term', 'clicks': 8}]}
            snapshot = json.dumps(saved).encode()
            (output / 'latest.json').write_bytes(snapshot)
            (output / 'history_2026-11-05.json').write_bytes(snapshot)
            service = MagicMock()
            service.searchanalytics().query().execute.side_effect = FakeHttpError('PRIVATE_ERROR_PAYLOAD')
            stdout = io.StringIO()
            with patch.object(sys, 'argv', ['seo_pipeline.py', '--output-dir', directory]), \
                    patch('seo_pipeline.google_service', return_value=service), \
                    patch('seo_workspace.write_workspace') as workspace, redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as exit_result:
                    main()
            self.assertEqual(exit_result.exception.code, 1)
            workspace.assert_not_called()
            self.assertEqual((output / 'latest.json').read_bytes(), snapshot)
            self.assertEqual((output / 'history_2026-11-05.json').read_bytes(), snapshot)
            health_text = (output / 'search-health.json').read_text()
            health = json.loads(health_text)
            self.assertEqual(health['status'], 'failed')
            self.assertEqual(health['error']['http_status'], 403)
            self.assertEqual(health['last_successful_snapshot']['period']['end'], '2026-11-02')
            self.assertNotEqual(health['attempted_at'], saved['generated_at'])
            self.assertNotIn('PRIVATE_ERROR_PAYLOAD', health_text + stdout.getvalue())

    def test_successful_refresh_keeps_observed_queries_outside_active_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            service = MagicMock()
            service.searchanalytics().query().execute.return_value = {'rows': []}

            def rows_for_dimensions(_service, dimensions, _window):
                return [row(['316L stainless steel jewelry supplier'], 7, 1, 12)] if dimensions == ['query'] else []

            with patch.object(sys, 'argv', ['seo_pipeline.py', '--output-dir', directory, '--inspect-limit', '0']), \
                    patch('seo_pipeline.google_service', return_value=service), \
                    patch('seo_pipeline.fetch_rows', side_effect=rows_for_dimensions), \
                    patch('seo_pipeline.change_results', return_value=[]), \
                    patch('seo_workspace.write_workspace'), redirect_stdout(io.StringIO()):
                main()
            saved = json.loads((Path(directory) / 'latest.json').read_text())
            health = json.loads((Path(directory) / 'search-health.json').read_text())
            self.assertEqual(saved['queries'][0]['clicks'], 1)
            self.assertNotIn('316L stainless steel jewelry supplier', saved['tracked_keywords'])
            self.assertEqual(set(saved['tracked_keywords']), set(update_data.ALL_KEYWORDS))
            self.assertEqual(health['status'], 'success')
            self.assertIsNone(health['error'])
            self.assertEqual(health['last_successful_snapshot']['period'], saved['period'])

    def test_diagnostic_write_failure_suppresses_sensitive_exception_chain(self):
        class FakeHttpError(Exception):
            resp = type('Response', (), {'status': 403})()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            snapshot = b'{"generated_at":"2026-11-05T00:00:00+00:00"}'
            (output / 'latest.json').write_bytes(snapshot)
            stdout = io.StringIO()
            caught = None
            rendered_traceback = ''
            with patch.object(sys, 'argv', ['seo_pipeline.py', '--output-dir', directory]), \
                    patch('seo_pipeline.google_service', side_effect=FakeHttpError('SENSITIVE_ORIGINAL_PAYLOAD')), \
                    patch('seo_pipeline.write_json', side_effect=PermissionError('SENSITIVE_WRITE_PAYLOAD')), \
                    patch('seo_workspace.write_workspace') as workspace, redirect_stdout(stdout):
                try:
                    main()
                except BaseException as error:
                    caught = error
                    rendered_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            self.assertIsInstance(caught, SystemExit)
            self.assertEqual(caught.code, 1)
            self.assertTrue(caught.__suppress_context__)
            self.assertEqual(stdout.getvalue(), 'Search Console refresh failed (FakeHttpError; HTTP 403); diagnostic-write-failed.\n')
            for marker in ('SENSITIVE_ORIGINAL_PAYLOAD', 'SENSITIVE_WRITE_PAYLOAD'):
                self.assertNotIn(marker, stdout.getvalue() + rendered_traceback)
            self.assertEqual((output / 'latest.json').read_bytes(), snapshot)
            self.assertFalse((output / 'search-health.json').exists())
            workspace.assert_not_called()

    def test_pages_use_page_totals_not_partial_query_totals(self):
        url = SITE + 'private-label/'
        current = {'pages': [row([url], 200, 10)], 'query_pages': [row(['private label jewelry', url], 20, 2)]}
        pages = build_pages(current, {'pages': []}, [], {'topics': []})
        self.assertEqual(pages[0]['current']['impressions'], 200)
        self.assertEqual(pages[0]['queries'][0]['impressions'], 20)
        self.assertEqual(pages[0]['index_status'], 'Not inspected')

    def test_low_data_does_not_become_confident_recommendation(self):
        url = SITE + 'private-label/'
        pages = build_pages({'pages': [row([url], 10, 0)], 'query_pages': []}, {'pages': []}, [], {'topics': []})
        self.assertEqual(pages[0]['confidence'], 'Low sample')

    def test_root_aliases_do_not_create_duplicate_page_workspaces(self):
        current = {'pages': [row([SITE], 20), row([SITE.rstrip('/')], 10)], 'query_pages': []}
        inventory = [{'url': SITE, 'issues': []}, {'url': SITE.rstrip('/'), 'issues': []}]
        pages = build_pages(current, {'pages': []}, inventory, {'topics': []})
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]['current']['impressions'], 30)

    def test_overlap_is_only_a_review_candidate(self):
        rows = [row(['private label', SITE], 20), row(['private label', SITE+'private-label/'], 20), row(['petra', SITE], 100), row(['petra', SITE+'about/'], 100)]
        result = overlap_candidates(rows)
        self.assertEqual(len(result), 1)
        self.assertIn('not cannibalization', result[0]['verdict'])

    def test_crawl_host_boundary(self):
        for url in ('http://petrajewelryfactory.com/', 'https://evil.com/', 'https://petrajewelryfactory.com.evil.com/', 'https://user@petrajewelryfactory.com/'):
            self.assertFalse(safe_url(url))
        self.assertTrue(safe_url(SITE+'private-label/'))

    def test_html_extracts_metadata_without_script_text(self):
        p = PageHTML(SITE)
        p.feed('<title>Factory</title><meta name="description" content="Custom"><meta name="robots" content="noindex"><h1>Jewelry <em>manufacturing</em></h1><a href="/private-label/">Private label</a><script>secret</script>')
        self.assertEqual(p.title, 'Factory')
        self.assertEqual(p.headings[0]['text'], 'Jewelry manufacturing')
        self.assertEqual(p.links, [SITE+'private-label/'])
        self.assertNotIn('secret', p.text)

    def test_change_followup_waits_for_full_window(self):
        service = MagicMock()
        result = change_results(service, [{'id':'a','page':'/private-label/','published_at':'2026-09-01'}], date(2026, 9, 4))
        self.assertEqual(result[0]['windows'][0]['status'], 'Collecting data')
        service.searchanalytics.assert_not_called()

    def test_before_after_uses_nonoverlapping_windows(self):
        service = MagicMock()
        service.searchanalytics().query().execute.return_value = {'rows':[row([], 100, 2)]}
        result = change_results(service, [{'id':'a','page':'/private-label/','published_at':'2026-08-01'}], date(2026, 9, 4))
        self.assertEqual(result[0]['windows'][0]['status'], 'Inconclusive: low sample')
        bodies = [c.kwargs['body'] for c in service.searchanalytics().query.call_args_list if 'body' in c.kwargs]
        self.assertEqual(bodies[0]['endDate'], '2026-07-31')
        self.assertEqual(bodies[1]['startDate'], '2026-08-01')
        self.assertEqual(bodies[1]['endDate'], '2026-08-28')


if __name__ == '__main__':
    unittest.main()
