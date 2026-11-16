"""Keep failed lab attempts separate from the last usable Lighthouse results."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from seo_pipeline import ROOT, safe_url, write_json


def summarize(input_dir, output_dir, required_urls=(), collection_failed=False):
    reports, failures = [], []
    if collection_failed:
        failures.append('Lighthouse collection command failed')
    for path in sorted(input_dir.glob('lhr-*.json')):
        try:
            raw = json.loads(path.read_text())
            url = raw.get('finalDisplayedUrl') or raw.get('finalUrl')
            requested = raw.get('requestedUrl') or url
            scores = {k: round(v['score'] * 100) if isinstance(v.get('score'), (int, float)) else None
                      for k, v in raw.get('categories', {}).items()}
            status = raw.get('audits', {}).get('http-status-code', {}).get('numericValue')
            if raw.get('runtimeError') or not url or not safe_url(url) or requested != url or not raw.get('fetchTime') or not scores or any(v is None for v in scores.values()) or (status and status >= 400):
                failures.append(f'{path.name}: runtime, response, redirect or incomplete score failure')
                continue
            reports.append({'url': url, 'fetched_at': raw['fetchTime'], 'scores': scores,
                            'findings': [{'title': a.get('title', ''), 'description': a.get('description', ''), 'value': a.get('displayValue', '')}
                                         for a in raw.get('audits', {}).values() if isinstance(a.get('score'), (int, float)) and a['score'] < 1
                                         and a.get('scoreDisplayMode') not in ('manual', 'notApplicable', 'informative')][:15]})
        except (ValueError, TypeError, KeyError, AttributeError):
            failures.append(f'{path.name}: invalid Lighthouse report')
    if not reports:
        failures.append('No usable Lighthouse reports found')
    failures.extend('Required target not measured: ' + u for u in sorted(set(required_urls) - {r['url'] for r in reports}))
    now = datetime.now(timezone.utc).isoformat()
    attempt = {'attempted_at': now, 'status': 'failed' if failures else 'passed', 'failures': failures,
               'usable_reports': len(reports), 'required_urls': list(required_urls),
               'note': 'Lab measurements only. Failed attempts preserve saved scores and are not field Core Web Vitals.'}
    write_json(output_dir / 'performance-health.json', attempt)
    if not failures:
        write_json(output_dir / 'performance.json', {'generated_at': now, 'reports': reports, 'type': 'Lighthouse mobile lab tests, not field Core Web Vitals'})
    return attempt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT / '.lighthouseci')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--config', type=Path, default=ROOT / '.lighthouserc.json')
    parser.add_argument('--collection-failed', action='store_true')
    args = parser.parse_args()
    required = json.loads(args.config.read_text())['ci']['collect']['url']
    attempt = summarize(args.input_dir, args.output_dir, required, args.collection_failed)
    print(f"Lighthouse attempt: {attempt['status']}; {attempt['usable_reports']} usable reports. See performance-health.json.")
    return 1 if attempt['status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
