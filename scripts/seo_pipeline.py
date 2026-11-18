"""Evidence-led SEO reporting. Only finalized GSC data; no publishing or email side effects."""
import argparse
import codecs
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from email.message import Message
from html import unescape
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
MAX_RESPONSE_BYTES = 4_000_000
PLACEHOLDERS = ("hello@outgrid.com", "(239) 555-0108", "lorem ipsum",
                "competitive interest rates", "flexible repayment options", "4140 parker rd",
                "sophie moore", "elliot ellington", "50+ top companies")


class CrawlError(ValueError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


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
    return ((parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
            + ("#" + parsed.fragment if parsed.fragment else ""))


def normalize_root(url):
    return SITE if url == SITE.rstrip('/') else url


class PageHTML(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.title, self.description, self.canonical = url, "", "", ""
        self.headings, self.links, self.fragment_links, self.robots, self.text = [], [], [], [], []
        self.capture, self.buffer, self.hidden, self.h1_count = None, [], 0, 0
        self.jsonld, self.schema, self.schema_errors = None, [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.jsonld = []
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
            observed = urljoin(self.url, a["href"])
            if safe_url(observed) and urlparse(observed).fragment.startswith("/"):
                self.fragment_links.append(observed)
            link = urldefrag(observed)[0]
            if safe_url(link) and not urlparse(link).query:
                self.links.append(link)

    def handle_endtag(self, tag):
        if tag == "script" and self.jsonld is not None:
            try:
                self.schema.append(json.loads("".join(self.jsonld)))
            except (ValueError, RecursionError):
                self.schema_errors += 1
            self.jsonld = None
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
        if self.jsonld is not None:
            self.jsonld.append(text)
        if not self.hidden:
            self.text.append(text)
            if self.capture:
                self.buffer.append(text)

    def schema_summary(self):
        types, queue = set(), list(self.schema)
        while queue:
            item = queue.pop()
            if isinstance(item, list):
                queue.extend(item)
            elif isinstance(item, dict):
                value = item.get("@type", [])
                types.update(v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str))
                queue.extend(item.values())
        return {"schema_types": sorted(types), "schema_hash": hashlib.sha256(json.dumps(self.schema, sort_keys=True).encode()).hexdigest(),
                "schema_errors": self.schema_errors}


def placeholder_matches(body):
    """Scan served payload as well as text: hidden demo content is still shipped."""
    decoded = unescape(body).casefold()
    candidates = [decoded, re.sub(r"<[^>]*>", " ", decoded)]
    candidates = [" ".join(value.split()) for value in candidates]
    return [marker for marker in PLACEHOLDERS if any(marker in value for value in candidates)]


def decode_response_body(body, headers):
    """Use actual encoding declarations, never Requests' implicit text/* Latin-1."""
    for marker, encoding in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                             (codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"),
                             (codecs.BOM_UTF16_BE, "utf-16")):
        if body.startswith(marker):
            return body.decode(encoding, errors="replace")

    def charset(content_type):
        message = Message()
        message["Content-Type"] = content_type
        return message.get_content_charset()

    class EncodingMeta(HTMLParser):
        encoding = None

        def handle_starttag(self, tag, attrs):
            if tag != "meta" or self.encoding:
                return
            attributes = dict(attrs)
            self.encoding = attributes.get("charset")
            if not self.encoding and (attributes.get("http-equiv") or "").lower() == "content-type":
                self.encoding = charset(attributes.get("content") or "")

    declared = charset(next((value for key, value in headers.items() if key.lower() == "content-type"), ""))
    if declared:
        try:
            return body.decode(declared, errors="replace")
        except (LookupError, UnicodeError, ValueError):
            pass
    # HTML's declaration prescan is bounded; comments and script text are not meta tags.
    prefix = body[:1024].decode("ascii", errors="ignore")
    meta = EncodingMeta()
    try:
        meta.feed(prefix)
    except (AssertionError, ValueError):
        pass  # Malformed markup must not prevent the encoding fallback.
    xml = re.match(r'\s*<\?xml\b[^>]*\bencoding\s*=\s*[\'\"]([^\'\"]+)', prefix, re.I)
    for encoding in (meta.encoding, xml.group(1) if xml else None):
        if encoding:
            try:
                return body.decode(encoding, errors="replace")
            except (LookupError, UnicodeError, ValueError):
                pass
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("windows-1252", errors="replace")


def request_page(session, url):
    """Follow only same-host HTTPS redirects; bound response sizes."""
    for _ in range(6):
        if not safe_url(url):
            raise CrawlError("unsafe_redirect", "URL is outside the configured website")
        with session.get(url, timeout=(10, 25), allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise CrawlError("response_too_large", f"Response exceeds {MAX_RESPONSE_BYTES:,}-byte crawl limit",
                                     limit_bytes=MAX_RESPONSE_BYTES, bytes_read=size, http_status=response.status_code)
                chunks.append(chunk)
            return response.status_code, decode_response_body(b"".join(chunks), response.headers), url, dict(response.headers)
    raise CrawlError("redirect_limit", "Redirect limit exceeded")


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
            warnings.append("robots.txt returned HTTP 404; crawling allowed, policy unavailable.")
        else:
            return [], [f"Crawl skipped: robots.txt returned HTTP {code}"]
    except Exception as exc:
        return [], [f"Crawl skipped: robots.txt unavailable ({type(exc).__name__})"]
    declared_maps = list(robot.site_maps() or [])
    sitemap_queue = declared_maps + [SITE + "sitemap_index.xml", SITE + "wp-sitemap.xml", SITE + "sitemap.xml"]
    candidates = list(dict.fromkeys([SITE] + urls))
    seen_maps = set()
    valid_maps, map_failures = 0, []
    while sitemap_queue and len(seen_maps) < 15:
        url = sitemap_queue.pop(0)
        if url in seen_maps or not safe_url(url) or not robot.can_fetch(AGENT, url):
            continue
        seen_maps.add(url)
        try:
            code, body, _, _ = request_page(session, url)
            if code != 200:
                map_failures.append(f"{path_of(url)}: HTTP {code}")
                continue
            xml = ElementTree.fromstring(body)
            if xml.tag.split("}")[-1] not in ("sitemapindex", "urlset"):
                raise ValueError("Not a sitemap document")
            valid_maps += 1
            locations = [e.text for e in xml.iter() if e.tag.split("}")[-1] == "loc" and e.text]
            if xml.tag.split("}")[-1] == "sitemapindex":
                sitemap_queue.extend(locations)
                declared_maps.extend(locations)
            else:
                candidates.extend(locations)
        except Exception as exc:
            map_failures.append(f"{path_of(url)}: {type(exc).__name__}")
    if not valid_maps:
        warnings.append("No readable sitemap found. " + "; ".join(map_failures))
    else:
        warnings.extend("Sitemap unavailable: " + failure for failure in map_failures
                        if any(failure.startswith(path_of(u) + ":") for u in declared_maps))
    if sitemap_queue:
        warnings.append("Sitemap discovery limit reached; coverage is partial.")
    queue = list(dict.fromkeys(candidates))
    seen = set()
    delay = max(0.3, robot.crawl_delay(AGENT) or 0)
    while queue and len(results) < limit:
        url = normalize_root(urldefrag(queue.pop(0))[0])
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
                results.append({"url": url, "path": path_of(url), "http_status": status,
                                "crawl_status": "unsupported", "issues": ["Expected HTML; received another content type"], "links": []})
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
            issues.extend("Template placeholder: " + marker for marker in placeholder_matches(body))
            schema = page.schema_summary()
            if page.schema_errors:
                issues.append("Invalid JSON-LD syntax; review schema")
            if not page.schema:
                issues.append("No JSON-LD found; review relevant truthful markup")
            links = sorted(set(page.links))
            results.append({"url": url, "path": path_of(url), "final_url": final_url, "http_status": status,
                            "crawl_status": "checked", "title": page.title, "description": page.description,
                            "canonical": page.canonical, "headings": page.headings, "word_count": len(text.split()),
                            "robots": sorted(set(page.robots + [headers.get("X-Robots-Tag", headers.get("x-robots-tag", "")).lower()])), **schema,
                            "text": text[:30000], "links": links, "fragment_links": sorted(set(page.fragment_links)), "issues": issues})
            queue.extend(link for link in links if link not in seen)
        except Exception as exc:
            error = {"code": exc.code, "message": str(exc), **exc.details} if isinstance(exc, CrawlError) else {
                "code": type(exc).__name__, "message": "Request or parsing failed (" + type(exc).__name__ + ")"}
            results.append({"url": url, "path": path_of(url), "crawl_status": "error", "error": error,
                            **({"http_status": error["http_status"]} if "http_status" in error else {}),
                            "issues": ["Crawl failed: " + error["message"]], "links": []})
            warnings.append(f"{path_of(url)}: {error['message']}")
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


def required_pages(editorial):
    return list(dict.fromkeys([SITE] + [urljoin(SITE, t["page"]) for t in editorial.get("topics", [])
                                       if t.get("intent") == "commercial"]))


def url_collisions(urls):
    groups = defaultdict(set)
    for url in urls:
        if safe_url(url):
            groups[normalize_root(urldefrag(url)[0])].add(normalize_root(url))
    return [{"request_url": base, "urls": sorted(variants),
             "note": "URL variants share one HTTP document. Review routing; do not merge automatically."}
            for base, variants in sorted(groups.items()) if len(variants) > 1]


def crawl_health(pages, warnings, required):
    by_url = {normalize_root(p["url"]): p for p in pages}
    blockers, notes = [], list(warnings)
    coverage = {"recorded": len(pages), "html_ok": 0, "http_errors": 0, "errors": 0, "blocked": 0, "unsupported": 0}
    for page in pages:
        state, code = page.get("crawl_status"), page.get("http_status") or 0
        if state in ("error", "blocked", "unsupported"):
            coverage[{"error": "errors", "blocked": "blocked", "unsupported": "unsupported"}[state]] += 1
        if state == "checked" and code == 200:
            coverage["html_ok"] += 1
        if code >= 400:
            coverage["http_errors"] += 1
            notes.append(f"{path_of(page['url'])}: HTTP {code}")
        if state == "error":
            blockers.append(f"{path_of(page['url'])}: " + "; ".join(page.get("issues") or ["Crawl failed"]))
        blockers.extend(f"{path_of(page['url'])}: {issue}" for issue in page.get("issues", [])
                        if issue.startswith("Template placeholder"))
        if state in ("blocked", "unsupported"):
            notes.append(f"{path_of(page['url'])}: {state}; HTML not checked")
    for url in required:
        page = by_url.get(normalize_root(url))
        if not page:
            blockers.append(f"Required page {path_of(url)}: not checked")
        elif page.get("crawl_status") != "checked" or page.get("http_status") != 200:
            blockers.append(f"Required page {path_of(url)}: {page.get('crawl_status', 'unknown')}, HTTP {page.get('http_status', 'unavailable')}")
        elif page.get("final_url", url) != url:
            blockers.append(f"Required page {path_of(url)}: redirects; destination needs review")
        elif "Noindex directive" in page.get("issues", []):
            blockers.append(f"Required page {path_of(url)}: noindex directive")
    urls = [u for p in pages for u in [p["url"], *p.get("fragment_links", [])]]
    collisions = url_collisions(urls)
    if collisions:
        notes.append("Fragment URL variants share an HTTP document; review route identity.")
    blockers, notes = list(dict.fromkeys(blockers)), list(dict.fromkeys(notes))
    return {"status": "failed" if blockers else "warning" if notes else "passed", "coverage": coverage,
            "required_urls": required, "blockers": blockers, "warnings": notes, "url_collisions": collisions}


def record_crawl(pages, warnings, required, output_dir):
    attempted_at = datetime.now(timezone.utc).isoformat()
    report = {"attempted_at": attempted_at, **crawl_health(pages, warnings, required), "pages": pages}
    write_json(output_dir / "crawl-health.json", report)
    inventory = {"pages": pages, "generated_at": attempted_at, "warnings": report["warnings"]}
    if report["status"] != "failed":
        write_json(output_dir / "content.json", inventory)
    return inventory, report


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
        if any(x.startswith(("Template placeholder", "HTTP 4", "HTTP 5", "Noindex", "Blocked by robots", "Crawl failed")) for x in issues):
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


def brief_blocked(page):
    audit = page.get("audit", {})
    return (bool(urlparse(page["url"]).fragment) or audit.get("crawl_status") != "checked" or audit.get("http_status") != 200
            or audit.get("final_url", page["url"]) != page["url"]
            or any(i.startswith(("Template placeholder", "Noindex")) for i in audit.get("issues", [])))


def enrich_briefs(pages):
    stop = {"the", "and", "for", "your", "with", "from", "jewelry", "petra", "manufacturing", "manufacturer"}
    for page in pages:
        if brief_blocked(page):
            page["brief"] = {"status": "blocked", "suggested_title": None, "suggested_h1": None,
                             "query_review": [], "buyer_questions": [], "internal_links": [],
                             "note": "Brief on hold. Resolve crawl, access or website blockers and verify this exact URL before drafting."}
            continue
        query = next((q["query"] for q in page["queries"] if not q["branded"]), None)
        topic = page["topic"] if page["topic"] != "Unassigned" else query
        headings = " ".join(h["text"] for h in page["audit"].get("headings", [])).lower()
        review_queries = [q["query"] for q in page["queries"] if not q["branded"] and q["query"].lower() not in headings][:6]
        tokens = set(re.findall(r"[a-z]{3,}", (topic or page["path"]).lower())) - stop
        links = []
        for source in pages:
            audit = source["audit"]
            if brief_blocked(source) or source["url"] == page["url"] or page["url"] in audit.get("links", []) or not audit.get("text"):
                continue
            overlap = tokens & set(re.findall(r"[a-z]{3,}", audit["text"].lower()))
            if overlap:
                links.append({"source": source["path"], "target": page["path"], "anchor": topic or page["path"], "reason": "Shared terms: " + ", ".join(sorted(overlap)), "overlap": len(overlap)})
        checks = ["Minimum order by design/material", "Sample approval process and timing", "Production lead time and what changes it", "Quality checks supported by real evidence", "Customization and packaging options", "Clear next step to request a quote"] if page["business_value"] >= 2 else ["Answer the actual query intent", "Add original examples and evidence", "Link to the relevant service page"]
        page["brief"] = {"status": "planning", "suggested_title": None, "suggested_h1": None, "query_review": review_queries,
                         "buyer_questions": checks, "internal_links": sorted(links, key=lambda x: x["overlap"], reverse=True)[:4],
                         "note": "Planning evidence only. Titles and copy come from the reviewed workspace packet after fact and intent approval. Confirm natural link placement before publishing. A query missing from headings is not proof the content is missing."}


def overlap_candidates(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.get("impressions", 0) >= 10 and not brand(row["keys"][0]):
            groups[row["keys"][0]].append({"url": row["keys"][1], **metrics([row])})
    return [{"query": query, "pages": pages, "verdict": "Review intent and URL changes over time; overlap alone is not cannibalization."} for query, pages in groups.items() if len(pages) > 1]


def change_results(service, changes, end, limit=50):
    results = []
    for number, change in enumerate(changes):
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
            if number >= limit:
                windows.append({"days": days, "status": "Deferred: follow-up request limit", "ready_on": post_end.isoformat()})
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


def record_search_health(output_dir, error=None):
    """Record attempt freshness separately; never copy raw exception/credential text."""
    snapshot = {}
    try:
        snapshot = json.loads((output_dir / "latest.json").read_text())
        if not isinstance(snapshot, dict):
            snapshot = {}
    except (OSError, ValueError):
        pass
    failure = None
    if error is not None:
        http_status = getattr(getattr(error, "resp", None), "status", None)
        http_status = http_status if type(http_status) is int else None
        category = "access_denied" if http_status == 403 else "authentication_failed" if http_status == 401 else "collection_failed"
        action = ("Review the workflow principal's access to the exact Search Console property and API quota. "
                  "Browser access is a separate authorization. Do not change access or resume email workflows without owner approval."
                  if http_status == 403 else
                  "Review the configured workflow authentication through its authorized owner; do not log credentials."
                  if http_status == 401 else
                  "Review the failed collection step. Keep the last successful snapshot until a complete refresh succeeds.")
        failure = {"type": type(error).__name__, "http_status": http_status, "category": category, "action": action}
    report = {"schema_version": 1, "attempted_at": datetime.now(timezone.utc).isoformat(),
              "site_url": SITE, "source": "Google Search Console", "status": "failed" if error is not None else "success",
              "last_successful_snapshot": {"generated_at": snapshot.get("generated_at"), "period": snapshot.get("period")},
              "error": failure}
    write_json(output_dir / "search-health.json", report)
    return report


def fail_search_refresh(output_dir, error):
    status = getattr(getattr(error, "resp", None), "status", None)
    status = status if type(status) is int else None
    suffix = f"; HTTP {status}" if status is not None else ""
    try:
        record_search_health(output_dir, error)
    except Exception:
        print(f"Search Console refresh failed ({type(error).__name__}{suffix}); diagnostic-write-failed.")
    else:
        print(f"Search Console refresh failed ({type(error).__name__}{suffix}). Previous search snapshot unchanged; see search-health.json.")
    raise SystemExit(1) from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl", action="store_true")
    parser.add_argument("--crawl-limit", type=int, default=100)
    parser.add_argument("--inspect-limit", type=int, default=10)
    parser.add_argument("--crawl-only", action="store_true", help="Refresh website inventory without changing Search Console timestamps")
    parser.add_argument("--workspace-only", action="store_true", help="Build offline reviews, drafts and follow-ups from saved inputs; no authentication")
    parser.add_argument("--followup-limit", type=int, default=50, help="Bound GSC follow-up collection; deferred records remain visible")
    parser.add_argument("--fail-on-health", action="store_true", help="Exit 1 after recording a failed crawl health check; requires --crawl or --crawl-only")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data", help="Output directory; use tmp/ for local checks")
    args = parser.parse_args()
    if args.workspace_only and (args.crawl or args.crawl_only or args.fail_on_health):
        parser.error("--workspace-only cannot be combined with crawl options")
    if args.fail_on_health and not (args.crawl or args.crawl_only):
        parser.error("--fail-on-health requires --crawl or --crawl-only")
    if args.crawl_limit < 1 or not 0 <= args.followup_limit <= 1000:
        parser.error("Use a positive crawl limit and a follow-up limit from 0 to 1000")
    editorial = json.loads((ROOT / "data/editorial.json").read_text())
    from seo_workspace import write_workspace
    if args.workspace_only:
        write_workspace(editorial, args.output_dir, args.output_dir)
        print("Built offline workspace from saved inputs. No search authentication, crawl or publishing performed.")
        return
    inventory_path = args.output_dir / "content.json"
    inventory_data = json.loads(inventory_path.read_text()) if inventory_path.exists() else {"pages": [], "generated_at": None, "warnings": []}
    health_report = None
    if args.crawl_only:
        pages, warnings = crawl([urljoin(SITE, t["page"]) for t in editorial["topics"]], args.crawl_limit)
        _, health_report = record_crawl(pages, warnings, required_pages(editorial), args.output_dir)
        write_workspace(editorial, args.output_dir, args.output_dir, health_report)
        print(f"Crawl health: {health_report['status']}; {health_report['coverage']['html_ok']}/{len(pages)} HTML pages checked successfully. Search Console data left unchanged.")
        if args.fail_on_health and health_report["status"] == "failed":
            raise SystemExit(1)
        return
    end = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=3)
    datasets = {}
    try:
        service = google_service()
        for label, window in (("current", period(28, end)), ("previous", period(28, end - timedelta(days=28)))):
            datasets[label] = {"period": window}
            for key, dims in (("overall", []), ("daily", ["date"]), ("pages", ["page"]), ("queries", ["query"]), ("query_pages", ["query", "page"])):
                datasets[label][key] = fetch_rows(service, dims, window)
        followups = change_results(service, editorial.get("changes", []), end, args.followup_limit)
    except Exception as exc:
        fail_search_refresh(args.output_dir, exc)
    if args.crawl:
        urls = [r["keys"][0] for r in datasets["current"]["pages"]] + [urljoin(SITE, t["page"]) for t in editorial["topics"]]
        inventory, warnings = crawl(urls, args.crawl_limit)
        inventory_data, health_report = record_crawl(inventory, warnings, required_pages(editorial), args.output_dir)
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
    from update_data import ALL_KEYWORDS, HIGH_PRIORITY, TARGET_KEYWORDS, TARGET_REVIEWED_AT
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
              "url_collisions": url_collisions([p["url"] for p in pages]),
              "tracked_keywords": tracked, "target_categories": TARGET_KEYWORDS, "target_reviewed_at": TARGET_REVIEWED_AT,
              "queries": [{"query": k, **v, "branded": brand(k)} for k, v in grouped(datasets["current"]["queries"], 0).items()],
              "change_results": followups,
              "content_generated_at": inventory_data["generated_at"], "crawl_warnings": inventory_data.get("warnings", []),
              "measurement": {"leads": "Not connected", "note": "Connect aggregate organic enquiries and qualified leads; do not publish customer details in this public repository."},
              "data_notes": ["Finalized web-search data, dates in Pacific Time.", "Query rows omit anonymized searches and may be limited by Google; they need not sum to page or property totals.", "Average position is not a fixed country/device rank.", "Priority scores organize review work; they do not forecast traffic gains."],
              "overall_metrics": {"total_clicks": overall["clicks"], "total_impressions": overall["impressions"], "avg_ctr": overall["ctr"], "avg_position": overall["position"], "period_start": datasets["current"]["period"]["start"], "period_end": end.isoformat()},
              "top_pages": [{"page": p["path"], **p["current"]} for p in pages]}
    write_json(args.output_dir / "latest.json", result)
    write_json(args.output_dir / f"history_{datetime.now(timezone.utc).date()}.json", result)
    record_search_health(args.output_dir)
    write_workspace(editorial, args.output_dir, args.output_dir, health_report)
    print(f"Updated {len(pages)} pages and {len(result['queries'])} queries through {end}.")
    if args.fail_on_health and health_report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
