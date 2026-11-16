"""Bounded, read-only rendered-page checks using the already installed Chrome wrapper."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse
from seo_pipeline import ROOT, SITE, PLACEHOLDERS, safe_url, write_json


def decode_result(output):
    line = next((line[8:] for line in output.splitlines() if line.startswith('result: ')), None)
    if line is None:
        raise ValueError('Browser returned no structured result')
    value = json.loads(line)
    for _ in range(3):
        if not isinstance(value, str):
            break
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError('Invalid browser result')
    return value


def evaluate_page(raw, requested):
    findings = []
    if not safe_url(raw.get('url', '')) or raw.get('url') != requested:
        findings.append('Unexpected browser destination; review routing')
    for key in ('raw_matches', 'visible_matches'):
        findings.extend(key + ': ' + marker for marker in raw.get(key, []))
    if not raw.get('title'):
        findings.append('Missing rendered title')
    if len(raw.get('h1', [])) != 1:
        findings.append('Expected one rendered H1')
    if not raw.get('description'):
        findings.append('Missing rendered description')
    if not raw.get('canonical'):
        findings.append('Missing canonical')
    if raw.get('visible_characters', 0) < 100:
        findings.append('Very little rendered text; inspect manually')
    if urlparse(requested).fragment:
        findings.append('Fragment route requires a canonical destination decision')
    return {'requested_url': requested, **raw, 'findings': findings,
            'note': 'Rendered DOM observation, not proof of HTTP status, Google indexing or factual accuracy.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', action='append', help='At most five same-site HTTPS URLs; defaults to homepage')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'tmp/browser-check')
    parser.add_argument('--browser-command', default='chrome-devtools-axi')
    args = parser.parse_args()
    urls = list(dict.fromkeys(args.url or [SITE]))
    if not 1 <= len(urls) <= 5 or any(not safe_url(u) or urlparse(u).query for u in urls):
        parser.error('Supply 1–5 same-site HTTPS URLs without query strings')
    command = shutil.which(args.browser_command)
    if not command:
        parser.error('Chrome wrapper unavailable; use a manual browser review. No installation is attempted.')
    script = '''(() => {
      const markers = MARKERS;
      const clean = s => s.toLowerCase().replace(/\\s+/g, ' ');
      const raw = clean(document.documentElement.outerHTML), visible = clean(document.body?.innerText || '');
      return {url:location.href,title:document.title,
        h1:[...document.querySelectorAll('h1')].filter(n=>n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden').map(n=>n.textContent.trim()).slice(0,10),
        raw_h1_count:document.querySelectorAll('h1').length,
        description:document.querySelector('meta[name="description"]')?.content || '',
        canonical:document.querySelector('link[rel="canonical"]')?.href || '',
        visible_characters:visible.length,
        raw_matches:markers.filter(m=>raw.includes(m)),visible_matches:markers.filter(m=>visible.includes(m))};
    })()'''.replace('MARKERS', json.dumps(PLACEHOLDERS))
    pages = []
    for url in urls:
        try:
            subprocess.run([command, 'open', url], capture_output=True, text=True, check=True, timeout=45)
            output = subprocess.run([command, 'eval', script], capture_output=True, text=True, check=True, timeout=30)
            pages.append(evaluate_page(decode_result(output.stdout), url))
        except (subprocess.SubprocessError, ValueError, OSError):
            pages.append({'requested_url': url, 'findings': ['Browser check failed; no clean result is assumed']})
    report = {'attempted_at': datetime.now(timezone.utc).isoformat(),
              'status': 'failed' if any(p['findings'] for p in pages) else 'passed', 'pages': pages,
              'scope': 'Bounded rendered DOM smoke check; no forms submitted or site changes made'}
    write_json(args.output_dir / 'browser-check.json', report)
    print(f"Browser check: {report['status']}; {len(pages)} URLs examined. Report: {args.output_dir / 'browser-check.json'}")
    return int(report['status'] == 'failed')


if __name__ == '__main__':
    raise SystemExit(main())
