"""Sync exported change records into editorial.json; never import private enquiry counts."""
import argparse
from datetime import date
import json
from pathlib import Path
from seo_pipeline import ROOT, SITE, safe_url, write_json
from urllib.parse import urljoin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('backup', type=Path)
    args = parser.parse_args()
    backup = json.loads(args.backup.read_text())
    if backup.get('version') != 2:
        raise ValueError('Expected a version 2 workspace export')
    records = backup.get('changes', [])
    if len(records) > 1000:
        raise ValueError('Too many change records')
    clean = []
    for record in records:
        if not isinstance(record.get('id'), str) or not record['id']:
            raise ValueError('Every change needs an ID')
        if not safe_url(urljoin(SITE, record['page'])) or not record['page'].startswith('/'):
            raise ValueError('Change page must belong to Petra')
        if date.fromisoformat(record['published_at']) > date.today():
            raise ValueError('Published date cannot be in the future')
        if not isinstance(record.get('summary'), str) or not record['summary'].strip() or len(record['summary']) > 1200:
            raise ValueError('Describe each published change in under 1200 characters')
        clean.append({key: record[key] for key in ('id', 'page', 'published_at', 'summary', 'type') if key in record})
    path = ROOT / 'data/editorial.json'
    editorial = json.loads(path.read_text())
    changes = {c['id']: c for c in editorial.get('changes', [])}
    changes.update({c['id']: c for c in clean})
    editorial['changes'] = list(changes.values())
    write_json(path, editorial)
    print(f'Synced {len(clean)} changes. Enquiry counts and owner names were not added to the public repository.')


if __name__ == '__main__':
    main()
