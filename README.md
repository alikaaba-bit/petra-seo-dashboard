# Petra · Content & Search

[Open dashboard](https://alikaaba-bit.github.io/petra-seo-dashboard/)

A static workspace for deciding which website pages to improve, preparing evidence-led briefs, and measuring published changes. It uses live Google Search Console data and a bounded crawl of petrajewelryfactory.com.

## Views

- Overview: equal-period metrics, daily visibility, next actions and aggregate enquiries.
- This week: business relevance, search evidence, website findings and work status.
- Pages & briefs: actual query-to-page data, review-gated title/H1 drafts, buyer-question checklist, link suggestions, crawl findings and downloadable Markdown.
- Content map: preferred topic destinations, unassigned pages and query-overlap candidates.
- Changes & results: published change log, 28/56-day follow-up results, browser-local aggregate enquiry counts and JSON backups.
- Site health: crawl checks, index inspection and optional Lighthouse mobile lab results.
- Search queries: branded/non-branded discovery and exact-match target tracking.
- Weekly review: all 50 term dispositions, confirmed facts, first-hand page evidence, grouped draft packets, alerts, drift and 28/56-day follow-ups.

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

GitHub Pages serves the root of `main`. The daily workflow refreshes GSC, crawls the site, inspects ten priority URLs and commits data only after collection succeeds. A weekly Lighthouse workflow produces mobile lab reports for the homepage, private-label and contract-manufacturing pages. This is lab data, not field Core Web Vitals. Existing weekly email scheduling is retained; this upgrade does not send a test email.

The September upgrade is already present on remote main and the November 5 Pages deployment. On November 16, the latest inspected [GSC refresh failure](https://github.com/alikaaba-bit/petra-seo-dashboard/actions/runs/43732656701) reported HTTP 403 for the configured URL-prefix property. That is the demonstrated collection blocker; the September billing-lock note is historical. Account billing settings were not inspected. A billing lock, if reported again, requires the account owner. A local crawl works independently of GSC access.

The existing email workflow can send after GSC access is restored. Recovering measurement must not implicitly authorize outbound email: the owner must separately approve isolating that workflow before access recovery. This local increment neither runs nor changes it. No new schedules, paid APIs or publishing integrations are introduced.

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

## Open-source integrations

[Trafilatura](https://github.com/adbar/trafilatura) extracts main content (Apache-2.0 for current versions). [Lighthouse CI](https://github.com/GoogleChrome/lighthouse-ci) supplies optional mobile lab checks (Apache-2.0). Dependency licenses remain applicable. Opportunity analysis is implemented here using transparent rules; no code was copied from GSC Opportunity Finder. SEOnaut and CrawlSEO were evaluated as alternatives but are not required or embedded.

## Website changes

See `website/PUBLISHING.md` and `website/private-label-draft.html`. These are historical drafts, not approved current copy. Identify the system actually serving the live site before changing it; the current hash routes do not establish WordPress authorship. The dashboard never publishes. See the local operating loop below.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check assets/dashboard.js
node --test tests/dashboard.test.cjs
```

The tests cover date windows, weighting, query/page separation, pagination, propagated API errors, low samples, overlap review and before/after evaluation boundaries. Health regressions cover oversized responses, hidden demo strings, robots failures, cross-host redirects, required-page failures, retained inventory, search/crawl separation, fragment identity, held briefs, unknown metrics and escaped diagnostics. Browser checks and any future deployed release remain separate verification steps.

## Offline operating loop

Use the existing Python environment and static dashboard. No added service, paid API, queue, database or schedule is required. The local build is complete; external access repair and website work are still owner actions.

1. **Unblock evidence and the live site.** Owner reviews the exact GSC property permission and billing if a current error names it. Approve isolating the existing email workflow before restoring access, since recovery can enable its scheduled sends. Website owner identifies the serving CMS/repo, removes raw/hidden demo leftovers, restores real commercial destinations and discovery endpoints, and verifies titles, H1s, canonicals and schema. Done: current authenticated measurement and verified routes, separately evidenced. This build does not perform those actions.
2. **Review this local branch.** The September workspace already reached main; do not merge the old branch blindly. Review `fix/seo-health-evidence-20261116` against current main, run the tests, inspect workflow diffs and preserve user edits in older checkouts. Release/push/merge/Pages deployment require separate authorization. Done locally: all checks pass and the public-only preview works. Done remotely only after an authorized deployment is read back.
3. **Prepare one focused page.** Weekly, use the 50-term table as dispositions, not 50 article requests. Review a small related group using actual supplier-versus-guide SERPs. Record market, device, date and result URLs; choose a real destination. Operations owner confirms public facts and limits; SEO lead records buyer problem, first-hand evidence, title and hypothesis. Missing facts remain unknown; unsupported capability records keep claim terms on hold. Done: an evidence-backed page packet that a person has reviewed.
4. **Publish and verify manually.** Export the browser workspace, dry-run the importer, apply only approved public fields to a local candidate, then rebuild. Capture an observed baseline before the website change. A person publishes through the verified serving system, checks desktop/mobile and the actual URL, then logs the real publication/verification dates. Re-crawl and compare with the baseline. Done: verified published page and imported publication record; task status alone does not count.
5. **Learn each week.** Run the existing GSC pipeline only after owner access recovery; review fresh non-brand opportunities alongside crawl/lab/browser evidence. Follow-up queue shows all publications at 28 and 56 days, allowing the existing three-day finalized-data lag. Collection defaults to 50 change records; later records explicitly show deferred status. Increase `--followup-limit` deliberately when needed, or review/archive old completed records. Keep the under-20-click and non-causal rules. Done: one documented next decision, not a content quota.

Build offline from saved public inputs (no authentication, site writes or sends):

```sh
.venv/bin/python scripts/seo_workspace.py --data-dir data --crawl-report tmp/health-check/crawl-health.json --output-dir tmp/workspace --save-baseline tmp/baselines/before-change.json
.venv/bin/python scripts/browser_check.py --url https://petrajewelryfactory.com/ --output-dir tmp/health-check
# Copy browser-check.json into the chosen data-dir, then rebuild to include it.
.venv/bin/python scripts/seo_workspace.py --data-dir data --crawl-report tmp/health-check/crawl-health.json --baseline-file tmp/baselines/before-change.json --output-dir tmp/workspace
```

Baseline creation refuses to overwrite an existing file. A broken baseline is labelled observed problems, never approved as known good. Drift compares titles, description, H1/headings, canonicals, redirects, robots and schema; missing coverage is unknown, not deletion. It never rolls back or changes the site. Use a newer post-change crawl for a meaningful comparison.

The browser checker uses the **already installed** `chrome-devtools-axi`, at most five same-site URLs, and read-only DOM inspection. If unavailable, use a manual browser check; the script installs nothing. A browser check complements the bounded HTTP crawl, does not override it, and cannot prove Google indexing. Output contains observed website copy, which is never imported as confirmed facts.

`workspace.json`, `draft-pack.json` and `weekly-review.md` are derived outputs. Copy public report files into the preview's `data/` alongside existing public inputs. Do not serve the repository root or private exports. `--editorial tmp/editorial-reviewed.json` lets the builder use a reviewed candidate without altering repository data. The pipeline also builds workspace outputs during crawl/full runs; `seo_pipeline.py --workspace-only` rebuilds from its selected `--output-dir` without authentication.

Local reviews do not change generated packets until exported, validated, imported and rebuilt. Pending local review edits hold packet/page-brief downloads. The importer requires explicit `--apply --public-reviewed` for local writes. Free text cannot be automatically proven public-safe: inspect it before importing, especially reviewer identities and evidence descriptions. Browser storage/export is private to that browser, not a shared editorial backend; export backups before moving devices.

## Failure reporting and tool ownership

- `seo_pipeline.py` owns GSC, bounded HTTP crawl, page/query mapping and result calculations. `seo_workspace.py` owns offline review dispositions, source-backed draft scaffolds, due dates, drift and on-dashboard alerts. Neither sends email nor publishes.
- `lighthouse_summary.py` writes `performance-health.json` on every attempted summary. Runtime errors, missing targets, redirects, null scores or failed collection preserve `performance.json`. CI uploads the attempt report even after collection failure; failed attempts remain in artifacts until deliberately copied to the dashboard. No fresh Lighthouse run was enabled by this local work. These are lab scores, not CrUX field data.
- Installed `~/.agents/skills/seo-flow/SKILL.md`, `seo-content-brief/SKILL.md` and `seo-drift/SKILL.md` guide the human review loop. Repo artifacts win over a duplicate skill database/crawler. Use `seo-google` for targeted read-only GSC/PageSpeed/CrUX/inspection gaps after access approval; technical/schema/sitemap skills are focused review aids, not autonomous publishing. Page/plan/site-architecture help choose destinations. Do not install a parallel calendar or orchestration stack.
- Keep Lighthouse CI; Unlighthouse is unnecessary unless a specific uncaptured route needs manual diagnosis. Keep the related keyword-calendar repo as historical reference only. Keep WordPress/Yoast as a human publishing option only after confirming they actually serve the target route.
- Organization JSON-LD drafts use only explicitly confirmed public fields. Unknown address, phone, MOQ, timing and certifications are omitted. A separate human check must match markup to visible page content. `llms.txt` is an optional convenience draft, not a ranking requirement; [Google's AI features guidance](https://developers.google.com/search/docs/appearance/ai-features) still requires ordinary Search eligibility. No GEO-first content mill.
- Paid SERP/SEO APIs, IndexNow submission, automatic email, backlink campaigns, shared backend and enquiry analytics remain off/unconnected pending explicit approval. Prefer dashboard alerts, manual SERP evidence and existing GSC. No programmatic landing-page multiplication, directory submissions, link buying, automatic redirects/canonicals or mass articles.
