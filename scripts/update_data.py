#!/usr/bin/env python3
"""
Update SEO Dashboard Data
Fetches latest data from Google Search Console API
"""

import json
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
CREDENTIALS_PATH = 'credentials.json'
SITE_URL = 'https://petrajewelryfactory.com/'
DATA_PATH = 'data'

# 50 Target Keywords
TARGET_KEYWORDS = {
    "china_location": [
        "jewelry manufacturer china",
        "china jewelry factory",
        "stainless steel jewelry manufacturer china",
        "jewelry supplier china wholesale",
        "premium jewelry manufacturer china",
        "jewelry factory dongguan",
        "chinese jewelry manufacturer for brands",
        "china jewelry factory high quality",
        "silver jewelry manufacturer china",
        "brass jewelry manufacturer china",
    ],
    "durability": [
        "hard jewelry manufacturer",
        "durable jewelry manufacturer",
        "waterproof jewelry manufacturer",
        "tarnish free jewelry supplier",
        "lifetime warranty jewelry manufacturer",
        "hypoallergenic jewelry manufacturer",
        "long lasting jewelry supplier",
        "surgical steel jewelry manufacturer",
    ],
    "materials": [
        "stainless steel jewelry manufacturer",
        "316L stainless steel jewelry supplier",
        "brass jewelry manufacturer",
        "sterling silver jewelry manufacturer",
        "925 silver jewelry wholesale",
        "PVD plated jewelry manufacturer",
        "gold plated stainless steel jewelry wholesale",
        "rose gold jewelry manufacturer",
        "stainless steel jewelry factory",
        "nickel free jewelry manufacturer",
    ],
    "private_label": [
        "private label jewelry manufacturer",
        "OEM jewelry manufacturer",
        "ODM jewelry manufacturer",
        "white label jewelry manufacturer",
        "custom jewelry manufacturer",
        "private label jewelry manufacturer china",
        "contract jewelry manufacturer",
        "jewelry manufacturing partner",
    ],
    "ecommerce": [
        "jewelry manufacturer for ecommerce brands",
        "jewelry supplier for DTC brands",
        "jewelry manufacturer for shopify brands",
        "wholesale jewelry supplier for online stores",
        "B2B jewelry manufacturer",
        "jewelry manufacturer for retailers",
        "jewelry supplier for amazon sellers",
    ],
    "quality": [
        "premium jewelry manufacturer",
        "high quality jewelry factory",
        "reliable jewelry manufacturer",
        "jewelry manufacturer quality control",
        "best jewelry manufacturer for brands",
        "luxury stainless steel jewelry manufacturer",
        "consistent jewelry manufacturing supplier",
    ],
}

ALL_KEYWORDS = []
for keywords in TARGET_KEYWORDS.values():
    ALL_KEYWORDS.extend(keywords)

HIGH_PRIORITY = [
    "jewelry manufacturer china",
    "stainless steel jewelry manufacturer",
    "private label jewelry manufacturer",
    "hard jewelry manufacturer",
    "316L stainless steel jewelry supplier",
    "jewelry manufacturer for ecommerce brands",
    "premium jewelry manufacturer china",
]


def get_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=['https://www.googleapis.com/auth/webmasters.readonly']
    )
    return build('searchconsole', 'v1', credentials=credentials)


def get_ranking_status(position):
    if position == 0:
        return 'Not Ranking'
    elif position <= 3:
        return 'Top 3'
    elif position <= 10:
        return 'Page 1'
    elif position <= 20:
        return 'Page 2'
    elif position <= 30:
        return 'Page 3'
    else:
        return 'Page 4+'


def get_keyword_rankings(service, keywords, days_back=7):
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days_back)
    results = {}

    for keyword in keywords:
        request = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': ['query'],
            'dimensionFilterGroups': [{
                'filters': [{
                    'dimension': 'query',
                    'operator': 'contains',
                    'expression': keyword
                }]
            }],
            'rowLimit': 100
        }

        try:
            response = service.searchanalytics().query(
                siteUrl=SITE_URL,
                body=request
            ).execute()

            rows = response.get('rows', [])
            if rows:
                total_impressions = sum(r.get('impressions', 0) for r in rows)
                total_clicks = sum(r.get('clicks', 0) for r in rows)
                avg_position = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows)
                avg_position = avg_position / total_impressions if total_impressions > 0 else 0

                results[keyword] = {
                    'impressions': total_impressions,
                    'clicks': total_clicks,
                    'avg_position': round(avg_position, 1),
                    'ctr': round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0,
                    'status': get_ranking_status(avg_position),
                    'is_priority': keyword in HIGH_PRIORITY,
                }
            else:
                results[keyword] = {
                    'impressions': 0,
                    'clicks': 0,
                    'avg_position': 0,
                    'ctr': 0,
                    'status': 'Not Ranking',
                    'is_priority': keyword in HIGH_PRIORITY,
                }
        except Exception as e:
            print(f"Error fetching {keyword}: {e}")
            results[keyword] = {
                'impressions': 0, 'clicks': 0, 'avg_position': 0,
                'ctr': 0, 'status': 'Error', 'is_priority': keyword in HIGH_PRIORITY,
            }

    return results


def get_overall_metrics(service, days_back=7):
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days_back)

    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['date'],
        'rowLimit': 100
    }

    response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
    rows = response.get('rows', [])

    total_clicks = sum(r.get('clicks', 0) for r in rows)
    total_impressions = sum(r.get('impressions', 0) for r in rows)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_position = sum(r.get('position', 0) for r in rows) / len(rows) if rows else 0

    return {
        'total_clicks': total_clicks,
        'total_impressions': total_impressions,
        'avg_ctr': round(avg_ctr, 2),
        'avg_position': round(avg_position, 1),
        'period_start': start_date.strftime('%Y-%m-%d'),
        'period_end': end_date.strftime('%Y-%m-%d'),
    }


def get_discovered_keywords(service, limit=30):
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=28)

    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['query'],
        'rowLimit': 500
    }

    response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
    rows = response.get('rows', [])
    tracked_lower = [k.lower() for k in ALL_KEYWORDS]

    discovered = []
    for row in rows:
        keyword = row['keys'][0]
        if keyword.lower() not in tracked_lower:
            discovered.append({
                'keyword': keyword,
                'impressions': row.get('impressions', 0),
                'clicks': row.get('clicks', 0),
                'position': round(row.get('position', 0), 1),
                'ctr': round(row.get('ctr', 0) * 100, 2)
            })

    discovered.sort(key=lambda x: x['impressions'], reverse=True)
    return discovered[:limit]


def get_top_pages(service, limit=10):
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=28)

    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['page'],
        'rowLimit': 100
    }

    response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
    rows = response.get('rows', [])

    pages = []
    for row in rows:
        pages.append({
            'page': row['keys'][0].replace('https://petrajewelryfactory.com', ''),
            'impressions': row.get('impressions', 0),
            'clicks': row.get('clicks', 0),
            'position': round(row.get('position', 0), 1),
            'ctr': round(row.get('ctr', 0) * 100, 2)
        })

    pages.sort(key=lambda x: x['impressions'], reverse=True)
    return pages[:limit]


def main():
    print("Updating SEO Dashboard data...")
    service = get_service()

    overall = get_overall_metrics(service)
    tracked = get_keyword_rankings(service, ALL_KEYWORDS)
    discovered = get_discovered_keywords(service)
    top_pages = get_top_pages(service)

    # Calculate stats
    category_stats = {}
    for category, keywords in TARGET_KEYWORDS.items():
        ranking = sum(1 for k in keywords if tracked.get(k, {}).get('avg_position', 0) > 0)
        page1 = sum(1 for k in keywords if 0 < tracked.get(k, {}).get('avg_position', 0) <= 10)
        category_stats[category] = {'total': len(keywords), 'ranking': ranking, 'page1': page1}

    total_ranking = sum(1 for v in tracked.values() if v['avg_position'] > 0)
    total_page1 = sum(1 for v in tracked.values() if 0 < v['avg_position'] <= 10)
    total_top3 = sum(1 for v in tracked.values() if 0 < v['avg_position'] <= 3)

    data = {
        'generated_at': datetime.now().isoformat(),
        'site_url': SITE_URL,
        'overall_metrics': overall,
        'keyword_summary': {
            'total_tracked': len(ALL_KEYWORDS),
            'total_ranking': total_ranking,
            'page1_keywords': total_page1,
            'top3_keywords': total_top3,
        },
        'category_stats': category_stats,
        'tracked_keywords': tracked,
        'discovered_keywords': discovered,
        'top_pages': top_pages,
    }

    # Save data
    os.makedirs(DATA_PATH, exist_ok=True)

    with open(os.path.join(DATA_PATH, 'latest.json'), 'w') as f:
        json.dump(data, f, indent=2)

    timestamp = datetime.now().strftime('%Y-%m-%d')
    with open(os.path.join(DATA_PATH, f'history_{timestamp}.json'), 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Data updated: {total_ranking}/{len(ALL_KEYWORDS)} keywords ranking")
    print(f"Page 1: {total_page1}, Top 3: {total_top3}")


if __name__ == '__main__':
    main()
