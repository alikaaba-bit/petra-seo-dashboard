# Human publication handoff

The dashboard prepares drafts and records live checks. Website publication is a human action.

## Verify the serving system first

On November 24, the bounded crawl checked 28 HTML URLs including the [supplier checklist](https://petrajewelryfactory.com/how-to-evaluate-jewelry-manufacturing-partners-a-quality-checklist/), which had returned 404 in the earlier snapshot. The current pages use clean routes and self-referencing canonicals. Live HTTP read-back showed static HTML with no WordPress or Yoast markers on the checked candidates. The November 18 release record identifies Hostinger's static serving files. Confirm the exact current source with the website owner before editing. For a WordPress-served route, prepare the page fields and Yoast preview. For a static route, pass those same fields to the source owner. [Current crawl](../data/crawl-health.json) · [Earlier crawl](https://github.com/alikaaba-bit/petra-seo-dashboard/blob/2f0cc84dedad2b84dc20d0d00403b7c97d5e5e1c/data/crawl-health.json).

## Current route decisions

- Keep the restored supplier checklist as the guide candidate while reviewing intent. If a new check shows it unavailable, approve restoring that URL or assigning the term to a verified guide before preparing edits.
- Review the process page first among the thin editorial candidates. Show a buyer's next decision, the inputs needed for a manufacturing brief, and where sample approval fits. Ask Operations to confirm any timing, process or quality detail before use. [Process page](https://petrajewelryfactory.com/how-it-works/) · [Roadmap](../data/roast-roadmap.md).
- Search Console access recovery belongs to the account owner. Use the read-only workflow evidence and confirm weekly email isolation first. [Latest failed collection](https://github.com/alikaaba-bit/petra-seo-dashboard/actions/runs/45261706353).

## Private label review

Use the [single-page packet](handoff-private-label.md) with the [30-day plan](../data/blitz-plan.md).

Historical drafts below require current factual and intent review. Use the dashboard Weekly review to collect sourced public fact confirmations, SERP evidence, buyer problem, first-hand proof and a measurement hypothesis. Leave all unknown operational details blank. Three planning packets cover the 50 tracked terms; they are not 50 publication requests.

Before publication, save the observed crawl baseline. After a human publishes, verify the exact real path, title, visible H1, canonical, indexability, schema and desktop/mobile behaviour; repeat raw and rendered demo checks. Log the actual publication date, public verification URL and verification date, export the browser workspace, dry-run the importer and rebuild from the reviewed local candidate. A work-status label is not publication evidence.

## Historical private-label draft

Only after the current destination and facts are approved, adapt `private-label-draft.html` for the approved `/private-label/` destination while preserving the current form, images, navigation and styling. Use a single page-level H1. Review the text against actual operations before publishing.

- Proposed SEO title: `Private Label Jewelry Manufacturing | Petra`
- Proposed meta description: `Plan a private label jewelry collection with Petra. Discuss designs, branding, packaging, samples and production requirements for your next collection.`
- Add original sample photography and documented quality checks when available.
- Confirm and add actual minimum quantities and lead times; the draft does not invent these.

## Shared quote template

The previous inspection found finance-template copy and demo contact information. Use the current crawl report to confirm affected URLs. Identify any currently affected shared template in the verified serving system and replace its heading/body with:

> Discuss your jewelry manufacturing project. Share your designs, preferred materials, quantities and delivery requirements so our team can review the next steps.

Replace finance-related bullets with: design requirements, material and finish preferences, estimated quantities, target delivery date. Remove dummy contact details; use the working contact form until verified sales details are supplied. Do not make up an address, certification, response-time promise or phone number.

Back up the affected page/template in its actual source system before applying edits. Verify desktop and mobile forms, then record the actual publication date in the dashboard. Re-crawl to confirm the leftovers are gone.
