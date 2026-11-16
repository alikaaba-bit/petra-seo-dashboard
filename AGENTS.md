# Petra Content & Search

## Commands

- Python 3.11+: install `requirements.txt` in a local virtual environment.
- Tests: `.venv/bin/python -B -m unittest discover -s tests -v`.
- Dashboard checks: `node --check assets/dashboard.js` and `node --test tests/dashboard.test.cjs` (Node 22 in CI).
- Read-only website check: `.venv/bin/python -B scripts/seo_pipeline.py --crawl-only --fail-on-health --crawl-limit 20 --output-dir tmp/health-check`.
- Offline weekly packet: `.venv/bin/python scripts/seo_workspace.py --data-dir data --output-dir tmp/workspace`.
- Rendered smoke check: `.venv/bin/python scripts/browser_check.py --output-dir tmp/browser-check` (installed Chrome wrapper only).
- Local preview: `python3.11 -m http.server 8765 --bind 127.0.0.1 --directory tmp/preview`, after copying only public HTML/assets/data into that directory. No compilation step.

## Architecture and patterns

- `scripts/seo_pipeline.py` owns GSC collection, bounded crawling, briefs and 28/56-day measurements. `scripts/update_data.py` retains the target-term configuration and compatibility entry point.
- `data/latest.json` is the saved search snapshot; `content.json` is the last accepted inventory; `crawl-health.json` is the latest crawl attempt, including failures. Do not substitute crawl dates for search dates.
- `data/editorial.json` holds reviewed public topic assignments, facts and published changes. `scripts/import_workspace.py` dry-runs reviewed change/fact/intent/page records from browser exports; apply requires explicit public review. `seo_workspace.py` owns offline draft packets, drift and follow-up queues.
- `index.html` and `assets/dashboard.js` serve a static, browser-local workspace. Preserve full observed URL identity, including fragments. Follow existing rendering/escaping helpers.
- Tests follow `tests/test_pipeline.py`, `tests/test_health.py` and the dependency-free Node harness in `tests/dashboard.test.cjs`.
- Keep temporary reports and previews under ignored `tmp/`. Preserve existing worktrees and uncommitted user changes.

## Operating boundaries

- Measurement, drafts and review only. Human owners approve facts, routing and publication; the dashboard has no website publishing credentials.
- Keep `.env`, credential JSON, tokens and private browser backups out of Git and previews. Do not read or print credentials during audits; crawl-only needs none.
- Unknown operations facts stay null. Do not infer MOQ, timing, certifications, addresses, phone numbers or capabilities from unverified website copy.
- Query overlap and fragment collisions are review candidates. No automatic redirects, canonical changes, history merging, link buying or mass content creation.
- A small or missing sample is not proof of impact. Preserve the existing fewer-than-20-click and non-causality rules.
- Do not run `scripts/email_alerts.py` as a diagnostic. Prefer on-dashboard health and read-only Actions evidence. Email, paid APIs, schedule changes, push/merge/deploy and website edits require explicit authorization.
- GSC access recovery can resume the existing email workflow. The owner must approve isolating email before recovery. Code cannot fix account billing locks.
