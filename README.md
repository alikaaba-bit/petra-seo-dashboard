# Petra · Content & Search

[Open dashboard](https://alikaaba-bit.github.io/petra-seo-dashboard/)

A static workspace for deciding which website pages to improve, preparing evidence-led briefs, and measuring published changes. It uses live Google Search Console data and a bounded crawl of petrajewelryfactory.com.

## Views

- Overview: equal-period metrics, daily visibility, next actions and aggregate enquiries.
- This week: business relevance, search evidence, website findings and work status.
- Pages & briefs: actual query-to-page data, title/H1 suggestions, buyer-question checklist, link suggestions, crawl findings and downloadable Markdown.
- Content map: preferred topic destinations, unassigned pages and query-overlap candidates.
- Changes & results: published change log, 28/56-day follow-up results, browser-local aggregate enquiry counts and JSON backups.
- Site health: crawl checks, index inspection and optional Lighthouse mobile lab results.
- Search queries: branded/non-branded discovery and exact-match target tracking.

## Run locally

Use Python 3.11 or newer. Credentials remain outside the repository.

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/credentials.json .venv/bin/python scripts/seo_pipeline.py --crawl --crawl-limit 100 --inspect-limit 10
python3.11 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765`. The service account needs read access to the configured Search Console property. `GSC_CREDENTIALS` may alternatively contain the service-account JSON in a CI secret. `scripts/update_data.py` remains a supported entry point.

`--crawl-only` refreshes `data/content.json` without claiming that Search Console has refreshed. Crawling respects robots.txt, accepts only same-host HTTPS URLs, follows bounded redirects, limits response sizes and checks up to the configured page limit. Crawl failures are reported separately from indexing findings.

## Scheduled updates and publishing

GitHub Pages serves the root of `main`. The daily workflow refreshes GSC, crawls the site, inspects ten priority URLs and commits data only after collection succeeds. A weekly Lighthouse workflow produces mobile lab reports for the homepage, private-label and contract-manufacturing pages. This is lab data, not field Core Web Vitals. Existing weekly email scheduling is retained; this upgrade does not send a test email.

The account reported a billing lock on September 7, 2026. Code cannot resolve an account billing lock. A local refresh works independently; scheduled Actions and Pages builds may stay blocked until account access is restored. Check workflow runs and the live site before assuming a pushed commit is deployed.

## Editorial state and results

Change statuses, logged changes and enquiry counts save in the current browser. Export a workspace backup before clearing browser storage or moving devices. No customer names or contact details should be entered. The site is public and has no authenticated shared editing backend.

To enable automatic follow-up calculations for changes recorded in the browser:

```sh
.venv/bin/python scripts/import_workspace.py /absolute/path/to/petra-workspace.json
```

Review `data/editorial.json`, commit it, and rerun the pipeline. The importer copies only change records; it deliberately excludes owner names and enquiry counts from public GitHub data. Topic ownership and confirmed business facts live in the same file. Unknown business facts are null, not invented.

The interface can import a previous browser backup. Records merge by ID. Aggregate enquiry records use a date-range/page key. Do not combine site-wide counts with page counts for overlapping dates. Enquiries are manual until an analytics integration is connected; missing data is never shown as zero conversions.

## Measurement rules

- Current and prior periods each contain exactly 28 dates, using finalized web-search data and Pacific Time date boundaries.
- Property totals, page totals and query rows are fetched separately. Privacy filtering and Google's internal limits mean query sums need not equal property/page totals.
- API pagination retrieves the rows Google makes available; it does not promise all searches.
- Missing query data is not proof that a page never ranks. Average position is not a fixed country/device ranking.
- Priority scores organize review work. They are not traffic forecasts, ranking guarantees or content-quality scores.
- Brand queries containing Petra are separated for review, not assumed to belong to a different company.
- Overlap is a review candidate, not proof of harmful cannibalization. No automatic redirects, canonical changes or merges occur.
- Briefs and link suggestions are deterministic editorial drafts. Validate buyer intent, actual body content, factual claims and natural link placement.
- Before/after windows are 28 and 56 days on either side of publication. Fewer than 20 clicks in either window is inconclusive. Observed differences do not establish causation.
- The previous eight-week plan remains a historical document, not a forecast or active promise.

## Open-source integrations

[Trafilatura](https://github.com/adbar/trafilatura) extracts main content (Apache-2.0 for current versions). [Lighthouse CI](https://github.com/GoogleChrome/lighthouse-ci) supplies optional mobile lab checks (Apache-2.0). Dependency licenses remain applicable. Opportunity analysis is implemented here using transparent rules; no code was copied from GSC Opportunity Finder. SEOnaut and CrawlSEO were evaluated as alternatives but are not required or embedded.

## Website changes

See `website/PUBLISHING.md` and `website/private-label-draft.html`. These are prepared WordPress edits; the dashboard does not publish them. Real MOQ, lead times, contact details and WordPress access are needed to complete those updates.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check assets/dashboard.js
```

The tests cover date windows, weighting, query/page separation, pagination, propagated API errors, low samples, overlap review, crawl host restrictions and before/after evaluation boundaries. Verify the actual browser routes, forms, export/import, mobile layout and live deployment as well.
