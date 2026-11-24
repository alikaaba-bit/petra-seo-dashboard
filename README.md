# Petra · Content & Search

[Open dashboard](https://alikaaba-bit.github.io/petra-seo-dashboard/)

A static workspace for deciding which website pages to improve, preparing evidence-led briefs, and measuring published changes. It reads saved Google Search Console snapshots and a bounded crawl of petrajewelryfactory.com; check each source's dates before treating it as current.

## Views

- Overview: equal-period metrics, daily visibility, next actions and aggregate enquiries.
- This week: business relevance, search evidence, website findings and work status.
- Pages & briefs: actual query-to-page data, review-gated title/H1 drafts, buyer-question checklist, link suggestions, crawl findings and downloadable Markdown.
- Content map: preferred topic destinations, unassigned pages and query-overlap candidates.
- Changes & results: published change log, 28/56-day follow-up results, browser-local aggregate enquiry counts and JSON backups.
- Site health: crawl checks, index inspection and optional Lighthouse mobile lab results.
- Search queries: branded/non-branded discovery and exact-match target tracking.
- Weekly review: ordered roadmap, single-page sprint, confirmed facts and proof, contextual links, optional AI observations, grouped draft packets, drift and 28/56-day follow-ups.

## Run locally

Use Python 3.11 or newer. Credentials remain outside the repository.

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/credentials.json .venv/bin/python scripts/seo_pipeline.py --crawl --crawl-limit 100 --inspect-limit 10
python3.11 -m http.server 8765 --bind 127.0.0.1 --directory tmp/preview
```

First prepare a public-only preview as described below. Open `http://127.0.0.1:8765`. The service account needs read access to the configured Search Console property. `GSC_CREDENTIALS` may alternatively contain the service-account JSON in a CI secret. `scripts/update_data.py` remains a supported entry point.

`--crawl-only` checks the website without authenticating to Search Console or changing search timestamps. Crawling respects robots.txt, accepts only same-host HTTPS URLs, follows bounded redirects, limits response sizes and checks up to the configured page limit. Crawl failures are reported separately from indexing findings.

## Local health check

Run a bounded, read-only check into an ignored temporary directory:

```sh
.venv/bin/python -B scripts/seo_pipeline.py --crawl-only --fail-on-health --crawl-limit 20 --output-dir tmp/health-check
```

An exit code of 1 means the health gate found a blocker, not that it repaired the website. No credentials are needed. `--output-dir` changes where generated reports go; topic configuration still comes from `data/editorial.json`. Omit it only when you intend to update the repository's local data files.

- `crawl-health.json` records the latest attempt, coverage, blockers, discovery warnings and per-URL evidence. A request exceeding 4,000,000 bytes is explicitly unexamined; the crawler does not silently raise the limit or certify that body as free of placeholders.
- `content.json` is replaced only when the health result is `passed` or `warning`. A failed attempt preserves the previous inventory. In crawl-only mode, `latest.json` and search history are never written.
- Required URLs are the homepage and the commercial destinations in `data/editorial.json`. Missing, failed, redirected, robots-blocked, non-HTML or noindex required pages fail the gate. Known demo strings anywhere in a fetched HTML payload and request/parsing errors also fail. Historical, non-required 404s and discovery limits are warnings for review.
- The known demo list checks raw HTML, attributes, entities and hidden payloads as well as text. It is a bounded denylist, not a general factual validator. Check rendered views in a browser as well; scripts can load content the HTTP crawl cannot see.
- The dashboard overlays the latest crawl evidence without retimestamping Search Console. Failed or unchecked pages have their briefs held; failed pages are excluded as link sources. Hash routes retain separate metrics and workspace identities, but drafts remain on hold pending a route decision. No metrics, task records or pages are automatically merged.
- `passed` means these bounded critical checks passed. It does not certify content quality, indexing, factual accuracy or the absence of all SEO findings. Crawl, GSC and Lighthouse freshness remain separate.

The exit gate is opt-in. This increment does not add workflow triggers or change schedules. With a separately authorized full GSC refresh, `--crawl --fail-on-health` still saves successfully fetched search metrics and the failed crawl report before returning 1; it preserves the previous good inventory. Review workflow artifact/commit handling before enabling that exit gate in CI, because an unsuccessful step normally skips later commit steps.

To inspect a temporary report in the UI, serve a preview containing only `index.html`, `assets/` and copies of public `data/` files, with its `data/crawl-health.json` replaced by the temporary report. Keep that preview under `tmp/`; do not copy credentials or browser backups into it.

## Scheduled updates and publishing

GitHub Pages serves the root of `main`. The daily workflow refreshes GSC, crawls the site, inspects ten priority URLs and saves data after successful collection. The site-wide daily aggregate in `daily-search.json` and the page/query snapshot in `latest.json` have separate dates and sources. The Lighthouse workflow produces mobile lab reports for the homepage, private-label and contract manufacturing pages. GitHub reported the weekly email workflow as manually disabled on November 24. [Actions workflows](https://github.com/alikaaba-bit/petra-seo-dashboard/actions).

The November 24 recovery verified read access to the exact `https://petrajewelryfactory.com/` property and refreshed page/query data. Check dates in the latest successful snapshot before interpreting search results. Use the bounded crawl for current website evidence. [Successful collector run](https://github.com/alikaaba-bit/petra-seo-dashboard/actions/runs/45354874045) · [Search health](data/search-health.json).

Search collection writes `search-health.json` with the attempt time, sanitized error classification and the last successful search snapshot's dates. Authentication, query and follow-up collection failures still exit 1 and preserve `latest.json` and history. The daily workflow uploads this diagnostic even after failure; failed-run artifacts are not automatically published to the dashboard. No raw exception payload or credential value is included. This local diagnostic change does not repair remote permissions or run the collector.

Confirm the email workflow remains disabled and get owner approval for isolation before changing Search Console access. A fresh successful workflow collection is the acceptance check for page/query measurement.

## Editorial state and results

Change statuses, logged changes and enquiry counts save in the current browser. Export a workspace backup before clearing browser storage or moving devices. No customer names or contact details should be entered. The site is public and has no authenticated shared editing backend.

To enable automatic follow-up calculations for changes recorded in the browser:

```sh
.venv/bin/python scripts/import_workspace.py /absolute/path/to/petra-workspace.json
```

This command is now a **dry run**. Review the export for private material, then use `--include-reviews --apply --public-reviewed --output tmp/editorial-reviewed.json` to write a local candidate. It imports whitelisted public changes and explicitly selected fact/term/page reviews, excluding owner names, tasks and enquiry counts. Validate and rebuild against that candidate before any separately approved repository release. No commit or remote update is implied. Legacy `business_facts` values are not treated as confirmations. Unknown facts remain null.

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
- The November 17 target configuration has 14 active terms and six priorities, centered on stainless-steel manufacturing, private label, original-design development and buyer preparation; silver is secondary. UK spelling and steel OEM variants share a proposed destination. All 50 original target terms remain in `HISTORICAL_TARGET_KEYWORDS`; saved search/history files and retired editorial reviews are preserved. Retired terms can still appear in actual observed query rows. Claim-led and brand-navigation targets are not active acquisition priorities. Proposed paths and guide intent are pending review, not content or publication approval.

## Open-source integrations

[Trafilatura](https://github.com/adbar/trafilatura) extracts main content (Apache-2.0 for current versions). [Lighthouse CI](https://github.com/GoogleChrome/lighthouse-ci) supplies optional mobile lab checks (Apache-2.0). Dependency licenses remain applicable. Opportunity analysis is implemented here using transparent rules; no code was copied from GSC Opportunity Finder. SEOnaut and CrawlSEO were evaluated as alternatives but are not required or embedded.

## Website changes

Use the [serving-system checklist](website/PUBLISHING.md) and the [private-label review packet](website/handoff-private-label.md). Verify the current source for the exact route before a human edits it. Use Yoast only when WordPress serves that route. The included HTML remains a historical reference.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check assets/dashboard.js
node --test tests/dashboard.test.cjs
```

The tests cover date windows, weighting, query/page separation, pagination, propagated API errors, low samples, overlap review and before/after evaluation boundaries. Health regressions cover oversized responses, hidden demo strings, robots failures, cross-host redirects, required-page failures, retained inventory, search/crawl separation, fragment identity, held briefs, unknown metrics and escaped diagnostics. Browser checks and any future deployed release remain separate verification steps.

## Offline operating loop

### Run the weekly review

The [Weekly SEO Review workflow](https://github.com/alikaaba-bit/petra-seo-dashboard/actions/workflows/seo-weekly-review.yml) runs Mondays at 19:23 Asia/Shanghai (11:23 UTC). The run summary shows the first decision, source dates, sampled Google coverage and private-label proof status. The run artifact includes the detailed review, roadmap and page plan. It reads the saved evidence and latest collector status with read-only access. Confirm successes from existing inbound records, qualify buyer projects, and record approved aggregate counts in Changes & results.

Every weekly run first tests the measurement and decision rules. It checks the exact Search Console property, finalized dates and totals, and holds search decisions on inconsistent input. Temporary GitHub reads retry up to three attempts. A stale or failed crawl triggers one bounded, read-only crawl in the run’s temporary directory. The checkpoint records the recovery outcome.

The workflow carries its verified weekly state forward through its Actions artifact. It compares newly available 28- and 56-day results, keeps low samples inconclusive, and selects one corrective decision or provides the evidence needed for the next page test. Manual reruns within a week have a single review-week count. The job prepares a review for the site owner. Sales qualifications and approved aggregate outcomes supply the business measure.

1. Run the bounded crawl. Review Fatal items first, then Revenue, Compounding and Fluff. Confirm an affected URL before writing a handoff. Retain historical failed checks with their observation dates.
2. Review one destination and its actual buyer SERP. Record market, device, date and evidence URLs. Confirm the relevant facts, first-hand proof and measurement hypothesis in the [public editorial store](data/editorial.json).
3. Dry-run the reviewed import and rebuild. The [30-day plan](data/blitz-plan.md) tracks the single private-label candidate and its evidence gates.
4. Capture the observed crawl baseline. A human publishes through the verified serving system, then checks the URL on desktop and mobile and records the actual publication and verification dates.
5. Review finalized 28- and 56-day windows after the three-day lag. The collector defaults to 50 change records per run. Review deferred records before increasing `--followup-limit`. A window below 20 clicks remains inconclusive.

Build offline from saved public inputs (no authentication, site writes or sends):

```sh
.venv/bin/python scripts/seo_workspace.py --data-dir data --crawl-report tmp/health-check/crawl-health.json --output-dir tmp/workspace --save-baseline tmp/baselines/before-change.json
.venv/bin/python scripts/browser_check.py --url https://petrajewelryfactory.com/ --output-dir tmp/health-check
.venv/bin/python scripts/seo_workspace.py --data-dir data --crawl-report tmp/health-check/crawl-health.json --baseline-file tmp/baselines/before-change.json --output-dir tmp/workspace
```

Baseline creation refuses to overwrite an existing file. A broken baseline is labelled observed problems, never approved as known good. Drift compares titles, description, H1/headings, canonicals, redirects, robots and schema; missing coverage is unknown, not deletion. It never rolls back or changes the site. Use a newer post-change crawl for a meaningful comparison.

The browser checker uses the **already installed** `chrome-devtools-axi`, at most five same-site URLs, and read-only DOM inspection. If unavailable, use a manual browser check; the script installs nothing. A browser check complements the bounded HTTP crawl, does not override it, and cannot prove Google indexing. Output contains observed website copy, which is never imported as confirmed facts.

`workspace.json`, `draft-pack.json`, `weekly-review.md`, `roast-roadmap.md`, `blitz-plan.md`, `customer-journey.md` and `internal-links.json` rebuild from the saved inputs. For a current preview, stage a copy of public input files in a temporary data folder and overlay the newer accepted `content.json`, latest `crawl-health.json` and `browser-check.json`. Build against that folder and copy public reports alongside its inputs. Serve only the preview directory with the loopback command above. Provide `--editorial tmp/editorial-reviewed.json` to build from a reviewed candidate. `seo_pipeline.py --workspace-only` also rebuilds from its selected `--output-dir` without authentication.

### Record facts, proof and manual observations

Use Weekly review for fact, intent and page reviews. Use `proof_reviews` in the same reviewed editorial file for atomic receipts. Each record has a stable lowercase ID, `status`, `category`, `pages`, `evidence`, `source_url`, `reviewed_at`, `reviewer` and `public_safe`. Categories are `process_test`, `customer_outcome`, `original_media`, `aggregate_data` and `qc_edge_case`. A confirmed record needs an approved public source and its exact page scope. Use `status: unknown` to withdraw a receipt.

Proof can be submitted as a version 2 review export with records under `review.proof_reviews`. Run `scripts/import_workspace.py` with `--include-reviews` to dry-run, then use `--apply --public-reviewed --output tmp/editorial-reviewed.json` after owner review. The same confirmation requirement applies to fact updates. Review the final public text and validate the source before release.

The optional [manual AI file](data/ai-visibility.json) uses version 1 records with `provider` (ChatGPT, Perplexity or Google AI Overviews), `prompt_id`, two-letter `market`, ISO `checked_at` and `result` (`cited`, `mentioned` or `absent`). Use `cited_url` only for a public Petra citation. The prompts are `quality-problems`, `supplier-evaluation`, `manufacturing-models`, `private-label-shortlist` and `brief-ready`. Keep raw answers, private notes and account details out of the file. An empty file means there are no observations.

Local reviews do not change generated packets until exported, validated, imported and rebuilt. Pending local review edits hold packet/page-brief downloads. The importer requires explicit `--apply --public-reviewed` for local writes. Free text cannot be automatically proven public-safe: inspect it before importing, especially reviewer identities and evidence descriptions. Browser storage/export is private to that browser, not a shared editorial backend; export backups before moving devices.

## Failure reporting and tool ownership

- `seo_pipeline.py` owns GSC, bounded HTTP crawl, page/query mapping and result calculations. `seo_workspace.py` owns offline review dispositions, source-backed draft scaffolds, due dates, drift and on-dashboard alerts. Neither sends email nor publishes.
- `lighthouse_summary.py` writes `performance-health.json` on every attempted summary. Runtime errors, missing targets, redirects, null scores or failed collection preserve `performance.json`. CI uploads the attempt report even after collection failure; failed attempts remain in artifacts until deliberately copied to the dashboard. No fresh Lighthouse run was enabled by this local work. These are lab scores, not CrUX field data.
- Installed `~/.agents/skills/seo-flow/SKILL.md`, `seo-content-brief/SKILL.md` and `seo-drift/SKILL.md` guide the human review loop. Repo artifacts win over a duplicate skill database/crawler. Use `seo-google` for targeted read-only GSC/PageSpeed/CrUX/inspection gaps after access approval; technical/schema/sitemap skills are focused review aids, not autonomous publishing. Page/plan/site-architecture help choose destinations. Do not install a parallel calendar or orchestration stack.
- The [eight Petra wrappers](.agents/skills/) adapt Illyism's review method to the dashboard and the factory buyer journey. The existing crawler and workspace build supply their evidence and outputs. [Illyism method](https://il.ly/blog/seo-skills) · [Upstream skills](https://github.com/Illyism/seo-skills).
- Keep Lighthouse CI; Unlighthouse is unnecessary unless a specific uncaptured route needs manual diagnosis. Keep the related keyword-calendar repo as historical reference only. Keep WordPress/Yoast as a human publishing option only after confirming they actually serve the target route.
- Organization JSON-LD drafts use only explicitly confirmed public fields. Unknown address, phone, MOQ, timing and certifications are omitted. A separate human check must match markup to visible page content. `llms.txt` is an optional convenience draft, not a ranking requirement; [Google's AI features guidance](https://developers.google.com/search/docs/appearance/ai-features) still requires ordinary Search eligibility. No GEO-first content mill.
- Paid SERP/SEO APIs, IndexNow submission, automatic email, backlink campaigns, shared backend and enquiry analytics remain off/unconnected pending explicit approval. Prefer dashboard alerts, manual SERP evidence and existing GSC. No programmatic landing-page multiplication, directory submissions, link buying, automatic redirects/canonicals or mass articles.
