"""Publish compact lab results, keeping full reports in workflow artifacts."""
from datetime import datetime, timezone
import json
from pathlib import Path
from seo_pipeline import ROOT, safe_url, write_json

reports = []
for path in sorted((ROOT / '.lighthouseci').glob('lhr-*.json')):
    raw = json.loads(path.read_text())
    url = raw.get('finalDisplayedUrl') or raw.get('finalUrl')
    if not url or not safe_url(url):
        continue
    reports.append({'url': url, 'fetched_at': raw.get('fetchTime'),
                    'scores': {k: round(v['score'] * 100) if v.get('score') is not None else None for k, v in raw.get('categories', {}).items()},
                    'findings': [{'title': a['title'], 'description': a.get('description', ''), 'value': a.get('displayValue', '')} for a in raw.get('audits', {}).values() if a.get('score') is not None and a['score'] < 1 and a.get('scoreDisplayMode') not in ('manual', 'notApplicable', 'informative')][:15]})
if not reports:
    raise RuntimeError('No Lighthouse reports found; preserving existing performance data')
write_json(ROOT / 'data/performance.json', {'generated_at': datetime.now(timezone.utc).isoformat(), 'reports': reports, 'type': 'Lighthouse mobile lab tests, not field Core Web Vitals'})
print(f'Saved {len(reports)} Lighthouse reports')
