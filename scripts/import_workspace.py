"""Validate a browser export; dry-run by default. Only reviewed public fields may be applied."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from seo_pipeline import ROOT, SITE, safe_url, write_json
from seo_workspace import canonical_path, public_url, reviewed_date, text, validate_fact, validate_term, validate_page_review, validate_proof
from urllib.parse import urljoin, unquote
from zoneinfo import ZoneInfo


def merge_workspace(backup, editorial, include_reviews=False, today=None):
    today = today or datetime.now(ZoneInfo('America/Los_Angeles')).date()
    if not isinstance(backup, dict) or backup.get('version') != 2:
        raise ValueError('Expected a version 2 workspace export')
    records = backup.get('changes', [])
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError('Too many change records')
    clean, ids = [], set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('page'), str):
            raise ValueError('Invalid publication record')
        ident = text(record.get('id'), 'Change ID', 100)
        if ident in ids:
            raise ValueError('Duplicate change IDs in export')
        ids.add(ident)
        page = record.get('page', '')
        if not canonical_path(page.split('#', 1)[0]) or any(c.isspace() for c in unquote(page)) or not safe_url(urljoin(SITE, page)):
            raise ValueError('Change page must belong to Petra')
        entry = {'id': ident, 'page': page, 'published_at': reviewed_date(record.get('published_at'), today),
                 'summary': text(record.get('summary'), 'Change summary', 1200)}
        for key in ('type', 'hypothesis'):
            if record.get(key):
                entry[key] = text(record[key], key, 1200)
        if record.get('evidence_url'):
            if not public_url(record['evidence_url']):
                raise ValueError('Publication evidence must be a public HTTPS reference without query tokens')
            entry['evidence_url'] = record['evidence_url']
        if record.get('verified_at'):
            entry['verified_at'] = reviewed_date(record['verified_at'], today)
            if entry['verified_at'] < entry['published_at']:
                raise ValueError('Live verification cannot precede publication')
        clean.append(entry)
    result = deepcopy(editorial)
    changes = {c['id']: c for c in result.get('changes', [])}
    changes.update({c['id']: c for c in clean})
    if len(changes) > 1000:
        raise ValueError('Merged publication log exceeds 1000 records; review archival before importing')
    result['changes'] = list(changes.values())
    if include_reviews:
        review = backup.get('review', {})
        if not isinstance(review, dict):
            raise ValueError('Invalid editorial review export')
        for section, validate, maximum in (('fact_reviews', validate_fact, 100), ('term_reviews', validate_term, 50), ('page_reviews', validate_page_review, 100)):
            records = review.get(section, {})
            if not isinstance(records, dict) or len(records) > maximum:
                raise ValueError('Invalid review section: ' + section)
            result.setdefault(section, {}).update({key: validate(key, record, today) for key, record in records.items()})
        if 'proof_reviews' in review:
            records = review['proof_reviews']
            if not isinstance(records, dict) or len(records) > 200:
                raise ValueError('Invalid proof review section')
            proofs = {**result.get('proof_reviews', {}), **{k: validate_proof(k, r, today) for k, r in records.items()}}
            if len(proofs) > 200:
                raise ValueError('Merged proof register exceeds 200 records')
            result['proof_reviews'] = proofs
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path)
    parser.add_argument('--editorial', type=Path, default=ROOT / 'data/editorial.json')
    parser.add_argument('--output', type=Path, help='Defaults to the input editorial file when applying')
    parser.add_argument('--include-reviews', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--public-reviewed', action='store_true', help='Attest that all imported free text and evidence are approved for a public repo')
    args = parser.parse_args()
    if args.apply and not args.public_reviewed:
        parser.error('--apply requires --public-reviewed; inspect the export for private material first')
    if args.backup.stat().st_size > 2_000_000:
        raise ValueError('Choose a workspace export under 2 MB')
    original = json.loads(args.editorial.read_text())
    proposed = merge_workspace(json.loads(args.backup.read_text()), original, args.include_reviews)
    if args.apply:
        write_json(args.output or args.editorial, proposed)
    print(json.dumps({'mode': 'applied locally' if args.apply else 'dry-run; no files changed',
                      'changed': proposed != original, 'changes': len(proposed['changes']),
                      'term_reviews': len(proposed.get('term_reviews', {})), 'fact_reviews': len(proposed.get('fact_reviews', {})),
                      'proof_reviews': len(proposed.get('proof_reviews', {})),
                      'page_reviews': len(proposed.get('page_reviews', {})), 'excluded': ['owner', 'tasks', 'leads']}, indent=2))


if __name__ == '__main__':
    main()
