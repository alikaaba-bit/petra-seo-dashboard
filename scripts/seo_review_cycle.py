"""Validate evidence, recover a stale public crawl, and record the weekly review decision."""
import argparse
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import sleep
from zoneinfo import ZoneInfo

from seo_method import markdown_text
from seo_pipeline import ROOT, SITE, write_json
from seo_workspace import checkpoint_markdown, latest_crawl, read_json, stale, write_workspace

TRANSIENT = re.compile(r'HTTP (?:429|5\d\d)|timeout|timed out|connection reset|temporary failure|rate limit', re.I)


def check_search(search, today):
    if search.get('site_url') != SITE:
        return 'The saved Search Console property is missing or does not match Petra’s website.'
    try:
        period = search['period']
        start, end = date.fromisoformat(period['start']), date.fromisoformat(period['end'])
        dates = [date.fromisoformat(row['date']) for row in search['daily']]
        days = (end - start).days + 1
        if days < 1 or days != period['days'] or len(set(dates)) != len(dates) or end >= today:
            return 'The finalized date range or daily dates failed validation.'
        if len(dates) != days or any(d < start or d > end for d in dates):
            return 'The daily dates do not cover the saved finalized period.'
        for metric in ('clicks', 'impressions'):
            values = [row[metric] for row in search['daily']]
            total = search['overall'][metric]
            if any(type(value) is not int or value < 0 for value in [total, *values]):
                return 'The property totals or daily counts are invalid.'
            if total != sum(values):
                return 'The saved property totals and daily counts do not reconcile.'
    except (KeyError, TypeError, ValueError):
        return 'The finalized period, daily dates, or property totals are missing or malformed.'
    return None


def read_with_retry(args, run=subprocess.run, delay=sleep):
    for attempt in range(1, 4):
        try:
            result = run(args, capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired:
            retry = True
        except OSError:
            return None, attempt
        else:
            if result.returncode == 0:
                return result.stdout.strip(), attempt
            retry = bool(TRANSIENT.search(result.stderr))
        if not retry or attempt == 3:
            return None, attempt
        delay(2 ** attempt)


def recover_crawl(data_dir, recovery_dir, today, run=subprocess.run):
    try:
        saved = latest_crawl(data_dir)
    except (OSError, AttributeError, json.JSONDecodeError):
        saved = {}
    observed = saved.get('attempted_at') or saved.get('generated_at')
    if saved.get('status') in ('passed', 'warning') and not stale(observed, today, 3):
        return saved, 'saved'
    crawl_args = [sys.executable, '-B', str(ROOT / 'scripts/seo_pipeline.py'), '--crawl-only',
                  '--fail-on-health', '--output-dir', str(recovery_dir)]
    excluded = ('GH_TOKEN', 'GITHUB_TOKEN', 'GSC_CREDENTIALS', 'GOOGLE_APPLICATION_CREDENTIALS')
    env = {key: value for key, value in os.environ.items() if key not in excluded}
    try:
        attempt = run(crawl_args, capture_output=True, text=True, timeout=120, env=env)
        fresh = read_object(recovery_dir / 'crawl-health.json')
    except (OSError, subprocess.TimeoutExpired):
        return saved, 'retry_failed'
    if attempt.returncode == 0 and fresh.get('status') in ('passed', 'warning'):
        return fresh, 'refreshed'
    return saved, 'retry_failed'


def observed_windows(report):
    outcomes = []
    for window in report['followups']:
        if window.get('status') not in ('Inconclusive: low sample', 'Observed change; not causal proof'):
            continue
        before = (window.get('before') or {}).get('clicks')
        after = (window.get('after') or {}).get('clicks')
        if type(before) is not int or type(after) is not int or min(before, after) < 0:
            continue
        delta = after - before
        outcome = 'inconclusive' if min(before, after) < 20 else 'decrease' if delta < 0 else 'increase' if delta > 0 else 'flat'
        outcomes.append({'change_id': window['change_id'], 'page': window['page'],
                         'days': window['days'], 'before': before, 'after': after, 'outcome': outcome})
    return outcomes


def choose_decision(report, search, collector, problem, crawl_result, outcomes):
    page = report['blitz']['page']
    if problem:
        return 'verify-search', None, f'SEO operator · Recheck the saved input. {problem}'
    if collector.get('conclusion') != 'success':
        return 'verify-collector', None, 'SEO operator · Check the latest collector run and use its dated evidence.'
    if crawl_result == 'retry_failed':
        return 'verify-crawl', None, 'Website owner · Review the failed crawl refresh and inspect the affected public routes.'
    critical = next((a for a in report['alerts'] if a['severity'] == 'critical'), None)
    if critical:
        return critical['id'], None, f"{critical['owner']} · {critical['next_action']}"
    if search.get('measurement', {}).get('leads') != 'Connected':
        return 'reconcile-enquiries', None, 'Website owner and sales lead · Match accepted quote and catalogue requests to received, qualified buyer projects.'
    decline = min((row for row in outcomes if row['outcome'] == 'decrease'),
                  key=lambda row: row['after'] - row['before'], default=None)
    if decline:
        path = decline['page']
        return 'review-decline', path, f"SEO lead · Inspect the observed {decline['days']}-day decline for {path} and prepare one evidence-backed next test."
    if report['blitz']['status'] == 'Held':
        return 'collect-proof', page, f'Factory and page owners · Review the missing first-hand evidence for {page}.'
    return 'review-page-test', page, f'Page owner · Review one proposed change and its outcome measure for {page}.'


def review_state(report, search, collector, prior, today, problem, crawl_result):
    week = today - timedelta(days=today.weekday() + 7)
    prior = prior if prior.get('version') == 1 and isinstance(prior.get('week_start'), str) else {}
    if prior:
        try:
            prior_week = date.fromisoformat(prior['week_start'])
            if prior_week.weekday() != 0 or prior_week > week:
                prior = {}
        except ValueError:
            prior = {}
    outcomes = observed_windows(report) if not problem else []
    key, page, action = choose_decision(report, search, collector, problem, crawl_result, outcomes)
    previous = prior.get('decision')
    previous = previous if isinstance(previous, dict) else {}
    same_decision = previous.get('key') == key and previous.get('page') == page
    earlier = prior.get('week_start')
    consecutive = 1
    if same_decision and earlier in (week.isoformat(), (week - timedelta(days=7)).isoformat()):
        count = previous.get('consecutive_weeks')
        if type(count) is int and count > 0:
            consecutive = count + int(earlier != week.isoformat())
    if key == 'reconcile-enquiries' and consecutive > 1:
        action = 'Website owner and sales lead · Identify the missing delivery, source, or qualification field and reconcile it against the original receipts.'
    previous_outcomes = prior.get('outcomes')
    previous_outcomes = previous_outcomes if isinstance(previous_outcomes, list) else []
    return {'version': 1, 'week_start': week.isoformat(), 'previous_week': earlier,
            'search_problem': problem, 'crawl_recovery': crawl_result, 'outcomes': outcomes,
            'new_outcomes': sum(row not in previous_outcomes for row in outcomes),
            'decision': {'key': key, 'page': page, 'action': action, 'consecutive_weeks': consecutive}}


def cycle_markdown(state, reads):
    issue = state['search_problem']
    lines = ['', '## Weekly verification and learning', '',
             '- Search property, dates and counts · ' + (markdown_text(issue) if issue else 'verified'),
             '- Crawl recovery · ' + {'saved': 'saved evidence was current', 'refreshed': 'one read-only retry supplied new evidence',
                                      'retry_failed': 'retry failed and prior crawl evidence was retained'}[state['crawl_recovery']],
             f"- Prior reviewed week · {markdown_text(state['previous_week'] or 'unavailable')}",
             f"- Current decision open for {state['decision']['consecutive_weeks']} consecutive review week(s).",
             f"- New or changed outcome windows · {state['new_outcomes']}.",
             '- Search click comparisons use equal windows and observational evidence. They do not establish causal impact.']
    for label, attempts in reads.items():
        lines.append(f'- {label} read attempts · {attempts}')
    for outcome in state['outcomes']:
        lines.append('- ' + markdown_text(f"{outcome['page']} · {outcome['days']}-day window · {outcome['outcome']} · "
                                         f"{outcome['before']} before and {outcome['after']} after clicks."))
    return '\n'.join(lines) + '\n'


def read_object(path):
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def get_inputs(repository, branch, prior_dir):
    base = f'repos/{repository}/actions/workflows'
    filters = ['-f', f'branch={branch}', '-f', 'status=completed']
    saved, collector_attempts = read_with_retry(
        ['gh', 'api', '--method', 'GET', f'{base}/update-dashboard.yml/runs', *filters, '-F', 'per_page=1',
         '--jq', '.workflow_runs[0] | {id, conclusion}'])
    history, history_attempts = read_with_retry(
        ['gh', 'api', '--method', 'GET', f'{base}/seo-weekly-review.yml/runs', *filters, '-F', 'per_page=10',
         '--jq', '[.workflow_runs[] | select(.conclusion == "success")][0].id'])
    try:
        collector = json.loads(saved) if saved else {}
    except json.JSONDecodeError:
        collector = {}
    collector = collector if isinstance(collector, dict) else {}
    reads = {'Collector status': collector_attempts, 'Review history': history_attempts}
    prior = {}
    if history and history.isdecimal():
        downloaded, reads['Prior review artifact'] = read_with_retry(
            ['gh', 'run', 'download', history, '-R', repository, '--name', 'seo-weekly-review', '--dir', str(prior_dir)])
        if downloaded is not None:
            prior = read_object(prior_dir / 'review-state.json')
    return collector, prior, reads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--github-repository')
    parser.add_argument('--branch', default='main')
    args = parser.parse_args()
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date()
    source = read_object(args.data_dir / 'latest.json')
    problem = check_search(source, today)
    search = {} if problem else source
    collector, prior, reads = ({}, {}, {})
    if args.github_repository:
        collector, prior, reads = get_inputs(args.github_repository, args.branch, args.output_dir / 'prior')
    crawl, recovery = recover_crawl(args.data_dir, args.output_dir / 'crawl-recovery', today)
    editorial = read_json(args.data_dir / 'editorial.json')
    report = write_workspace(editorial, args.data_dir, args.output_dir, crawl, search=search)
    state = review_state(report, search, collector, prior, today, problem, recovery)
    checkpoint = checkpoint_markdown(report, search, crawl, collector, today, decision=state['decision']['action'])
    (args.output_dir / 'checkpoint.md').write_text(checkpoint + cycle_markdown(state, reads), encoding='utf-8')
    write_json(args.output_dir / 'review-state.json', state)


if __name__ == '__main__':
    main()
