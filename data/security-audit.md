# Dashboard defensive security review

**24 November 2026 · source baseline `2f0cc84` and local review changes.** Scope covered the static UI, Python collectors, Actions configuration, local backup handling, and the loopback preview. The production GitHub Pages overview and all eight local dashboard views rendered successfully.

| # | Protection | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Privileged routes require access checks | N/A | Public static workspace. Editorial actions write to browser-local storage or explicit offline files. |
| 2 | Object-level authorization | N/A | The app serves static public inputs and has no shared account records or object API. |
| 3 | Server-only confidential credentials | Pass | Google and Resend credential reads are in Python and Actions. The browser loads public files. |
| 4 | Server validation of prices | N/A | Editorial and search measurement only. |
| 5 | Server validation of quantities | N/A | No quantities are submitted to a server. Browser backup enquiry counts have local validation. |
| 6 | Provider-verified payment or order state | N/A | The workspace has no payment or order processing. |
| 7 | One-time, limited redemption | N/A | The workspace has no credits, coupons or redemption. |
| 8 | Server-controlled roles | N/A | The workspace has no signup or roles. |
| 9 | Login and code controls | N/A | The workspace has no login, OTP or magic links. |
| 10 | Untrusted text stays data | Pass | The collectors parse evidence deterministically. The wrappers keep crawled text, GSC, backups and AI responses in the evidence role. Manual AI observations accept whitelisted metadata. Reviewed export apply still requires public review. |
| 11 | Escaping and safe links | Fix implemented | The dashboard now restricts navigable page links to the factory origin. New panels escape text and validate proof links. Markdown downloads escape evidence. Local regressions cover text and rejected links. |
| 12 | Upload content controls | N/A | There is no server upload. The bounded browser-only backup import parses and validates JSON as data. |
| 13 | Secrets out of Git and previews | Fix implemented | Added ignore rules for credential variants, private key files and default workspace backups. A path-only working tree and history scan covered known credential formats. The preview was built from an explicit public file list. |
| 14 | Parameterized database queries | N/A | No application database. Search Console requests use structured API filter data. |

Verification used the repository's Python and Node 22 tests, a secret-pattern scan of tracked source and reachable text history, and a public-only preview on loopback. GitHub reported the existing weekly email workflow as disabled. [Repository](https://github.com/alikaaba-bit/petra-seo-dashboard) · [Weekly workflow](https://github.com/alikaaba-bit/petra-seo-dashboard/actions/workflows/weekly-report.yml).
