import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import seo_pipeline as pipeline


def checked(url, status=200, issues=None):
    return {'url': url, 'path': pipeline.path_of(url), 'final_url': url,
            'crawl_status': 'checked', 'http_status': status, 'issues': issues or [],
            'text': 'Factory sampling process', 'links': []}


class HealthTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def test_oversize_error_identifies_limit_without_response_body(self):
        response = MagicMock(status_code=200, headers={}, encoding='utf-8')
        response.iter_content.return_value = [b'x' * 4_000_001]
        session = MagicMock()
        session.get.return_value.__enter__.return_value = response
        with self.assertRaises(ValueError) as caught:
            pipeline.request_page(session, pipeline.SITE)
        self.assertEqual(caught.exception.code, 'response_too_large')
        self.assertEqual(caught.exception.details['limit_bytes'], 4_000_000)
        self.assertNotIn('xxxxx', str(caught.exception))

    def test_demo_detection_covers_attributes_entities_and_hidden_payload(self):
        body = '<a href="mailto:hello&#64;outgrid.com">Contact</a><div hidden>Sophie <b>Moore</b></div><script>{"name":"Elliot Ellington"}</script>'
        found = pipeline.placeholder_matches(body)
        self.assertIn('hello@outgrid.com', found)
        self.assertIn('sophie moore', found)
        self.assertIn('elliot ellington', found)
        self.assertEqual(pipeline.placeholder_matches('<p>Factory sampling process</p>'), [])

    def test_fragment_variants_keep_separate_metrics_and_workspaces(self):
        urls = [pipeline.SITE, pipeline.SITE + '#/services']
        current = {'pages': [{'keys': [u], 'impressions': n, 'clicks': n, 'position': 1}
                             for u, n in zip(urls, [8, 1])], 'query_pages': []}
        pages = pipeline.build_pages(current, {'pages': []}, [], {'topics': []})
        self.assertEqual({p['path'] for p in pages}, {'/', '/#/services'})
        self.assertEqual({p['url']: p['current']['clicks'] for p in pages}, dict(zip(urls, [8, 1])))
        collision = pipeline.url_collisions(urls)[0]
        self.assertEqual(collision['request_url'], pipeline.SITE)
        self.assertEqual(set(collision['urls']), set(urls))

    def test_core_404_fails_but_retired_unrequired_404_is_only_a_warning(self):
        root = checked(pipeline.SITE)
        retired = checked(pipeline.SITE + 'old-demo/', 404, ['HTTP 404'])
        report = pipeline.crawl_health([root, retired], [], [pipeline.SITE])
        self.assertEqual(report['status'], 'warning')
        report = pipeline.crawl_health([root, retired], [], [pipeline.SITE, retired['url']])
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(any('HTTP 404' in item for item in report['blockers']))

    def test_missing_required_page_and_empty_crawl_fail_closed(self):
        report = pipeline.crawl_health([], ['Crawl skipped: robots.txt unavailable'], [pipeline.SITE])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['coverage']['html_ok'], 0)
        self.assertIn('not checked', ' '.join(report['blockers']).lower())

    def test_403_blocked_and_non_html_are_never_successful_html_coverage(self):
        pages = [checked(pipeline.SITE, 403, ['HTTP 403']),
                 {'url': pipeline.SITE + 'blocked/', 'crawl_status': 'blocked', 'issues': []},
                 {'url': pipeline.SITE + 'download/', 'http_status': 200, 'crawl_status': 'unsupported', 'issues': []}]
        report = pipeline.crawl_health(pages, [], [p['url'] for p in pages])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['coverage']['html_ok'], 0)
        self.assertEqual(report['coverage']['http_errors'], 1)
        self.assertEqual(report['coverage']['blocked'], 1)
        self.assertEqual(report['coverage']['unsupported'], 1)

    def test_placeholder_on_any_crawled_page_is_a_blocker(self):
        pages = [checked(pipeline.SITE), checked(pipeline.SITE + 'about/', issues=['Template placeholder: sophie moore'])]
        self.assertEqual(pipeline.crawl_health(pages, [], [pipeline.SITE])['status'], 'failed')

    def test_crawl_deduplicates_fragments_and_exposes_discovery_failures(self):
        body = '<title>Factory</title><h1>Factory</h1><a href="#/services">Services</a>'
        def response(session, url):
            if url == pipeline.SITE:
                return 200, body, url, {'Content-Type': 'text/html'}
            return 404, '', url, {'Content-Type': 'text/html'}
        with patch.object(pipeline, 'request_page', side_effect=response) as request, patch('time.sleep'):
            pages, warnings = pipeline.crawl([pipeline.SITE + '#/services'], 10)
        self.assertEqual([p['url'] for p in pages], [pipeline.SITE])
        self.assertEqual(pages[0]['fragment_links'], [pipeline.SITE + '#/services'])
        self.assertEqual(sum(c.args[1] == pipeline.SITE for c in request.call_args_list), 1)
        self.assertIn('robots.txt', ' '.join(warnings))
        self.assertIn('sitemap', ' '.join(warnings).lower())

    def test_oversize_http_200_is_reported_but_never_counts_as_checked(self):
        def response(session, url):
            if url == pipeline.SITE:
                raise pipeline.CrawlError('response_too_large', 'Response exceeds limit', http_status=200, limit_bytes=4_000_000)
            return 404, '', url, {}
        with patch.object(pipeline, 'request_page', side_effect=response), patch('time.sleep'):
            pages, warnings = pipeline.crawl([pipeline.SITE], 1)
        self.assertEqual(pages[0]['http_status'], 200)
        self.assertEqual(pages[0]['error']['limit_bytes'], 4_000_000)
        self.assertEqual(pages[0]['crawl_status'], 'error')
        report = pipeline.crawl_health(pages, warnings, [pipeline.SITE])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['coverage']['html_ok'], 0)

    def test_failed_crawl_check_preserves_inventory_and_search_data_without_auth(self):
        old = {'generated_at': '2026-11-05T00:00:00Z', 'pages': [checked(pipeline.SITE)]}
        (self.output / 'content.json').write_text(json.dumps(old))
        (self.output / 'latest.json').write_text('{"search":"unchanged"}')
        failed = {'url': pipeline.SITE, 'crawl_status': 'error', 'issues': ['Crawl failed: response too large']}
        args = ['seo_pipeline.py', '--crawl-only', '--fail-on-health', '--output-dir', str(self.output)]
        with patch.object(sys, 'argv', args), patch.object(pipeline, 'google_service') as google, patch.object(pipeline, 'crawl', return_value=([failed], [])):
            with self.assertRaises(SystemExit) as result:
                pipeline.main()
        self.assertEqual(result.exception.code, 1)
        google.assert_not_called()
        self.assertEqual(json.loads((self.output / 'content.json').read_text()), old)
        self.assertEqual((self.output / 'latest.json').read_text(), '{"search":"unchanged"}')
        report = json.loads((self.output / 'crawl-health.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['coverage']['errors'], 1)
        self.assertEqual(report['pages'][0]['crawl_status'], 'error')

    def test_successful_crawl_promotes_inventory_without_search_auth(self):
        ed = json.loads((ROOT / 'data/editorial.json').read_text())
        pages = [checked(u) for u in pipeline.required_pages(ed)]
        args = ['seo_pipeline.py', '--crawl-only', '--fail-on-health', '--output-dir', str(self.output)]
        with patch.object(sys, 'argv', args), patch.object(pipeline, 'google_service') as google, patch.object(pipeline, 'crawl', return_value=(pages, [])):
            pipeline.main()
        google.assert_not_called()
        self.assertEqual(json.loads((self.output / 'crawl-health.json').read_text())['status'], 'passed')
        self.assertEqual(json.loads((self.output / 'content.json').read_text())['pages'], pages)
        self.assertFalse((self.output / 'latest.json').exists())

    def test_briefs_and_links_are_withheld_for_failed_pages(self):
        urls = [pipeline.SITE, pipeline.SITE + 'private-label/']
        pages = pipeline.build_pages({'pages': [], 'query_pages': []}, {'pages': []},
                                     [checked(urls[0]), checked(urls[1], 404, ['HTTP 404'])],
                                     {'topics': [{'page': '/private-label/', 'topic': 'Factory sampling', 'business_value': 3}]})
        pipeline.enrich_briefs(pages)
        by_url = {p['url']: p for p in pages}
        blocked = by_url[urls[1]]['brief']
        self.assertEqual(blocked['status'], 'blocked')
        self.assertIsNone(blocked['suggested_title'])
        self.assertEqual(blocked['internal_links'], [])
        self.assertEqual(by_url[urls[0]]['brief']['internal_links'], [])

    def test_fragment_response_is_not_independent_page_evidence(self):
        url = pipeline.SITE + '#/services'
        self.assertTrue(pipeline.brief_blocked({'url': url, 'audit': checked(url)}))

    def test_cross_host_redirect_is_not_requested(self):
        response = MagicMock(status_code=302, headers={'Location': 'https://example.com/'})
        session = MagicMock()
        session.get.return_value.__enter__.return_value = response
        with self.assertRaises(pipeline.CrawlError) as caught:
            pipeline.request_page(session, pipeline.SITE)
        self.assertEqual(caught.exception.code, 'unsafe_redirect')
        self.assertEqual(session.get.call_count, 1)

    def test_unavailable_robots_skips_crawl_and_fails_required_coverage(self):
        with patch.object(pipeline, 'request_page', return_value=(403, '', pipeline.SITE + 'robots.txt', {})) as request:
            pages, warnings = pipeline.crawl([pipeline.SITE])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(pages, [])
        self.assertEqual(pipeline.crawl_health(pages, warnings, [pipeline.SITE])['status'], 'failed')
        self.assertIn('robots.txt returned HTTP 403', warnings[0])

    def test_successful_search_fetch_survives_failed_crawl_with_true_metrics(self):
        old = {'generated_at': '2026-11-05T00:00:00Z', 'pages': [checked(pipeline.SITE)]}
        (self.output / 'content.json').write_text(json.dumps(old))
        def rows(service, dimensions, window):
            if not dimensions:
                return [{'clicks': 24, 'impressions': 240, 'position': 7}]
            if dimensions == ['page']:
                return [{'keys': [pipeline.SITE], 'clicks': 24, 'impressions': 240, 'position': 7}]
            return []
        args = ['seo_pipeline.py', '--crawl', '--fail-on-health', '--inspect-limit', '0', '--output-dir', str(self.output)]
        with patch.object(sys, 'argv', args), patch.object(pipeline, 'google_service'), patch.object(pipeline, 'fetch_rows', side_effect=rows), patch.object(pipeline, 'crawl', return_value=([checked(pipeline.SITE, 403, ['HTTP 403'])], [])):
            with self.assertRaises(SystemExit) as result:
                pipeline.main()
        self.assertEqual(result.exception.code, 1)
        latest = json.loads((self.output / 'latest.json').read_text())
        self.assertEqual(latest['overall']['clicks'], 24)
        root = next(p for p in latest['pages'] if p['url'] == pipeline.SITE)
        self.assertEqual(root['current']['clicks'], 24)
        self.assertEqual(root['brief']['status'], 'blocked')
        self.assertEqual(json.loads((self.output / 'content.json').read_text()), old)


if __name__ == '__main__':
    unittest.main()
