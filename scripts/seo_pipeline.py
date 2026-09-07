"""Evidence-led SEO reporting. Only finalized GSC data; no publishing or email side effects."""
import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://petrajewelryfactory.com/"
HOST = urlparse(SITE).netloc
AGENT = "PetraContentAudit/2.0"


def period(days, end):
    return {"start": (end - timedelta(days=days - 1)).isoformat(), "end": end.isoformat(), "days": days}


def metrics(rows):
    impressions = sum(r.get("impressions", 0) for r in rows)
    clicks = sum(r.get("clicks", 0) for r in rows)
    return {"clicks": clicks, "impressions": impressions,
            "ctr": round(100 * clicks / impressions, 3) if impressions else 0,
            "position": round(sum(r.get("position", 0) * r.get("impressions", 0) for r in rows) / impressions, 2) if impressions else None}


def fetch_rows(service, dimensions, window, filters=None):
    """Paginate returned top rows. GSC privacy and internal limits still apply."""
    rows = []
    for offset in range(0, 250000, 25000):
        body = {"startDate": window["start"], "endDate": window["end"], "dimensions": dimensions,
                "type": "web", "dataState": "final", "rowLimit": 25000, "startRow": offset}
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]
        batch = service.searchanalytics().query(siteUrl=SITE, body=body).execute(num_retries=3).get("rows", [])
        rows.extend(batch)
        if len(batch) < 25000:
            return rows
    raise RuntimeError("Pagination safety limit reached; refusing to publish an incomplete refresh.")


def google_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
    if os.environ.get("GSC_CREDENTIALS"):
        creds = service_account.Credentials.from_service_account_info(json.loads(os.environ["GSC_CREDENTIALS"]), scopes=scopes)
    else:
        creds = service_account.Credentials.from_service_account_file(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json"), scopes=scopes)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def safe_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc == HOST and not parsed.username and not parsed.password


def path_of(url):
    parsed = urlparse(url)
    return (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")


def normalize_root(url):
    return SITE if url == SITE.rstrip('/') else url


class PageHTML(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.title, self.description, self.canonical = url, "", "", ""
        self.headings, self.links, self.robots, self.text = [], [], [], []
        self.capture, self.buffer, self.hidden, self.h1_count = None, [], 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("title", "h1", "h2", "h3"):
            self.capture, self.buffer = tag, []
            self.h1_count += int(tag == "h1")
        if tag == "meta":
            name = a.get("name", "").lower()
            if name == "description":
                self.description = a.get("content", "")
            if name in ("robots", "googlebot"):
                self.robots.append(a.get("content", "").lower())
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = urljoin(self.url, a.get("href", ""))
        if tag == "a" and a.get("href"):
            link = urldefrag(urljoin(self.url, a["href"]))[0]
            if safe_url(link) and not urlparse(link).query:
                self.links.append(link)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag == self.capture:
            value = " ".join(" ".join(self.buffer).split())
            if tag == "title":
                self.title = value
            else:
                self.headings.append({"level": tag, "text": value})
            self.capture, self.buffer = None, []

    def handle_data(self, text):
        if not self.hidden:
            self.text.append(text)
            if self.capture:
                self.buffer.append(text)


def request_page(session, url):
    """Follow only same-host HTTPS redirects; bound response sizes."""
    for _ in range(6):
        if not safe_url(url):
            raise ValueError("URL is outside the configured website")
        with session.get(url, timeout=(10, 25), allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError("Response exceeds crawl size limit")
                chunks.append(chunk)
            return response.status_code, b"".join(chunks).decode(response.encoding or "utf-8", errors="replace"), url, dict(response.headers)
    raise ValueError("Redirect limit exceeded")


def crawl(urls, limit=100):
    import requests
    import trafilatura
    from defusedxml import ElementTree
    import time
    session = requests.Session()
    session.headers["User-Agent"] = AGENT
    robot = RobotFileParser()
    warnings, results = [], []
    try:
        code, body, _, _ = request_page(session, SITE + "robots.txt")
        if code == 200:
            robot.parse(body.splitlines())
        elif code == 404:
            robot.parse([])
        else:
            return [], [f"Crawl skipped: robots.txt returned HTTP {code}"]
    except Exception as exc:
        return [], [f"Crawl skipped: robots.txt unavailable ({type(exc).__name__})"]
    sitemap_queue = list(robot.site_maps() or []) + [SITE + "sitemap_index.xml", SITE + "wp-sitemap.xml"]
    candidates = list(dict.fromkeys([SITE] + urls))
    seen_maps = set()
    while sitemap_queue and len(seen_maps) < 15:
        url = sitemap_queue.pop(0)
        if url in seen_maps or not safe_url(url) or not robot.can_fetch(AGENT, url):
            continue
        seen_maps.add(url)
        try:
            code, body, _, _ = request_page(session, url)
            if code != 200:
                continue
            xml = ElementTree.fromstring(body)
            locations = [e.text for e in xml.iter() if e.tag.split("}")[-1] == "loc" and e.text]
            if xml.tag.split("}")[-1] == "sitemapindex":
                sitemap_queue.extend(locations)
            else:
                candidates.extend(locations)
        except Exception:
            warnings.append(f"Could not parse sitemap: {path_of(url)}")
    queue = list(dict.fromkeys(candidates))
    seen = set()
    delay = max(0.3, robot.crawl_delay(AGENT) or 0)
    while queue and len(results) < limit:
        url = normalize_root(queue.pop(0))
        if url in seen or not safe_url(url) or urlparse(url).query:
            continue
        if re.search(r"\.(png|jpg|jpeg|pdf|svg|webp|zip|xml|gif)$", url, re.I):
            continue
        seen.add(url)
        if not robot.can_fetch(AGENT, url):
            results.append({"url": url, "path": path_of(url), "issues": ["Blocked by robots.txt"], "crawl_status": "blocked", "links": []})
            continue
        time.sleep(delay)
        try:
            status, body, final_url, headers = request_page(session, url)
            if "text/html" not in headers.get("Content-Type", headers.get("content-type", "")) and status == 200:
                continue
            page = PageHTML(final_url)
            page.feed(body)
            text = trafilatura.extract(body, include_tables=True) or ""
            issues = []
            if status != 200:
                issues.append(f"HTTP {status}")
            if final_url != url:
                issues.append("Redirects to " + path_of(final_url))
            if not page.title:
                issues.append("Missing title")
            if not page.description:
                issues.append("Missing meta description")
            if not page.canonical:
                issues.append("Missing canonical")
            elif page.canonical.rstrip("/") != final_url.rstrip("/"):
                issues.append("Canonical points to a different URL")
            if page.h1_count != 1:
                issues.append(f"Review heading structure: {page.h1_count} H1 headings")
            robots_text = " ".join(page.robots) + " " + headers.get("X-Robots-Tag", headers.get("x-robots-tag", ""))
            if "noindex" in robots_text.lower():
                issues.append("Noindex directive")
            visible = " ".join(page.text).lower()
            for marker in ("hello@outgrid.com", "(239) 555-0108", "lorem ipsum", "competitive interest rates", "flexible repayment options", "4140 parker rd"):
                if marker in visible:
                    issues.append("Template placeholder: " + marker)
            links = sorted(set(page.links))
            results.append({"url": url, "path": path_of(url), "final_url": final_url, "http_status": status,
                            "crawl_status": "checked", "title": page.title, "description": page.description,
                            "canonical": page.canonical, "headings": page.headings, "word_count": len(text.split()),
                            "text": text[:30000], "links": links, "issues": issues})
            queue.extend(link for link in links if link not in seen)
        except Exception as exc:
            results.append({"url": url, "path": path_of(url), "crawl_status": "error", "issues": ["Crawl failed: " + type(exc).__name__], "links": []})
    by_url = {p["url"]: p for p in results}
    for page in results:
        page["incoming_links"] = [p["path"] for p in results if p["url"] != page["url"] and page["url"] in p.get("links", [])]
        for link in page.get("links", []):
            if by_url.get(link, {}).get("http_status", 200) >= 400:
                page["issues"].append("Broken internal link: " + path_of(link))
    for field in ("title", "description"):
        groups = defaultdict(list)
        for page in results:
            if page.get(field) and page.get("http_status") == 200 and page["url"] == page.get("final_url"):
                groups[page[field]].append(page)
        for group in groups.values():
            if len(group) > 1:
                for page in group:
                    page["issues"].append("Duplicate " + field)
    if queue:
        warnings.append(f"Crawl limited to {limit} pages; internal-link coverage is partial.")
    return results, warnings


def brand(query):
    return bool(re.search(r"\bpetra\b", query, re.I))


def grouped(rows, index):
    result = defaultdict(list)
    for row in rows:
        result[normalize_root(row["keys"][index])].append(row)
    return {key: metrics(values) for key, values in result.items()}


def build_pages(current, previous, inventory, editorial):
    current_pages, previous_pages = grouped(current["pages"], 0), grouped(previous["pages"], 0)
    query_pages = defaultdict(list)
    for row in current["query_pages"]:
        query_pages[normalize_root(row["keys"][1])].append({"query": row["keys"][0], **metrics([row]), "branded": brand(row["keys"][0])})
    content = {}
    for entry in inventory:
        content.setdefault(normalize_root(entry["url"]), entry)
    topics = {urljoin(SITE, t["page"]): t for t in editorial.get("topics", [])}
    pages = []
    for url in sorted(set(current_pages) | set(previous_pages) | set(content) | set(topics)):
        if not safe_url(url):
            continue
        now, before = current_pages.get(url, metrics([])), previous_pages.get(url, metrics([]))
        queries = sorted(query_pages[url], key=lambda q: q["impressions"], reverse=True)
        topic = topics.get(url, {})
        audit = content.get(url, {})
        business = topic.get("business_value", 2 if any(x in url for x in ("manufactur", "private-label", "services")) else 1)
        issues = audit.get("issues", [])
        evidence, actions = [], []
        if any(x.startswith(("Template placeholder", "HTTP 4", "HTTP 5", "Noindex", "Blocked by robots")) for x in issues):
            evidence.append("Website issue needs attention")
            actions.append("Resolve the flagged website issues, then verify the live page.")
        near = [q for q in queries if not q["branded"] and 4 <= (q["position"] or 0) <= 20 and q["impressions"] >= 20]
        if near:
            evidence.append(f"{len(near)} non-brand queries in positions 4–20 with at least 20 impressions")
            actions.append("Review intent and expand the existing page around the relevant query evidence.")
        if before["clicks"] >= 10 and now["clicks"] < before["clicks"] * 0.8:
            evidence.append(f"Clicks declined from {before['clicks']} to {now['clicks']}")
            actions.append("Check lost queries, demand, indexing and recent edits before rewriting.")
        if (before["clicks"] >= 10 and min(now["impressions"], before["impressions"]) >= 100
                and now["position"] is not None and before["position"] is not None
                and abs(now["position"] - before["position"]) <= 2 and now["ctr"] < before["ctr"] * 0.7):
            evidence.append(f"CTR fell from {before['ctr']}% to {now['ctr']}% with broadly stable average position")
            actions.append("Review query mix, search appearance and title relevance; the cause of the CTR change is not established.")
        if not actions and issues:
            actions.append("Review the on-page findings and improve the page's presentation in search.")
            evidence.append(f"{len(issues)} crawl findings")
        if not actions:
            actions.append("Review buyer questions and collect more search data before choosing a major rewrite.")
            evidence.append("Limited search evidence" if now["impressions"] < 100 else "Maintain and monitor")
        score = business * 10 + min(now["impressions"] / 20, 20) + min(len(near) * 5, 20) + (35 if any("Template placeholder" in i or "Noindex" in i for i in issues) else 0) + (15 if before["clicks"] >= 10 and now["clicks"] < before["clicks"] * .8 else 0)
        page = {"url": url, "path": path_of(url), "current": now, "previous": before, "queries": queries,
                "topic": topic.get("topic", "Unassigned"), "intent": topic.get("intent", "Needs review"), "business_value": business,
                "priority_score": round(score), "confidence": "Low sample" if now["impressions"] < 100 or now["clicks"] < 10 else "Directional evidence",
                "evidence": evidence, "actions": actions, "effort": "Review", "audit": audit,
                "index_status": "Not inspected", "click_change": now["clicks"] - before["clicks"]}
        pages.append(page)
    return sorted(pages, key=lambda p: p["priority_score"], reverse=True)


def enrich_briefs(pages):
    stop = {"the", "and", "for", "your", "with", "from", "jewelry", "petra", "manufacturing", "manufacturer"}
    for page in pages:
        query = next((q["query"] for q in page["queries"] if not q["branded"]), None)
        topic = page["topic"] if page["topic"] != "Unassigned" else query
        title = (topic[:70].rstrip() + " | Petra") if topic else None
        headings = " ".join(h["text"] for h in page["audit"].get("headings", [])).lower()
        review_queries = [q["query"] for q in page["queries"] if not q["branded"] and q["query"].lower() not in headings][:6]
        tokens = set(re.findall(r"[a-z]{3,}", (topic or page["path"]).lower())) - stop
        links = []
        for source in pages:
            audit = source["audit"]
            if source["url"] == page["url"] or page["url"] in audit.get("links", []) or not audit.get("text"):
                continue
            overlap = tokens & set(re.findall(r"[a-z]{3,}", audit["text"].lower()))
            if overlap:
                links.append({"source": source["path"], "target": page["path"], "anchor": topic or page["path"], "reason": "Shared terms: " + ", ".join(sorted(overlap)), "overlap": len(overlap)})
        checks = ["Minimum order by design/material", "Sample approval process and timing", "Production lead time and what changes it", "Quality checks supported by real evidence", "Customization and packaging options", "Clear next step to request a quote"] if page["business_value"] >= 2 else ["Answer the actual query intent", "Add original examples and evidence", "Link to the relevant service page"]
        page["brief"] = {"suggested_title": title, "suggested_h1": topic, "query_review": review_queries,
                         "buyer_questions": checks, "internal_links": sorted(links, key=lambda x: x["overlap"], reverse=True)[:4],
                         "note": "Draft suggestions. Confirm intent, company facts and natural link placement before publishing. A query missing from headings is not proof the content is missing."}


def overlap_candidates(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.get("impressions", 0) >= 10 and not brand(row["keys"][0]):
            groups[row["keys"][0]].append({"url": row["keys"][1], **metrics([row])})
    return [{"query": query, "pages": pages, "verdict": "Review intent and URL changes over time; overlap alone is not cannibalization."} for query, pages in groups.items() if len(pages) > 1]


def change_results(service, changes, end):
    results = []
    for change in changes[:50]:
        try:
            published = date.fromisoformat(change["published_at"])
            url = urljoin(SITE, change["page"])
            if not safe_url(url):
                raise ValueError("Wrong site")
        except (KeyError, ValueError, TypeError):
            results.append({"change": change, "error": "Invalid page or published_at date"})
            continue
        windows = []
        for days in (28, 56):
            post_end = published + timedelta(days=days - 1)
            if post_end > end:
                windows.append({"days": days, "status": "Collecting data", "ready_on": post_end.isoformat()})
                continue
            filters = [{"dimension": "page", "operator": "equals", "expression": url}]
            before = metrics(fetch_rows(service, [], period(days, published - timedelta(days=1)), filters))
            after = metrics(fetch_rows(service, [], period(days, post_end), filters))
            windows.append({"days": days, "before": before, "after": after,
                            "status": "Inconclusive: low sample" if min(before["clicks"], after["clicks"]) < 20 else "Observed change; not causal proof"})
        results.append({"change": change, "windows": windows})
    return results


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl", action="store_true")
    parser.add_argument("--crawl-limit", type=int, default=100)
    parser.add_argument("--inspect-limit", type=int, default=10)
    parser.add_argument("--crawl-only", action="store_true", help="Refresh website inventory without changing Search Console timestamps")
    args = parser.parse_args()
    editorial = json.loads((ROOT / "data/editorial.json").read_text())
    inventory_path = ROOT / "data/content.json"
    inventory_data = json.loads(inventory_path.read_text()) if inventory_path.exists() else {"pages": [], "generated_at": None, "warnings": []}
    if args.crawl_only:
        pages, warnings = crawl([urljoin(SITE, t["page"]) for t in editorial["topics"]], args.crawl_limit)
        write_json(inventory_path, {"pages": pages, "generated_at": datetime.now(timezone.utc).isoformat(), "warnings": warnings})
        print(f"Crawled {len(pages)} pages; Search Console data left unchanged.")
        return
    service = google_service()
    end = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=3)
    datasets = {}
    for label, window in (("current", period(28, end)), ("previous", period(28, end - timedelta(days=28)))):
        datasets[label] = {"period": window}
        for key, dims in (("overall", []), ("daily", ["date"]), ("pages", ["page"]), ("queries", ["query"]), ("query_pages", ["query", "page"])):
            datasets[label][key] = fetch_rows(service, dims, window)
    if args.crawl:
        urls = [r["keys"][0] for r in datasets["current"]["pages"]] + [urljoin(SITE, t["page"]) for t in editorial["topics"]]
        inventory, warnings = crawl(urls, args.crawl_limit)
        inventory_data = {"pages": inventory, "generated_at": datetime.now(timezone.utc).isoformat(), "warnings": warnings}
        write_json(inventory_path, inventory_data)
    pages = build_pages(datasets["current"], datasets["previous"], inventory_data["pages"], editorial)
    for page in pages[:max(0, args.inspect_limit)]:
        try:
            response = service.urlInspection().index().inspect(body={"inspectionUrl": page["url"], "siteUrl": SITE, "languageCode": "en-US"}).execute(num_retries=2)
            inspection = response.get("inspectionResult", {}).get("indexStatusResult", {})
            page["index_status"] = inspection.get("coverageState", "Unknown")
            page["inspection"] = {k: inspection[k] for k in ("verdict", "lastCrawlTime", "googleCanonical", "userCanonical", "robotsTxtState", "indexingState") if k in inspection}
            if inspection.get("verdict") in ("FAIL", "NEUTRAL"):
                page["evidence"].insert(0, "Index inspection: " + page["index_status"])
                page["actions"].insert(0, "Investigate index coverage and page usefulness before expanding this content.")
                page["priority_score"] += 15
        except Exception as exc:
            page["index_status"] = "Inspection unavailable: " + type(exc).__name__
    pages.sort(key=lambda p: p["priority_score"], reverse=True)
    enrich_briefs(pages)
    from update_data import ALL_KEYWORDS, HIGH_PRIORITY, TARGET_KEYWORDS
    query_metrics = {k.lower(): v for k, v in grouped(datasets["current"]["queries"], 0).items()}
    tracked = {}
    for keyword in ALL_KEYWORDS:
        m = query_metrics.get(keyword.lower(), metrics([]))
        position = m["position"]
        tracked[keyword] = {**m, "avg_position": position or 0, "is_priority": keyword in HIGH_PRIORITY,
                            "status": "No query data" if position is None else "Top 3" if position <= 3 else "Top 10" if position <= 10 else "Observed"}
    overall = metrics(datasets["current"]["overall"])
    result = {"schema_version": 2, "generated_at": datetime.now(timezone.utc).isoformat(), "site_url": SITE,
              "period": datasets["current"]["period"], "previous_period": datasets["previous"]["period"],
              "overall": overall, "previous_overall": metrics(datasets["previous"]["overall"]),
              "daily": [{"date": r["keys"][0], **metrics([r])} for r in datasets["current"]["daily"]],
              "pages": pages, "overlap_candidates": overlap_candidates(datasets["current"]["query_pages"]),
              "tracked_keywords": tracked, "target_categories": TARGET_KEYWORDS,
              "queries": [{"query": k, **v, "branded": brand(k)} for k, v in grouped(datasets["current"]["queries"], 0).items()],
              "change_results": change_results(service, editorial.get("changes", []), end),
              "content_generated_at": inventory_data["generated_at"], "crawl_warnings": inventory_data.get("warnings", []),
              "measurement": {"leads": "Not connected", "note": "Connect aggregate organic enquiries and qualified leads; do not publish customer details in this public repository."},
              "data_notes": ["Finalized web-search data, dates in Pacific Time.", "Query rows omit anonymized searches and may be limited by Google; they need not sum to page or property totals.", "Average position is not a fixed country/device rank.", "Priority scores organize review work; they do not forecast traffic gains."],
              "overall_metrics": {"total_clicks": overall["clicks"], "total_impressions": overall["impressions"], "avg_ctr": overall["ctr"], "avg_position": overall["position"], "period_start": datasets["current"]["period"]["start"], "period_end": end.isoformat()},
              "top_pages": [{"page": p["path"], **p["current"]} for p in pages]}
    write_json(ROOT / "data/latest.json", result)
    write_json(ROOT / "data" / f"history_{datetime.now(timezone.utc).date()}.json", result)
    print(f"Updated {len(pages)} pages and {len(result['queries'])} queries through {end}.")


if __name__ == "__main__":
    main()
