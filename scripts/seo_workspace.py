"""Offline editorial decisions, draft packs, drift and weekly review. No publishing or sends."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
from html import escape
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

from seo_pipeline import ROOT, SITE, brief_blocked, crawl_health, required_pages, write_json
from update_data import TARGET_KEYWORDS, ALL_KEYWORDS, HISTORICAL_KEYWORDS, TARGET_PAGES

FACT_FIELDS = {
    'organization_name': 'Public organization name', 'manufacturing_summary': 'Confirmed manufacturing scope',
    'moq': 'Minimum order rules', 'sample_lead_time': 'Sample timing and conditions',
    'production_lead_time': 'Production timing and conditions', 'sales_email': 'Public sales email',
    'phone': 'Public phone', 'address': 'Public address', 'certifications': 'Current certification evidence',
    'sampling_process': 'First-hand sampling process', 'quality_evidence': 'First-hand quality-control evidence',
    'china_manufacturing': 'Manufacturing in China', 'dongguan_manufacturing': 'Manufacturing in Dongguan',
    'stainless_steel': 'Stainless steel capability', 'steel_316l': '316L material evidence',
    'brass': 'Brass capability', 'silver': 'Silver capability', 'sterling_925': '925 silver evidence',
    'pvd': 'PVD process capability', 'gold_plating': 'Gold plating capability', 'rose_gold': 'Rose gold capability',
    'waterproof': 'Waterproof claim and test conditions', 'tarnish_free': 'Tarnish claim and test conditions',
    'lifetime_warranty': 'Warranty policy and exclusions', 'hypoallergenic': 'Hypoallergenic claim evidence',
    'surgical_steel': 'Surgical steel grade evidence', 'nickel_free': 'Nickel claim and test evidence',
    'durability': 'Durability evidence and conditions', 'brand_affiliation': 'Permission for named-brand association',
    'odm': 'ODM design capability', 'white_label': 'White-label capability', 'wholesale': 'Wholesale supply model',
}
CAPABILITIES = set(FACT_FIELDS) - {'organization_name', 'manufacturing_summary', 'moq', 'sample_lead_time',
    'production_lead_time', 'sales_email', 'phone', 'address', 'certifications', 'sampling_process', 'quality_evidence'}
CLAIMS = [('china', 'china_manufacturing'), ('chinese', 'china_manufacturing'), ('dongguan', 'dongguan_manufacturing'),
    ('stainless', 'stainless_steel'), ('316l', 'steel_316l'), ('brass', 'brass'), ('silver', 'silver'),
    ('sterling', 'sterling_925'), ('925', 'sterling_925'), ('pvd', 'pvd'), ('gold plated', 'gold_plating'),
    ('rose gold', 'rose_gold'), ('waterproof', 'waterproof'), ('tarnish', 'tarnish_free'),
    ('lifetime warranty', 'lifetime_warranty'), ('hypoallergenic', 'hypoallergenic'), ('surgical', 'surgical_steel'),
    ('nickel', 'nickel_free'), ('durable', 'durability'), ('long lasting', 'durability'), ('hard jewelry', 'brand_affiliation'),
    ('odm', 'odm'), ('white label', 'white_label'), ('wholesale', 'wholesale'), ('quality', 'quality_evidence'),
    ('premium', 'quality_evidence'), ('luxury', 'quality_evidence'), ('reliable', 'quality_evidence'), ('consistent', 'quality_evidence')]
DRIFT_FIELDS = ('http_status', 'final_url', 'title', 'description', 'canonical', 'robots', 'headings', 'schema_types', 'schema_hash')


def text(value, name, limit=1600):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or re.search(r'[\x00-\x08\x0b-\x1f]', value):
        raise ValueError(f'{name}: supply nonempty text under {limit} characters')
    return value.strip()


def reviewed_date(value, today):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) or date.fromisoformat(value) > today:
        raise ValueError('Review date must be an ISO date, not in the future')
    return value


def public_url(value):
    if not isinstance(value, str) or len(value) > 2000 or re.search(r'[\s\\]', value):
        return False
    try:
        u = urlparse(value)
        host = u.hostname or ''
        if u.scheme != 'https' or not host or u.username or u.password or u.query or u.port not in (None, 443):
            return False
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return not re.fullmatch(r'[0-9.]+', host)
    except ValueError:
        return False


def canonical_path(value):
    if not isinstance(value, str) or not value.startswith('/') or value.startswith('//'):
        return False
    decoded = unquote(value)
    return (not re.search(r'[\s\\?#]', decoded) and not decoded.startswith('//')
            and all(part not in ('.', '..') for part in decoded.split('/'))
            and len(value) < 500)


def validate_fact(key, record, today):
    if key not in FACT_FIELDS or not isinstance(record, dict):
        raise ValueError('Unknown fact field')
    if record.get('status', 'unknown') == 'unknown':
        return {'status': 'unknown', 'value': None}
    if record.get('status') != 'confirmed' or record.get('public_safe') is not True or not public_url(record.get('source_url')):
        raise ValueError(f'{key}: confirmation needs a public-safe source URL without credentials or query tokens')
    clean = {k: text(record.get(k), k) for k in ('value', 'reviewer')}
    clean.update(status='confirmed', public_safe=True, source_url=record['source_url'],
                 reviewed_at=reviewed_date(record.get('reviewed_at'), today))
    if key in CAPABILITIES:
        if not isinstance(record.get('supported'), bool):
            raise ValueError(f'{key}: explicitly state whether this capability is supported')
        clean['supported'] = record['supported']
    if key == 'sales_email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', clean['value']):
        raise ValueError('Invalid public sales email')
    return clean


def confirmed_facts(editorial, today=None):
    today = today or datetime.now(ZoneInfo('America/Los_Angeles')).date()
    result = {}
    for key, record in editorial.get('fact_reviews', {}).items():
        clean = validate_fact(key, record, today)
        if clean['status'] == 'confirmed':
            result[key] = clean
    return result


def seed_term(keyword, category):
    facts = list(dict.fromkeys(['organization_name', 'manufacturing_summary'] + [key for word, key in CLAIMS if word in keyword.lower()]))
    page = '/private-label/' if category == 'private_label' else '/services/'
    if any(word in keyword for word in ('OEM', 'contract', 'manufacturing partner')):
        page = '/contract-manufacturing/'
    page = TARGET_PAGES.get(keyword, page)
    informational = category == 'buyer_preparation'
    return {'keyword': keyword, 'category': category, 'intent': 'informational' if informational else 'commercial',
            'page_type': 'guide' if informational else 'supplier_landing',
            'proposed_page': page, 'approved_page': None, 'required_facts': facts,
            'status': 'hold' if len(facts) > 2 else 'needs_review',
            'reason': 'Capability, location or claim evidence and SERP review required.' if len(facts) > 2 else 'Proposed grouping only; review actual SERP intent and approve the destination.',
            'serp': {'urls': [], 'checked_at': None, 'market': None, 'device': None, 'page_type': None},
            'reviewer': None, 'reviewed_at': None}


def validate_term(keyword, record, today):
    category = next((c for c, terms in TARGET_KEYWORDS.items() if keyword in terms), None)
    if category is None or not isinstance(record, dict):
        raise ValueError('Unknown target term')
    base = seed_term(keyword, category)
    status = record.get('status', base['status'])
    if status not in ('approved', 'needs_review', 'hold'):
        raise ValueError('Invalid term status')
    base.update(status=status, reason=text(record.get('reason', base['reason']), 'Term reason'))
    if status != 'approved':
        return base
    serp = record.get('serp', {})
    urls = serp.get('urls', [])
    intent, page_type = record.get('intent'), record.get('page_type')
    if not isinstance(urls, list) or not 1 <= len(urls) <= 5 or not all(public_url(u) for u in urls):
        raise ValueError('Term approval requires 1–5 public result-page evidence URLs')
    if not canonical_path(record.get('approved_page')):
        raise ValueError('Approve a same-site path without a fragment, query or traversal')
    if intent not in ('commercial', 'informational') or page_type not in ('supplier_landing', 'comparison', 'guide') or serp.get('page_type') != page_type:
        raise ValueError('Selected page type must match the reviewed SERP page type')
    if (intent == 'informational') != (page_type == 'guide'):
        raise ValueError('Review the intent and page-type mismatch')
    if serp.get('device') not in ('desktop', 'mobile'):
        raise ValueError('Record the SERP device')
    base.update(approved_page=record['approved_page'], intent=intent, page_type=page_type,
                reviewer=text(record.get('reviewer'), 'Reviewer', 100), reviewed_at=reviewed_date(record.get('reviewed_at'), today),
                serp={'urls': urls, 'checked_at': reviewed_date(serp.get('checked_at'), today),
                      'market': text(serp.get('market'), 'SERP market', 100), 'device': serp['device'], 'page_type': page_type})
    return base


def term_map(editorial, today):
    reviews = editorial.get('term_reviews', {})
    # Retired reviews stay in the original editorial record without reactivating a target.
    if not isinstance(reviews, dict) or set(reviews) - set(ALL_KEYWORDS) - set(HISTORICAL_KEYWORDS):
        raise ValueError('Term reviews must use the configured target list')
    return [validate_term(keyword, reviews.get(keyword, {}), today) for keyword in ALL_KEYWORDS]


def missing_facts(term, facts):
    return [key for key in term['required_facts'] if key not in facts or
            (key in CAPABILITIES and facts[key].get('supported') is not True)]


def validate_page_review(path, record, today):
    if not canonical_path(path) or not isinstance(record, dict) or record.get('public_safe') is not True or not public_url(record.get('source_url')):
        raise ValueError('Page review needs a canonical path and public-safe first-hand evidence URL')
    clean = {k: text(record.get(k), k) for k in ('buyer_problem', 'first_hand_evidence', 'hypothesis', 'reviewer')}
    if record.get('working_title'):
        clean['working_title'] = text(record['working_title'], 'Working title', 200)
    return {**clean, 'source_url': record['source_url'], 'public_safe': True,
            'reviewed_at': reviewed_date(record.get('reviewed_at'), today)}


def draft_pack(editorial, terms, pages, today):
    facts = confirmed_facts(editorial, today)
    reviews = {p: validate_page_review(p, r, today) for p, r in editorial.get('page_reviews', {}).items()}
    topics = {t['page']: t['topic'] for t in editorial.get('topics', [])}
    by_url = {p['url']: p for p in pages}
    packets = []
    paths = sorted({t['approved_page'] or t['proposed_page'] for t in terms})
    for path in paths:
        group = [t for t in terms if (t['approved_page'] or t['proposed_page']) == path]
        eligible = [t for t in group if t['status'] == 'approved' and not missing_facts(t, facts)]
        blockers = []
        if not eligible:
            blockers.append('No term has both reviewed SERP intent and the required confirmed facts.')
        if path not in reviews:
            blockers.append('Add a reviewed buyer problem, first-hand evidence and measurement hypothesis.')
        page = by_url.get(urljoin(SITE, path), {})
        if brief_blocked({'url': urljoin(SITE, path), 'audit': page}):
            blockers.append('Verify the exact live destination: crawl, redirect, indexability or demo checks are unresolved.')
        title = reviews.get(path, {}).get('working_title') or topics.get(path) or 'Page purpose needs review'
        if title == 'Page purpose needs review':
            blockers.append('Supply a reviewed working title; target terms are not approved factual copy.')
        packet = {'page': path, 'topic': title, 'status': 'hold' if blockers else 'draft_for_human_review',
                  'blockers': blockers, 'terms': [t['keyword'] for t in group], 'eligible_terms': [t['keyword'] for t in eligible],
                  'missing_facts': sorted({k for t in group for k in missing_facts(t, facts)}),
                  'page_review': reviews.get(path), 'suggested_title': None, 'suggested_description': None,
                  'outline': ['Answer the reviewed buyer problem', 'Explain confirmed scope and limits',
                              'Show first-hand process and quality evidence', 'Explain confirmed sampling and production conditions',
                              'State what a brand should provide to request a quote'],
                  'evidence': [{'keyword': t['keyword'], **t['serp']} for t in eligible],
                  'confirmed_facts': {k: facts[k] for k in sorted({k for t in eligible for k in t['required_facts']})},
                  'measurement': 'Log the actual human publication date. Review equal 28/56-day windows; either window below 20 clicks is inconclusive. Observed change is not causation.'}
        if not blockers:
            packet['suggested_title'] = f"{title} | {facts['organization_name']['value']}"
            packet['suggested_description'] = facts['manufacturing_summary']['value']
        packets.append(packet)
    schema = None
    if 'organization_name' in facts:
        schema = {'@context': 'https://schema.org', '@type': 'Organization', '@id': SITE + '#organization',
                  'name': facts['organization_name']['value'], 'url': SITE}
        for key, prop in (('sales_email', 'email'), ('phone', 'telephone')):
            if key in facts:
                schema[prop] = facts[key]['value']
    ready = [p for p in packets if p['status'] == 'draft_for_human_review']
    llms = None
    if ready and 'manufacturing_summary' in facts:
        llms = '# ' + escape(facts['organization_name']['value']) + '\n\n' + escape(facts['manufacturing_summary']['value']) + '\n\n## Public pages\n' + '\n'.join('- [' + escape(p['topic']).replace('[', '').replace(']', '') + '](' + urljoin(SITE, p['page']) + ')' for p in ready) + '\n'
    return {'status': 'draft_only', 'packets': packets, 'organization_schema': schema, 'llms_txt': llms,
            'unknown_facts': [k for k in FACT_FIELDS if k not in facts],
            'note': 'Planning packets are not publication approval. Validate schema against visible confirmed facts; llms.txt is optional and is not a Google Search requirement.'}


def baseline_snapshot(crawl):
    pages = [{k: p[k] for k in ('url', 'crawl_status', 'issues', *DRIFT_FIELDS) if k in p} for p in crawl.get('pages', [])]
    return {'captured_at': crawl.get('attempted_at') or crawl.get('generated_at'), 'pages': pages,
            'quality': 'observed_problems' if not pages or any(p.get('crawl_status') != 'checked' or p.get('http_status') != 200 or p.get('issues') for p in pages) else 'observed_only',
            'note': 'Observed baseline, never automatically approved as known good.',
            'id': hashlib.sha256(json.dumps(pages, sort_keys=True).encode()).hexdigest()[:16]}


def compare_drift(before, after):
    baseline = before if 'captured_at' in before else baseline_snapshot(before)
    current = {p['url']: p for p in after.get('pages', [])}
    findings = []
    after_at = after.get('attempted_at') or after.get('generated_at')
    if not baseline.get('captured_at') or not after_at or after_at < baseline['captured_at']:
        return {'baseline_at': baseline.get('captured_at'), 'compared_at': after_at,
                'findings': [{'kind': 'not_checked', 'field': 'chronology', 'severity': 'warning',
                              'url': SITE, 'before': baseline.get('captured_at'), 'after': after_at}],
                'note': 'Use a dated baseline followed by a newer crawl; no drift conclusion is available.'}
    for old in baseline.get('pages', []):
        new = current.get(old['url'])
        if not new or new.get('crawl_status') != 'checked':
            findings.append({'url': old['url'], 'kind': 'not_checked', 'field': 'coverage', 'severity': 'warning',
                             'before': old.get('crawl_status'), 'after': new.get('crawl_status') if new else None})
            continue
        for field in DRIFT_FIELDS:
            if field not in old or field not in new or old[field] == new[field]:
                continue
            critical = field in ('canonical', 'final_url') or (field == 'http_status' and new[field] >= 400) or (field == 'robots' and any('noindex' in r for r in new[field]))
            findings.append({'url': old['url'], 'kind': 'changed', 'field': field,
                             'severity': 'critical' if critical else 'warning', 'before': old[field], 'after': new[field]})
    return {'baseline_at': baseline.get('captured_at'), 'baseline_quality': baseline.get('quality'),
            'compared_at': after.get('attempted_at') or after.get('generated_at'), 'findings': findings,
            'note': 'Review changes against the intended publication. No automatic rollback, redirect or canonical edit.'}


def followups(changes, search, today):
    result, cutoff = [], search.get('period', {}).get('end')
    for change in changes:
        published = date.fromisoformat(change['published_at'])
        saved = next((r for r in search.get('change_results', []) if r.get('change', {}).get('id') == change['id']
                      and r['change'].get('page') == change['page'] and r['change'].get('published_at') == change['published_at']), {})
        for days in (28, 56):
            end = published + timedelta(days=days - 1)
            earliest = end + timedelta(days=3)
            window = next((w for w in saved.get('windows', []) if w.get('days') == days and w.get('before') is not None and w.get('after') is not None), None)
            if window:
                status = window['status']
            elif earliest > today:
                status = 'Collecting data'
            elif not cutoff or cutoff < end.isoformat():
                status = 'Awaiting finalized GSC refresh'
            else:
                status = 'Due for calculation'
            result.append({'change_id': change['id'], 'page': change['page'], 'days': days,
                           'window_end': end.isoformat(), 'earliest_check_on': earliest.isoformat(), 'status': status,
                           'before': window.get('before') if window else None, 'after': window.get('after') if window else None})
    return result


def stale(value, today, days):
    try:
        return (today - date.fromisoformat(value[:10])).days > days
    except (TypeError, ValueError):
        return True


def build_workspace(editorial, search, crawl, performance, baseline=None, browser=None, today=None, lab_attempt=None):
    today = today or datetime.now(ZoneInfo('America/Los_Angeles')).date()
    terms = term_map(editorial, today)
    facts = confirmed_facts(editorial, today)
    for term in terms:
        term['missing_facts'] = missing_facts(term, facts)
    crawl_at = crawl.get('attempted_at') or crawl.get('generated_at')
    pack = draft_pack(editorial, terms, [] if stale(crawl_at, today, 3) else crawl.get('pages', []), today)
    due = followups(editorial.get('changes', []), search, today)
    sources = {'search': search.get('generated_at'), 'search_through': search.get('period', {}).get('end'),
               'crawl': crawl.get('attempted_at') or crawl.get('generated_at'), 'lab': performance.get('generated_at'),
               'browser': (browser or {}).get('attempted_at')}
    alerts = []
    def alert(key, severity, message, action, owner):
        alerts.append({'id': key, 'severity': severity, 'message': message, 'next_action': action, 'owner': owner})
    if stale(sources['search'], today, 3):
        alert('search-stale', 'critical', 'Search evidence is stale or unavailable.', 'Inspect the existing Actions failure and exact GSC property access. Isolate email with approval before access recovery.', 'Account owner')
    if stale(sources['crawl'], today, 3):
        alert('crawl-stale', 'warning', 'Crawl evidence is stale or unavailable.', 'Run the bounded crawl-only check.', 'SEO operator')
    health = crawl
    if crawl.get('status') not in ('passed', 'warning', 'failed') and crawl.get('pages'):
        health = crawl_health(crawl['pages'], crawl.get('warnings', []), required_pages(editorial))
    if health.get('status') == 'failed':
        alert('crawl-blockers', 'critical', 'Live page or coverage blockers need review.', 'Identify the serving CMS/repo and repair approved destinations; verify in a browser.', 'Website owner')
    elif health.get('status') == 'warning' or any(brief_blocked({'url': p['url'], 'audit': p}) for p in crawl.get('pages', [])):
        alert('crawl-warnings', 'warning', 'Crawl findings need review; affected pages remain held from drafts and link suggestions.', 'Review crawl-health.json warnings and page findings; retain holds for unavailable pages.', 'Website owner')
    if stale(sources['lab'], today, 8):
        alert('lab-stale', 'warning', 'Lighthouse lab evidence is stale or unavailable.', 'Review runner access and approved URL targets before a manual lab check.', 'Technical maintainer')
    if (lab_attempt or {}).get('status') == 'failed':
        alert('lab-failed', 'warning', 'Latest Lighthouse attempt failed; older scores were preserved.', 'Inspect performance-health.json and the workflow artifact before interpreting scores.', 'Technical maintainer')
    if not browser or stale(sources['browser'], today, 3) or browser.get('status') != 'passed':
        alert('browser-check', 'warning', 'Rendered-page checks are missing, stale or have findings.', 'Run the bounded browser smoke check; inspect raw and visible demo strings.', 'Website owner')
    pending = sum(t['status'] != 'approved' or bool(t['missing_facts']) for t in terms)
    if pending:
        alert('term-review', 'warning', f'{pending} target terms need intent review or confirmed facts.', 'Review grouped page briefs; approve only evidence-backed destinations.', 'SEO lead and operations owner')
    if not editorial.get('changes'):
        alert('publication-log', 'info', 'No publication records are available for follow-up.', 'After a human publish, verify the URL, log the actual date, export and dry-run the reviewed import.', 'Publisher')
    if any(r['status'].startswith(('Awaiting', 'Due')) for r in due):
        alert('followups-due', 'warning', 'Publication follow-ups need data or calculation.', 'Refresh finalized data after access recovery; retain inconclusive/non-causal wording.', 'SEO operator')
    drift = compare_drift(baseline, crawl) if baseline else {'findings': [], 'note': 'No baseline supplied. Capture the observed pre-change state before a human publish.'}
    if drift['findings']:
        alert('drift-review', 'warning', f"{len(drift['findings'])} drift or coverage findings need review.", 'Compare with the approved change; do not automatically change routing or canonicals.', 'Publisher')
    opportunities = sorted([{'page': p['path'], 'query': q['query'], 'impressions': q['impressions'], 'clicks': q.get('clicks'),
                              'position': q.get('position'), 'search_generated_at': sources['search'], 'status': 'Review candidate'}
                             for p in search.get('pages', []) for q in p.get('queries', [])
                             if not q.get('branded') and q.get('impressions', 0) >= 20 and 4 <= (q.get('position') or 0) <= 20],
                            key=lambda q: q['impressions'], reverse=True)[:10]
    return {'version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(), 'sources': sources, 'terms': terms,
            'fact_fields': FACT_FIELDS, 'capability_fields': sorted(CAPABILITIES), 'facts': facts, 'draft_pack': pack,
            'followups': due, 'alerts': alerts, 'drift': drift, 'opportunities': opportunities,
            'publication_ready': False, 'note': 'This workspace measures, briefs and checks. A person approves and publishes.'}


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else ({} if default is None else default)


def latest_crawl(data_dir, explicit=None):
    if explicit:
        return read_json(explicit)
    attempt, inventory = read_json(data_dir / 'crawl-health.json'), read_json(data_dir / 'content.json')
    return attempt if attempt.get('attempted_at', '') >= inventory.get('generated_at', '') and attempt.get('attempted_at') else inventory


def write_workspace(editorial, data_dir, output_dir, crawl=None, baseline=None, browser=None):
    report = build_workspace(editorial, read_json(data_dir / 'latest.json'), crawl if crawl is not None else latest_crawl(data_dir),
                             read_json(data_dir / 'performance.json'), baseline, browser or read_json(data_dir / 'browser-check.json'),
                             lab_attempt=read_json(data_dir / 'performance-health.json'))
    write_json(output_dir / 'workspace.json', report)
    write_json(output_dir / 'draft-pack.json', report['draft_pack'])
    lines = ['# Weekly SEO review', '', 'Draft planning output. Human approval and publication required.', '',
             '## Source dates', '```json', json.dumps(report['sources'], indent=2), '```', '', '## Actions']
    lines.extend(f"- {a['severity']}: {a['message']} {a['next_action']} Owner: {a['owner']}." for a in report['alerts'])
    for packet in report['draft_pack']['packets']:
        lines.extend(['', '## ' + packet['page'], 'Status: ' + packet['status'], *['- HOLD: ' + b for b in packet['blockers']],
                      'Terms: ' + ', '.join(packet['terms']), 'Unknown facts: ' + ', '.join(packet['missing_facts']),
                      *['- ' + item for item in packet['outline']], packet['measurement']])
    (output_dir / 'weekly-review.md').write_text('\n'.join(lines) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--editorial', type=Path, default=ROOT / 'data/editorial.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'tmp/workspace')
    parser.add_argument('--crawl-report', type=Path)
    parser.add_argument('--baseline-file', type=Path)
    parser.add_argument('--save-baseline', type=Path, help='Write a new observed baseline; refuses to overwrite')
    args = parser.parse_args()
    crawl = latest_crawl(args.data_dir, args.crawl_report)
    if args.save_baseline:
        if not crawl.get('pages') or not (crawl.get('attempted_at') or crawl.get('generated_at')):
            raise ValueError('A dated crawl is required for a baseline')
        args.save_baseline.parent.mkdir(parents=True, exist_ok=True)
        with args.save_baseline.open('x') as out:
            json.dump(baseline_snapshot(crawl), out, indent=2)
    if args.baseline_file and not args.baseline_file.exists():
        raise ValueError('Baseline file does not exist')
    report = write_workspace(read_json(args.editorial), args.data_dir, args.output_dir, crawl,
                             read_json(args.baseline_file) if args.baseline_file else None)
    print(f"Prepared {len(report['terms'])} term dispositions, {len(report['draft_pack']['packets'])} grouped planning packets and {len(report['alerts'])} review alerts. No search refresh or publishing performed.")


if __name__ == '__main__':
    main()
