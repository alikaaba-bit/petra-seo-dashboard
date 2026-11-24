from datetime import date, timedelta
import json
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import seo_review_cycle as cycle

TODAY = date(2026, 11, 24)


def snapshot():
    end = TODAY - timedelta(days=3)
    start = end - timedelta(days=27)
    return {
        'site_url': 'https://petrajewelryfactory.com/',
        'period': {'start': start.isoformat(), 'end': end.isoformat(), 'days': 28},
        'overall': {'clicks': 28, 'impressions': 280},
        'daily': [{'date': (start + timedelta(days=i)).isoformat(), 'clicks': 1, 'impressions': 10}
                  for i in range(28)],
        'measurement': {'leads': 'Not connected'},
    }


def workspace():
    return {'alerts': [], 'blitz': {'page': '/private-label/', 'status': 'Held'}, 'followups': []}


class ReviewCycleTests(unittest.TestCase):
    def test_reconciles_property_data_and_rejects_wrong_scope_or_duplicate_rows(self):
        search = snapshot()
        self.assertIsNone(cycle.check_search(search, TODAY))
        search['overall']['clicks'] = 99
        self.assertIn('do not reconcile', cycle.check_search(search, TODAY))
        search['daily'][0]['date'] = search['daily'][1]['date']
        self.assertIn('dates', cycle.check_search(search, TODAY))
        self.assertIn('property', cycle.check_search({'site_url': 'https://example.org/'}, TODAY))

    def test_retries_transient_reads_and_stops_for_access_denial(self):
        run = Mock(side_effect=[TimeoutExpired(['gh'], 10), CompletedProcess([], 0, '{"id":7}', '')])
        delay = Mock()
        self.assertEqual(cycle.read_with_retry(['gh'], run=run, delay=delay), ('{"id":7}', 2))
        delay.assert_called_once()
        run = Mock(return_value=CompletedProcess([], 1, '', 'HTTP 403: permission denied'))
        self.assertEqual(cycle.read_with_retry(['gh'], run=run, delay=Mock()), (None, 1))

    def test_tries_one_fresh_crawl_when_saved_evidence_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / 'data'
            data.mkdir()
            saved = {'attempted_at': '2026-11-18T03:00:00Z', 'status': 'passed', 'pages': []}
            original = data / 'crawl-health.json'
            original.write_text(json.dumps(saved))
            target = Path(tmp) / 'recovery'
            fresh = {**saved, 'attempted_at': '2026-11-24T03:00:00Z'}

            def crawl(args, **kwargs):
                self.assertIn('--crawl-only', args)
                target.mkdir()
                (target / 'crawl-health.json').write_text(json.dumps(fresh))
                return CompletedProcess(args, 0, '', '')

            run = Mock(side_effect=crawl)
            row, result = cycle.recover_crawl(data, target, TODAY, run=run)
            self.assertEqual((row, result), (fresh, 'refreshed'))
            self.assertEqual(json.loads(original.read_text()), saved)
            run.assert_called_once()

    def test_failed_recovery_preserves_last_crawl_and_fresh_inputs_skip_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            saved = {'attempted_at': '2026-11-24', 'status': 'passed'}
            p = data / 'crawl-health.json'
            p.write_text(json.dumps(saved))
            run = Mock(return_value=CompletedProcess([], 1, '', ''))
            self.assertEqual(cycle.recover_crawl(data, data / 'retry', TODAY, run=run), (saved, 'saved'))
            saved.update(status='failed')
            p.write_text(json.dumps(saved))
            self.assertEqual(cycle.recover_crawl(data, data / 'retry', TODAY, run=run), (saved, 'retry_failed'))
            run.assert_called_once()

    def test_tracks_an_open_decision_across_weeks_without_counting_manual_reruns(self):
        search, report = snapshot(), workspace()
        collector = {'conclusion': 'success'}
        initial = cycle.review_state(report, search, collector, {}, TODAY, None, 'saved')
        self.assertEqual(initial['decision']['key'], 'reconcile-enquiries')
        self.assertEqual(initial['decision']['consecutive_weeks'], 1)
        retry = cycle.review_state(report, search, collector, initial, TODAY, None, 'saved')
        self.assertEqual(retry['decision']['consecutive_weeks'], 1)
        following = cycle.review_state(report, search, collector, retry, TODAY + timedelta(days=7), None, 'saved')
        self.assertEqual(following['decision']['consecutive_weeks'], 2)
        self.assertIn('missing', following['decision']['action'])

    def test_learns_from_observed_and_inconclusive_windows_without_claiming_causation(self):
        search, report = snapshot(), workspace()
        search['measurement']['leads'] = 'Connected'
        report['followups'] = [
            {'change_id': 'experiment', 'page': '/private-label/', 'days': 28,
             'status': 'Inconclusive: low sample', 'before': {'clicks': 8}, 'after': {'clicks': 4}},
            {'change_id': 'experiment', 'page': '/private-label/', 'days': 56,
             'status': 'Observed change; not causal proof', 'before': {'clicks': 38}, 'after': {'clicks': 23}},
        ]
        collector = {'conclusion': 'success'}
        first = cycle.review_state(report, search, collector, {}, TODAY, None, 'saved')
        self.assertEqual(first['decision']['key'], 'review-decline')
        self.assertEqual([x['outcome'] for x in first['outcomes']], ['inconclusive', 'decrease'])
        self.assertEqual(first['new_outcomes'], 2)
        second = cycle.review_state(report, search, collector, first, TODAY, None, 'saved')
        self.assertEqual(second['new_outcomes'], 0)
        self.assertIn('causal', cycle.cycle_markdown(first, {}))

    def test_failed_verification_has_priority_over_an_experiment(self):
        failed = cycle.review_state(workspace(), snapshot(), {'conclusion': 'success'}, {},
                                    TODAY, 'Property totals do not reconcile.', 'saved')
        self.assertEqual(failed['decision']['key'], 'verify-search')
        self.assertIn('do not reconcile', failed['decision']['action'])

    def test_reads_last_verified_review_only_after_a_successful_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            prior = Path(tmp)
            report = {'version': 1, 'week_start': '2026-11-09'}
            (prior / 'review-state.json').write_text(json.dumps(report))
            with patch.object(cycle, 'read_with_retry',
                              side_effect=[('{"conclusion":"success"}', 1), ('7', 1), ('', 2)]):
                collector, state, reads = cycle.get_inputs('owner/repo', 'main', prior)
            self.assertEqual(collector['conclusion'], 'success')
            self.assertEqual(state, report)
            self.assertEqual(reads['Prior review artifact'], 2)
            with patch.object(cycle, 'read_with_retry', side_effect=[('broken', 1), ('7', 2), (None, 3)]):
                collector, state, reads = cycle.get_inputs('owner/repo', 'main', prior)
            self.assertEqual(collector, {})
            self.assertEqual(state, {})
            self.assertEqual(reads['Prior review artifact'], 3)


if __name__ == '__main__':
    unittest.main()
