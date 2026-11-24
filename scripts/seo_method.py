"""Prioritize observed SEO work and prepare one review-only page sprint."""
from html import escape
import re
from urllib.parse import urljoin, urlparse

from seo_pipeline import SITE, brief_blocked, safe_url

CHECKLIST = '/how-to-evaluate-jewelry-manufacturing-partners-a-quality-checklist/'
PRIVATE_LABEL = '/private-label/'
CONTRACT = '/contract-manufacturing/'
STEEL = '/stainless-steel-jewelry-manufacturer/'
TIERS = ('Fatal', 'Revenue', 'Compounding', 'Fluff')
PROOF_CATEGORIES = {
    'process_test': 'Process or quality-control test',
    'customer_outcome': 'Customer outcome cleared for public use',
    'original_media': 'Original factory or sample photo or video',
    'aggregate_data': 'Approved aggregate production data',
    'qc_edge_case': 'Sampling or quality-control edge case',
}
JOURNEY = (
    ('quality-problems', 'Unaware', 'Work out why samples and production pieces differ.',
     'Why do jewelry samples and production pieces finish differently?',
     'What should a jewelry product developer compare when an approved sample differs from a production piece?',
     '/resources/stainless-steel-sample-approval/'),
    ('supplier-evaluation', 'Problem-aware', 'Evaluate a new manufacturing partner.',
     'how to evaluate a jewelry manufacturer',
     'Build a due diligence checklist for a brand evaluating jewelry factories. What evidence should a buyer request?',
     CHECKLIST),
    ('manufacturing-models', 'Solution-aware', 'Choose a manufacturing model for the collection.',
     'private label vs OEM jewelry manufacturing',
     'Which questions help a brand choose between private label and OEM jewelry manufacturing?',
     CONTRACT),
    ('private-label-shortlist', 'Product-aware', 'Shortlist factories and compare fit.',
     'private label jewelry manufacturer China',
     'Compare evidence a brand can use to shortlist private label jewelry manufacturers in China. Cite the factory pages you use.',
     PRIVATE_LABEL),
    ('brief-ready', 'Most-aware', 'Prepare a sampling or quote discussion.',
     'jewelry manufacturing brief template',
     'What should a brand include in its brief for an OEM stainless steel jewelry factory?',
     '/resources/jewelry-manufacturing-brief/'),
)
LINK_CANDIDATES = (
    (CHECKLIST, PRIVATE_LABEL, 'private label jewelry manufacturing', 'Place beside the supplier shortlisting criteria.'),
    ('/how-it-works/', PRIVATE_LABEL, 'start with a private label collection', 'Use where the process explains how to select an approach.'),
    ('/resources/jewelry-manufacturing-brief/', PRIVATE_LABEL, 'private label collection brief', 'Use where the guide discusses selecting a base design.'),
    ('/resources/jewelry-manufacturing-brief/', CONTRACT, 'custom and OEM jewelry manufacturing', 'Use where the buyer brings an original design.'),
    ('/resources/stainless-steel-sample-approval/', STEEL, 'stainless steel jewelry manufacturing', 'Use beside the sample specification checklist.'),
    ('/resources/stainless-steel-material-specification/', STEEL, 'discuss stainless steel jewelry production', 'Use at the next step after a specification review.'),
    (PRIVATE_LABEL, '/catalog/', 'request the private label catalog', 'Check the next step for a buyer choosing designs.'),
    (CONTRACT, '/contact/', 'discuss your manufacturing brief', 'Check the next step for a buyer with an original design.'),
)


def crawl_routes(pages):
    return {p['url']: p for p in pages if safe_url(p['url']) and
            not (urlparse(p['url']).query or urlparse(p['url']).fragment)}


def verified_page(url, row):
    return row.get('canonical') == url and not brief_blocked({'url': url, 'audit': row})


def internal_links(inventory, current, crawl_at):
    accepted = crawl_routes(inventory.get('pages', []))
    nodes = {url: row for url, row in accepted.items()
             if verified_page(url, row) and verified_page(url, current.get(url, {}))}
    incoming = {url: [] for url in nodes}
    edges = {}
    for source, row in sorted(nodes.items()):
        targets = sorted((set(row.get('links', [])) & nodes.keys()) - {source})
        edges[source] = targets
        for target in targets:
            incoming[target].append(source)
    graph = [{'url': url, 'incoming': incoming[url], 'outgoing': targets} for url, targets in edges.items()]

    suggestions = []
    for source, target, anchor, placement in LINK_CANDIDATES:
        source_url, target_url = urljoin(SITE, source), urljoin(SITE, target)
        if source_url not in nodes or target_url not in nodes:
            continue
        body = current[source_url].get('body_links')
        if body is not None and target_url in body:
            continue
        evidence = ('Main-content link not seen.' if body is not None else
                    'Check main-content placement in a browser.')
        suggestions.append({'source': source, 'target': target, 'anchor': anchor,
                            'reason': f'{evidence} {placement}', 'status': 'Draft for review'})
    return {'inventory_at': inventory.get('generated_at') or inventory.get('attempted_at'),
            'crawl_at': crawl_at, 'graph': graph, 'suggestions': suggestions}


def search_issue(search, attempt, stale_search):
    error = attempt.get('error') or {}
    failed = attempt.get('status') == 'failed' and (attempt.get('attempted_at') or '') >= (search.get('generated_at') or '')
    if failed and error.get('http_status') == 403:
        return 'The latest recorded Search Console workflow attempt returned HTTP 403 for the URL-prefix property.'
    if failed:
        return 'The latest recorded Search Console workflow attempt failed.'
    if stale_search:
        return 'Page and query measurement is stale or unavailable.'
    return None


def roadmap(current, health, sources, issue, packets, link_report, ai):
    rows = []

    def add(tier, task, status, evidence, action, owner, observed_at, path=None):
        rows.append({'tier': tier, 'task': task, 'status': status, 'evidence': evidence,
                     'next_action': action, 'owner': owner, 'observed_at': observed_at, 'page': path})

    if issue:
        add('Fatal', 'Restore page and query measurement', 'Open', issue,
            'Confirm the weekly email workflow remains isolated, then have the owner restore read access for the exact property and verify a complete refresh.',
            'Account owner', sources.get('search_attempt') or sources['search'])

    crawl_at = sources['crawl']
    if not current:
        add('Fatal', 'Refresh live route evidence', 'Needs evidence', 'A current bounded crawl is unavailable.',
            'Run the crawl-only check and verify affected routes before drafting.', 'SEO operator', crawl_at)
    elif health.get('status') == 'failed':
        add('Fatal', 'Resolve crawl blockers', 'Open', f"{len(health.get('blockers', []))} blockers in the latest attempt.",
            'Check the crawl report and have the website owner apply approved fixes in the serving system.', 'Website owner', crawl_at)

    url = urljoin(SITE, CHECKLIST)
    guide = current.get(url, {})
    guide_ready = verified_page(url, guide)
    if guide_ready:
        add('Fatal', 'Recheck the supplier checklist route', 'Verified', 'The previously unavailable route now returns HTTP 200 with its own canonical.',
            'Review guide intent and retain the exact route in the term review.', 'SEO lead', crawl_at, CHECKLIST)
    else:
        status = guide.get('http_status')
        evidence = f'Last route check returned HTTP {status}.' if status else 'Current exact-route evidence is missing.'
        add('Fatal', 'Decide the supplier checklist destination', 'Open' if guide else 'Needs evidence', evidence,
            'Verify the exact URL. If unavailable, have the owner approve restoring the guide here or retargeting the term to a verified guide.',
            'Website owner', crawl_at, CHECKLIST)

    for path, name, action in (
        ('/how-it-works/', 'Explain the route to sampling', 'Review whether first-time buyers can identify the next decision, their inputs and the sample approval step.'),
        ('/', 'Clarify homepage buyer paths', 'Check how a brand chooses private label or custom production and finds the brief or catalog.'),
        (CONTRACT, 'Review the contract manufacturing page', 'Review OEM intent, first-hand evidence and the enquiry step against a dated baseline.'),
    ):
        url = urljoin(SITE, path)
        page = current.get(url, {})
        if not verified_page(url, page) or not isinstance(page.get('word_count'), int):
            add('Revenue', name, 'Needs evidence', 'Current page-depth evidence is unavailable.',
                'Verify the exact route and extract its main content before choosing a change.', 'SEO lead', crawl_at, path)
            continue
        count = page['word_count']
        status = 'Review' if count < 350 else 'Monitor'
        add('Revenue', name, status, f'{count} extracted words. The 350-word threshold flags pages for editorial triage.',
            action, 'SEO lead', crawl_at, path)

    held = [p for p in packets if p['status'] == 'hold']
    missing = {fact for p in held for fact in p['missing_facts']}
    if held:
        add('Revenue', 'Clear the draft holds', 'Held', f'{len(held)} packets held. {len(missing)} distinct required fact fields are unknown or unsupported.',
            'Review search intent and confirm required public facts with first-hand evidence for one page.',
            'Operations owner and SEO lead', crawl_at)
    add('Compounding', 'Review contextual internal links', 'Review' if link_report['suggestions'] else 'Needs evidence',
        f"{len(link_report['suggestions'])} placements to check against the accepted inventory and latest crawl.",
        'Review body placement and buyer context on the exact live source and destination.', 'SEO lead', crawl_at)
    add('Compounding', 'Collect buyer-prompt observations', 'Review' if ai['observations'] else 'Optional',
        f"{len(ai['unobserved_prompts'])} buyer prompts lack a recorded observation.",
        'Record a dated manual observation before proposing any change for AI visibility.', 'SEO lead', ai['latest_checked_at'])
    add('Fluff', 'Defer cosmetic metadata refinements', 'Deferred', 'Address crawl and revenue work first.',
        'Revisit minor copy and metadata polish after the higher-priority decisions.', 'SEO lead', None)
    return rows


def blitz_plan(current, sources, pack, roadmap_rows, proof):
    url = urljoin(SITE, PRIVATE_LABEL)
    page = current.get(url, {})
    packet = next((p for p in pack['packets'] if p['page'] == PRIVATE_LABEL), {})
    receipts = [r for r in proof.values() if PRIVATE_LABEL in r['pages']]
    proof_categories = {r['category'] for r in receipts}
    blockers = [row['task'] for row in roadmap_rows if row['tier'] == 'Fatal' and row['status'] in ('Open', 'Needs evidence')]
    if not verified_page(url, page):
        blockers.append('Verify the exact private-label destination before starting.')
    blockers.extend(packet.get('blockers', ['Review a term and page packet for this destination.']))
    if 'private label jewelry manufacturer' not in packet.get('eligible_terms', []):
        blockers.append('Approve intent, destination and facts for the primary private-label term.')
    if len(proof_categories) < 4:
        blockers.append('Review four distinct first-hand proof categories for the sprint.')
    return {'page': PRIVATE_LABEL, 'keyword': 'private label jewelry manufacturer',
            'status': 'Held' if blockers else 'Ready for human review',
            'crawl_at': sources['crawl'], 'search_through': sources['search_through'],
            'live_verified': verified_page(url, page), 'blockers': blockers, 'proof_categories': len(proof_categories),
            'proof_needed': [key for key in PROOF_CATEGORIES if key not in proof_categories],
            'confirmed_fields': sorted(packet.get('confirmed_facts', {})),
            'missing_facts': packet.get('missing_facts', []),
            'weeks': [
                ('Days 1–7', 'Confirm the live source and finalized GSC baseline. Review the exact term’s supplier SERP and compare the existing title, H1 and enquiry path.'),
                ('Days 8–14', 'Review one buyer problem, the public fact limits and the approved proof. Draft a focused opening, title and natural links.'),
                ('Days 15–21', 'Save the crawl baseline. Have the owner review a single page change, then verify the live result after any authorized publication.'),
                ('Days 22–30', 'Review discovery, indexability and qualified enquiries. Schedule 28- and 56-day comparisons from the actual publication date.'),
            ],
            'measurement': 'Use finalized, equal pre/post windows for page and exact-term clicks, impressions, CTR and average position. Log qualified B2B enquiries with supporting attribution. Either click window under 20 is inconclusive. Observed differences do not establish causation.'}


def markdown_text(value):
    plain = ' '.join(str(value).split())
    return re.sub(r'([\\`*_{}\[\]()~|])', r'\\\1', escape(plain))


def roadmap_markdown(rows):
    lines = ['# SEO roadmap', '', 'Priorities for evidence, content and human publication.',
             '', '[Crawl evidence](crawl-health.json) · [Page and query snapshot](latest.json)',
             '', 'Observation dates are UTC.']
    for tier in TIERS:
        lines.extend(['', '## ' + tier, ''])
        for row in (r for r in rows if r['tier'] == tier):
            path = f" ({row['page']})" if row['page'] else ''
            observed = f" Checked {row['observed_at'][:10]}." if row['observed_at'] else ''
            lines.append('- ' + markdown_text(f"{row['status']} — {row['task']}{path}. {row['evidence']}{observed} "
                                              f"{row['owner']}. {row['next_action']}"))
    return '\n'.join(lines) + '\n'


def blitz_markdown(plan):
    live = 'Yes' if plan['live_verified'] else 'Awaiting evidence'
    lines = ['# Private label manufacturing · 30-day review plan', '',
             f"- Destination {plan['page']}", f"- Primary term **{plan['keyword']}**",
             f"- Status **{plan['status']}**", f"- Exact route and canonical verified · {live}",
             f"- Crawl evidence {plan['crawl_at'] or 'Unavailable'}",
             f"- Finalized page/query data through {plan['search_through'] or 'Unavailable'}",
             f"- Public proof categories documented {plan['proof_categories']} of {len(PROOF_CATEGORIES)}",
             f"- Confirmed draft fields {', '.join(plan['confirmed_fields']) or 'None recorded'}",
             '', '## Before starting', '',
             *['- ' + markdown_text(b) for b in plan['blockers']]]
    if plan['proof_categories'] < 4:
        lines.extend(['', 'Choose enough of the following receipts to document four distinct categories.', '',
                      *['- ' + PROOF_CATEGORIES[key] for key in plan['proof_needed']]])
    lines.extend([
             '', '## Review schedule', '',
             *[f'- **{step}** {action}' for step, action in plan['weeks']],
             '', '## Change log and measurement', '',
             'Record the affected URL, approved change, hypothesis, observed baseline, actual publication date and verification link in Changes & results.',
             plan['measurement'], '', '[Human review and publication packet](../website/handoff-private-label.md)'])
    return '\n'.join(lines) + '\n'


def journey_markdown():
    lines = ['# Jewelry brand buyer journey', '',
             'Use these example searches to test buyer intent. Destinations are candidates for review.']
    for _, stage, need, google, ai, page in JOURNEY:
        lines.extend(['', f'## {stage}', '', need, '', f'- Google example · {google}',
                      f'- AI example · {ai}', f'- Candidate page · {page}'])
    return '\n'.join(lines) + '\n'
