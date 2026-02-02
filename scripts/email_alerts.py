#!/usr/bin/env python3
"""
SEO Email Alert System for Petra Jewelry Factory
Sends weekly reports and ranking change alerts to ali@petrabrands.com
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
CREDENTIALS_PATH = os.environ.get('GSC_CREDENTIALS_PATH', 'credentials.json')
SITE_URL = 'https://petrajewelryfactory.com/'
ALERT_EMAIL = 'ali@petrabrands.com'
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'seo-alerts@petrajewelryfactory.com')

# Priority keywords to monitor closely
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
    # China Location
    "jewelry manufacturer china", "china jewelry factory",
    "stainless steel jewelry manufacturer china", "jewelry supplier china wholesale",
    "premium jewelry manufacturer china", "jewelry factory dongguan",
    "chinese jewelry manufacturer for brands", "china jewelry factory high quality",
    "silver jewelry manufacturer china", "brass jewelry manufacturer china",
    # Durability
    "hard jewelry manufacturer", "durable jewelry manufacturer",
    "waterproof jewelry manufacturer", "tarnish free jewelry supplier",
    "lifetime warranty jewelry manufacturer", "hypoallergenic jewelry manufacturer",
    "long lasting jewelry supplier", "surgical steel jewelry manufacturer",
    # Materials
    "stainless steel jewelry manufacturer", "316L stainless steel jewelry supplier",
    "brass jewelry manufacturer", "sterling silver jewelry manufacturer",
    "925 silver jewelry wholesale", "PVD plated jewelry manufacturer",
    "gold plated stainless steel jewelry wholesale", "rose gold jewelry manufacturer",
    "stainless steel jewelry factory", "nickel free jewelry manufacturer",
    # Private Label
    "private label jewelry manufacturer", "OEM jewelry manufacturer",
    "ODM jewelry manufacturer", "white label jewelry manufacturer",
    "custom jewelry manufacturer", "private label jewelry manufacturer china",
    "contract jewelry manufacturer", "jewelry manufacturing partner",
    # Ecommerce
    "jewelry manufacturer for ecommerce brands", "jewelry supplier for DTC brands",
    "jewelry manufacturer for shopify brands", "wholesale jewelry supplier for online stores",
    "B2B jewelry manufacturer", "jewelry manufacturer for retailers",
    "jewelry supplier for amazon sellers",
    # Quality
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
        # Try loading from environment variable
        import json
        creds_json = os.environ.get('GSC_CREDENTIALS', '{}')
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
    return build('searchconsole', 'v1', credentials=credentials)


def get_keyword_data(service, keyword, days=7):
    """Get ranking data for a specific keyword."""
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

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
        'rowLimit': 10
    }

    try:
        response = service.searchanalytics().query(
            siteUrl=SITE_URL,
            body=request
        ).execute()

        rows = response.get('rows', [])
        if rows:
            total_imp = sum(r.get('impressions', 0) for r in rows)
            total_clicks = sum(r.get('clicks', 0) for r in rows)
            avg_pos = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows)
            avg_pos = avg_pos / total_imp if total_imp > 0 else 0

            return {
                'impressions': total_imp,
                'clicks': total_clicks,
                'position': round(avg_pos, 1),
                'ranking': avg_pos > 0
            }
    except Exception as e:
        print(f"Error fetching {keyword}: {e}")

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
    """Load previous week's data for comparison."""
    data_path = 'data/previous_rankings.json'
    if os.path.exists(data_path):
        with open(data_path, 'r') as f:
            return json.load(f)
    return {}


def save_current_data(data):
    """Save current data for next week's comparison."""
    os.makedirs('data', exist_ok=True)
    with open('data/previous_rankings.json', 'w') as f:
        json.dump(data, f, indent=2)


def generate_weekly_report(current_data, previous_data, overall):
    """Generate weekly email report."""

    # Calculate summary stats
    ranking_count = sum(1 for k, v in current_data.items() if v['ranking'])
    page1_count = sum(1 for k, v in current_data.items() if 0 < v['position'] <= 10)
    top3_count = sum(1 for k, v in current_data.items() if 0 < v['position'] <= 3)

    prev_ranking = sum(1 for k, v in previous_data.items() if v.get('ranking', False))

    # Find improvements and new rankings
    improvements = []
    new_rankings = []

    for kw, data in current_data.items():
        prev = previous_data.get(kw, {})

        if data['ranking'] and not prev.get('ranking', False):
            new_rankings.append((kw, data['position']))
        elif data['ranking'] and prev.get('ranking', False):
            pos_change = prev.get('position', 100) - data['position']
            if pos_change > 2:  # Improved by more than 2 positions
                improvements.append((kw, data['position'], pos_change))

    # Build email HTML
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background: #1a1a2e; color: #d4af37; padding: 20px; text-align: center; }}
            .metric-box {{ display: inline-block; background: #f5f5f5; padding: 15px 25px; margin: 10px; border-radius: 8px; text-align: center; }}
            .metric-value {{ font-size: 28px; font-weight: bold; color: #1a1a2e; }}
            .metric-label {{ font-size: 12px; color: #666; }}
            .section {{ margin: 20px 0; padding: 15px; background: #fafafa; border-radius: 8px; }}
            .section h3 {{ color: #1a1a2e; margin-top: 0; }}
            .success {{ color: #00b894; }}
            .warning {{ color: #fdcb6e; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #1a1a2e; color: #fff; }}
            .badge {{ padding: 3px 10px; border-radius: 12px; font-size: 11px; }}
            .badge-success {{ background: #00b894; color: #fff; }}
            .badge-new {{ background: #e94560; color: #fff; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Petra Jewelry Factory</h1>
            <p>Weekly SEO Report - {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div style="padding: 20px;">
            <h2>📊 Overall Performance (Last 7 Days)</h2>
            <div style="text-align: center;">
                <div class="metric-box">
                    <div class="metric-value">{overall['clicks']}</div>
                    <div class="metric-label">CLICKS</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{overall['impressions']}</div>
                    <div class="metric-label">IMPRESSIONS</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{overall['ctr']}%</div>
                    <div class="metric-label">CTR</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{overall['position']}</div>
                    <div class="metric-label">AVG POSITION</div>
                </div>
            </div>

            <h2>🎯 Keyword Tracking (50 Keywords)</h2>
            <div style="text-align: center;">
                <div class="metric-box">
                    <div class="metric-value">{ranking_count}/50</div>
                    <div class="metric-label">RANKING</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{page1_count}</div>
                    <div class="metric-label">PAGE 1</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{top3_count}</div>
                    <div class="metric-label">TOP 3</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">{ranking_count - prev_ranking:+d}</div>
                    <div class="metric-label">VS LAST WEEK</div>
                </div>
            </div>
    """

    # New rankings section
    if new_rankings:
        html += """
            <div class="section">
                <h3>🎉 NEW RANKINGS THIS WEEK</h3>
                <table>
                    <tr><th>Keyword</th><th>Position</th></tr>
        """
        for kw, pos in new_rankings:
            html += f'<tr><td>{kw}</td><td><span class="badge badge-new">#{pos:.0f}</span></td></tr>'
        html += "</table></div>"

    # Improvements section
    if improvements:
        html += """
            <div class="section">
                <h3>📈 IMPROVED RANKINGS</h3>
                <table>
                    <tr><th>Keyword</th><th>Position</th><th>Change</th></tr>
        """
        for kw, pos, change in sorted(improvements, key=lambda x: -x[2])[:10]:
            html += f'<tr><td>{kw}</td><td>#{pos:.0f}</td><td class="success">↑ {change:.0f}</td></tr>'
        html += "</table></div>"

    # Priority keywords status
    html += """
        <div class="section">
            <h3>⭐ PRIORITY KEYWORDS STATUS</h3>
            <table>
                <tr><th>Keyword</th><th>Position</th><th>Impressions</th><th>Clicks</th></tr>
    """
    for kw in PRIORITY_KEYWORDS:
        data = current_data.get(kw, {})
        pos = data.get('position', 0)
        pos_display = f"#{pos:.0f}" if pos > 0 else "Not ranking"
        html += f"""
            <tr>
                <td>{kw}</td>
                <td>{pos_display}</td>
                <td>{data.get('impressions', 0)}</td>
                <td>{data.get('clicks', 0)}</td>
            </tr>
        """
    html += "</table></div>"

    # Footer
    html += f"""
            <div style="margin-top: 30px; padding: 20px; background: #1a1a2e; color: #fff; text-align: center;">
                <p>View full dashboard: <a href="https://alikaaba-bit.github.io/petra-seo-dashboard/" style="color: #d4af37;">SEO Dashboard</a></p>
                <p style="font-size: 12px; color: #888;">Data from Google Search Console | Report generated automatically</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def send_email(subject, html_content):
    """Send email using SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP credentials not configured. Email not sent.")
        print(f"Would send to: {ALERT_EMAIL}")
        print(f"Subject: {subject}")
        # Save report locally instead
        with open('data/latest_report.html', 'w') as f:
            f.write(html_content)
        print("Report saved to data/latest_report.html")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = ALERT_EMAIL

    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, ALERT_EMAIL, msg.as_string())
        print(f"Email sent to {ALERT_EMAIL}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def main():
    """Main function to generate and send weekly report."""
    print(f"Generating weekly SEO report for {SITE_URL}")
    print(f"Alert email: {ALERT_EMAIL}")

    service = get_service()

    # Get current data
    print("Fetching keyword data...")
    current_data = {}
    for kw in ALL_KEYWORDS:
        current_data[kw] = get_keyword_data(service, kw)

    # Get overall metrics
    overall = get_overall_metrics(service)

    # Load previous data
    previous_data = load_previous_data()

    # Generate report
    html_report = generate_weekly_report(current_data, previous_data, overall)

    # Calculate summary for subject line
    ranking_count = sum(1 for v in current_data.values() if v['ranking'])
    new_rankings = sum(1 for k, v in current_data.items()
                       if v['ranking'] and not previous_data.get(k, {}).get('ranking', False))

    subject = f"Petra SEO Report: {ranking_count}/50 keywords ranking"
    if new_rankings > 0:
        subject += f" (+{new_rankings} new!)"

    # Send email
    send_email(subject, html_report)

    # Save current data for next comparison
    save_current_data(current_data)

    print("Report complete!")


if __name__ == '__main__':
    main()
