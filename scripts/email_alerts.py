#!/usr/bin/env python3
"""
SEO Email Alert System for Petra Jewelry Factory
Sends weekly reports to ali@petrabrands.com via Resend API
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
CREDENTIALS_PATH = 'credentials.json'
SITE_URL = 'https://petrajewelryfactory.com/'
ALERT_EMAIL = 'ali@petrabrands.com'
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = 'SEO Reports <reports@resend.dev>'  # Use resend.dev for testing

# Priority keywords
PRIORITY_KEYWORDS = [
    "jewelry manufacturer china",
    "stainless steel jewelry manufacturer",
    "private label jewelry manufacturer",
    "hard jewelry manufacturer",
    "316L stainless steel jewelry supplier",
    "jewelry manufacturer for ecommerce brands",
    "premium jewelry manufacturer china",
]

# All 50 keywords
ALL_KEYWORDS = [
    # China Location (10)
    "jewelry manufacturer china", "china jewelry factory",
    "stainless steel jewelry manufacturer china", "jewelry supplier china wholesale",
    "premium jewelry manufacturer china", "jewelry factory dongguan",
    "chinese jewelry manufacturer for brands", "china jewelry factory high quality",
    "silver jewelry manufacturer china", "brass jewelry manufacturer china",
    # Durability (8)
    "hard jewelry manufacturer", "durable jewelry manufacturer",
    "waterproof jewelry manufacturer", "tarnish free jewelry supplier",
    "lifetime warranty jewelry manufacturer", "hypoallergenic jewelry manufacturer",
    "long lasting jewelry supplier", "surgical steel jewelry manufacturer",
    # Materials (10)
    "stainless steel jewelry manufacturer", "316L stainless steel jewelry supplier",
    "brass jewelry manufacturer", "sterling silver jewelry manufacturer",
    "925 silver jewelry wholesale", "PVD plated jewelry manufacturer",
    "gold plated stainless steel jewelry wholesale", "rose gold jewelry manufacturer",
    "stainless steel jewelry factory", "nickel free jewelry manufacturer",
    # Private Label (8)
    "private label jewelry manufacturer", "OEM jewelry manufacturer",
    "ODM jewelry manufacturer", "white label jewelry manufacturer",
    "custom jewelry manufacturer", "private label jewelry manufacturer china",
    "contract jewelry manufacturer", "jewelry manufacturing partner",
    # Ecommerce (7)
    "jewelry manufacturer for ecommerce brands", "jewelry supplier for DTC brands",
    "jewelry manufacturer for shopify brands", "wholesale jewelry supplier for online stores",
    "B2B jewelry manufacturer", "jewelry manufacturer for retailers",
    "jewelry supplier for amazon sellers",
    # Quality (7)
    "premium jewelry manufacturer", "high quality jewelry factory",
    "reliable jewelry manufacturer", "jewelry manufacturer quality control",
    "best jewelry manufacturer for brands", "luxury stainless steel jewelry manufacturer",
    "consistent jewelry manufacturing supplier",
]


def get_service():
    """Initialize GSC API service."""
    if os.path.exists(CREDENTIALS_PATH):
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
    else:
        creds_json = os.environ.get('GSC_CREDENTIALS', '{}')
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
    return build('searchconsole', 'v1', credentials=credentials)


def get_keyword_data(service, keyword, days=7):
    """Get ranking data for a keyword."""
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['query'],
        'dimensionFilterGroups': [{
            'filters': [{'dimension': 'query', 'operator': 'contains', 'expression': keyword}]
        }],
        'rowLimit': 10
    }

    try:
        response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
        rows = response.get('rows', [])
        if rows:
            total_imp = sum(r.get('impressions', 0) for r in rows)
            total_clicks = sum(r.get('clicks', 0) for r in rows)
            avg_pos = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows)
            avg_pos = avg_pos / total_imp if total_imp > 0 else 0
            return {'impressions': total_imp, 'clicks': total_clicks, 'position': round(avg_pos, 1), 'ranking': avg_pos > 0}
    except Exception as e:
        print(f"Error: {e}")
    return {'impressions': 0, 'clicks': 0, 'position': 0, 'ranking': False}


def get_overall_metrics(service, days=7):
    """Get overall site metrics."""
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    request = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'dimensions': ['date'],
    }

    response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
    rows = response.get('rows', [])

    return {
        'clicks': sum(r.get('clicks', 0) for r in rows),
        'impressions': sum(r.get('impressions', 0) for r in rows),
        'ctr': round(sum(r.get('ctr', 0) for r in rows) / len(rows) * 100, 2) if rows else 0,
        'position': round(sum(r.get('position', 0) for r in rows) / len(rows), 1) if rows else 0,
    }


def load_previous_data():
    """Load previous week's data."""
    if os.path.exists('data/previous_rankings.json'):
        with open('data/previous_rankings.json', 'r') as f:
            return json.load(f)
    return {}


def save_current_data(data):
    """Save current data for comparison."""
    os.makedirs('data', exist_ok=True)
    with open('data/previous_rankings.json', 'w') as f:
        json.dump(data, f, indent=2)


def generate_report_html(current_data, previous_data, overall):
    """Generate HTML email report."""
    ranking_count = sum(1 for v in current_data.values() if v['ranking'])
    page1_count = sum(1 for v in current_data.values() if 0 < v['position'] <= 10)
    top3_count = sum(1 for v in current_data.values() if 0 < v['position'] <= 3)
    prev_ranking = sum(1 for v in previous_data.values() if v.get('ranking', False))

    # Find changes
    new_rankings = []
    improvements = []
    for kw, data in current_data.items():
        prev = previous_data.get(kw, {})
        if data['ranking'] and not prev.get('ranking', False):
            new_rankings.append((kw, data['position']))
        elif data['ranking'] and prev.get('ranking', False):
            change = prev.get('position', 100) - data['position']
            if change > 2:
                improvements.append((kw, data['position'], change))

    html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
.container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #d4af37; padding: 30px; text-align: center; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header p {{ margin: 10px 0 0; color: #a0a0a0; font-size: 14px; }}
.metrics {{ display: flex; flex-wrap: wrap; padding: 20px; gap: 10px; }}
.metric {{ flex: 1; min-width: 120px; background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
.metric-value {{ font-size: 28px; font-weight: bold; color: #1a1a2e; }}
.metric-label {{ font-size: 11px; color: #666; text-transform: uppercase; margin-top: 5px; }}
.section {{ padding: 20px; border-top: 1px solid #eee; }}
.section h2 {{ font-size: 16px; color: #1a1a2e; margin: 0 0 15px; }}
.alert {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 12px 15px; margin: 10px 0; border-radius: 0 8px 8px 0; }}
.alert-new {{ background: #fff3e0; border-color: #ff9800; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ background: #f8f9fa; padding: 10px; text-align: left; font-weight: 600; color: #333; }}
td {{ padding: 10px; border-bottom: 1px solid #eee; }}
.badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.badge-success {{ background: #e8f5e9; color: #2e7d32; }}
.badge-warning {{ background: #fff3e0; color: #ef6c00; }}
.badge-muted {{ background: #f5f5f5; color: #999; }}
.footer {{ background: #1a1a2e; color: #888; padding: 20px; text-align: center; font-size: 12px; }}
.footer a {{ color: #d4af37; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Petra Jewelry Factory</h1>
        <p>Weekly SEO Report &bull; {datetime.now().strftime('%B %d, %Y')}</p>
    </div>

    <div class="metrics">
        <div class="metric">
            <div class="metric-value">{overall['clicks']}</div>
            <div class="metric-label">Clicks</div>
        </div>
        <div class="metric">
            <div class="metric-value">{overall['impressions']}</div>
            <div class="metric-label">Impressions</div>
        </div>
        <div class="metric">
            <div class="metric-value">{ranking_count}<span style="font-size:14px;color:#666">/50</span></div>
            <div class="metric-label">Ranking</div>
        </div>
        <div class="metric">
            <div class="metric-value">{page1_count}</div>
            <div class="metric-label">Page 1</div>
        </div>
    </div>
"""

    # Week over week
    change = ranking_count - prev_ranking
    if change != 0:
        html += f"""
    <div class="section">
        <div class="alert {'alert-new' if change > 0 else ''}">
            <strong>Week over Week:</strong> {'+' if change > 0 else ''}{change} keywords {'now ranking' if change > 0 else 'lost'}
        </div>
    </div>
"""

    # New rankings
    if new_rankings:
        html += """
    <div class="section">
        <h2>🎉 New Rankings This Week</h2>
        <table>
            <tr><th>Keyword</th><th>Position</th></tr>
"""
        for kw, pos in sorted(new_rankings, key=lambda x: x[1]):
            html += f'<tr><td>{kw}</td><td><span class="badge badge-success">#{int(pos)}</span></td></tr>'
        html += "</table></div>"

    # Improvements
    if improvements:
        html += """
    <div class="section">
        <h2>📈 Improved Rankings</h2>
        <table>
            <tr><th>Keyword</th><th>Position</th><th>Change</th></tr>
"""
        for kw, pos, chg in sorted(improvements, key=lambda x: -x[2])[:5]:
            html += f'<tr><td>{kw}</td><td>#{int(pos)}</td><td style="color:#2e7d32">↑ {int(chg)}</td></tr>'
        html += "</table></div>"

    # Priority keywords
    html += """
    <div class="section">
        <h2>⭐ Priority Keywords</h2>
        <table>
            <tr><th>Keyword</th><th>Position</th><th>Impressions</th></tr>
"""
    for kw in PRIORITY_KEYWORDS:
        d = current_data.get(kw, {})
        pos = d.get('position', 0)
        if pos > 0:
            badge = f'<span class="badge badge-success">#{int(pos)}</span>'
        else:
            badge = '<span class="badge badge-muted">Not ranking</span>'
        html += f'<tr><td>{kw}</td><td>{badge}</td><td>{d.get("impressions", 0)}</td></tr>'

    html += f"""
        </table>
    </div>

    <div class="footer">
        <p><a href="https://alikaaba-bit.github.io/petra-seo-dashboard/">View Full Dashboard</a></p>
        <p>Data from Google Search Console &bull; Auto-generated report</p>
    </div>
</div>
</body>
</html>
"""
    return html


def send_email_resend(to_email, subject, html_content):
    """Send email using Resend API."""
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set. Saving report locally.")
        os.makedirs('data', exist_ok=True)
        with open('data/latest_report.html', 'w') as f:
            f.write(html_content)
        print("Report saved to data/latest_report.html")
        return False

    url = 'https://api.resend.com/emails'
    data = json.dumps({
        'from': FROM_EMAIL,
        'to': [to_email],
        'subject': subject,
        'html': html_content
    }).encode('utf-8')

    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', f'Bearer {RESEND_API_KEY}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"Email sent successfully! ID: {result.get('id')}")
            return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Failed to send email: {e.code} - {error_body}")
        return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def main():
    """Main function."""
    print(f"Generating weekly SEO report...")
    print(f"Target: {ALERT_EMAIL}")

    service = get_service()

    # Fetch data
    print("Fetching keyword data...")
    current_data = {}
    for kw in ALL_KEYWORDS:
        current_data[kw] = get_keyword_data(service, kw)

    overall = get_overall_metrics(service)
    previous_data = load_previous_data()

    # Generate report
    html = generate_report_html(current_data, previous_data, overall)

    # Summary for subject
    ranking_count = sum(1 for v in current_data.values() if v['ranking'])
    new_count = sum(1 for k, v in current_data.items()
                    if v['ranking'] and not previous_data.get(k, {}).get('ranking', False))

    subject = f"Petra SEO: {ranking_count}/50 keywords ranking"
    if new_count > 0:
        subject += f" (+{new_count} new!)"

    # Send email
    send_email_resend(ALERT_EMAIL, subject, html)

    # Save for next week
    save_current_data(current_data)

    print("Done!")


if __name__ == '__main__':
    main()
