"use strict";
const SITE = "https://petrajewelryfactory.com";
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (v) =>
  v == null
    ? "—"
    : Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
const pct = (v) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);
const label = (path) =>
  path === "/" ? "Homepage" : path.replace(/^\/+|\/+$/g, "").replace(/-/g, " ");
const badge = (text, color = "") =>
  `<span class="badge ${color}">${esc(text)}</span>`;
const empty = (text) => `<div class="empty">${esc(text)}</div>`;
const safePath = (path) =>
  typeof path === "string" &&
  path.startsWith("/") &&
  !path.startsWith("//") &&
  !/[\\\s]/.test(path);
let data, editorial, inventory, activePage;
let performanceData = { reports: [] };
let local = { changes: [], tasks: {}, leads: [] };
try {
  local = {
    ...local,
    ...JSON.parse(localStorage.getItem("petra-workspace-v2") || "{}"),
  };
} catch {
  /* storage may be unavailable */
}
if (!Array.isArray(local.changes)) local.changes = [];
if (!Array.isArray(local.leads)) local.leads = [];
if (!local.tasks || typeof local.tasks !== "object") local.tasks = {};
const views = {
  overview: [
    "A clearer path to growth.",
    "Search performance, useful next steps, and the evidence behind them.",
  ],
  priorities: [
    "Make this week count.",
    "Prioritized page improvements. Review the evidence, then make a focused change.",
  ],
  pages: [
    "Every page has a purpose.",
    "Connect search queries with content, buyer questions, and internal links.",
  ],
  topics: [
    "Give every topic a home.",
    "Assign search intent to an existing page before creating another one.",
  ],
  results: [
    "Know what changed. Learn what worked.",
    "Track published edits and organic enquiries, with clear limits on attribution.",
  ],
  health: [
    "A stronger foundation.",
    "Crawl findings that affect accessibility, clarity, and the buyer experience.",
  ],
  keywords: [
    "Listen to real searches.",
    "Separate target terms from observed demand and review brand queries on their own.",
  ],
};
function save() {
  try {
    localStorage.setItem("petra-workspace-v2", JSON.stringify(local));
  } catch {
    toast("Storage unavailable. Export your work before closing.");
  }
}
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  setTimeout(() => {
    $("#toast").hidden = true;
  }, 4200);
}
function download(name, text, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function panel(title, body, subtitle = "", link = "") {
  return `<section class="panel"><div class="panel-header"><div><h2>${esc(title)}</h2>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div>${link}</div>${body}</section>`;
}
function delta(now, before) {
  if (before == null) return "Comparison unavailable";
  const d = now - before;
  return `<span class="${d >= 0 ? "positive" : "negative"}">${d > 0 ? "+" : ""}${num(d)}</span> vs previous period`;
}
function metric(name, value, note = "") {
  return `<div class="metric"><div class="metric-label">${esc(name)}</div><div class="metric-value">${value}</div><div class="metric-note">${note}</div></div>`;
}
function pageButton(p) {
  return `<button class="text-button" data-page="${esc(p.path)}">${esc(label(p.path))}</button>`;
}
function table(headers, rows) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function normalize(raw) {
  if (raw.schema_version === 2) return raw;
  const m = raw.overall_metrics || {},
    oldPages = raw.top_pages || [];
  const paths = [
    ...new Set([
      ...oldPages.map((p) => p.page),
      ...(inventory.pages || []).map((p) => p.path),
      ...editorial.topics.map((t) => t.page),
    ]),
  ];
  return {
    ...raw,
    legacy: true,
    period: { start: m.period_start, end: m.period_end, days: 8 },
    overall: {
      clicks: m.total_clicks,
      impressions: m.total_impressions,
      ctr: m.avg_ctr,
      position: m.avg_position,
    },
    pages: paths
      .map((path) => {
        const current = oldPages.find((p) => p.page === path),
          topic = editorial.topics.find((t) => t.page === path),
          audit = (inventory.pages || []).find((p) => p.path === path) || {};
        return {
          path,
          url: SITE + path,
          current: current || {
            clicks: null,
            impressions: null,
            position: null,
            ctr: null,
          },
          previous: {},
          queries: [],
          audit,
          topic: topic?.topic || "Unassigned",
          intent: topic?.intent || "Needs review",
          business_value: topic?.business_value || 1,
          priority_score:
            (topic?.business_value || 1) * 10 +
            (audit.issues?.some((i) => i.includes("Template placeholder"))
              ? 35
              : 0),
          confidence: "Historical snapshot",
          evidence: [
            "Query-to-page data unavailable until the next successful refresh.",
          ],
          actions: [
            "Review current content and resolve the listed website findings.",
          ],
          index_status: "Not inspected",
          brief: {
            suggested_title: topic ? `${topic.topic} | Petra` : null,
            suggested_h1: topic?.topic,
            query_review: [],
            internal_links: [],
            buyer_questions: [
              "Confirm minimum order by design/material",
              "Explain sample and production timing",
              "Add verified quality-control evidence",
              "Make quote requirements clear",
            ],
            note: "Editorial draft. Search evidence is not yet connected.",
          },
        };
      })
      .sort((a, b) => b.priority_score - a.priority_score),
    queries: (raw.discovered_keywords || []).map((q) => ({
      ...q,
      query: q.keyword,
      branded: /\bpetra\b/i.test(q.keyword),
    })),
    daily: [],
    overlap_candidates: [],
    change_results: [],
  };
}
function freshness() {
  const age = Math.floor(
      (Date.now() - new Date(data.generated_at).getTime()) / 86400000,
    ),
    stale = !Number.isFinite(age) || age > 3;
  $("#status").className = `banner ${stale ? "warning" : ""}`;
  $("#status").textContent = stale
    ? `Search data is stale · Last successful refresh: ${data.generated_at?.slice(0, 10) || "unknown"}. Recommendations use this saved snapshot. Check Update status for the current failure.`
    : `Search data refreshed ${data.generated_at.slice(0, 10)} · Finalized results through ${data.period.end}.`;
  if (data.legacy)
    $("#status").textContent +=
      " Legacy snapshot: summary and page metrics cover different periods; query-to-page analysis is unavailable.";
  $("#period").textContent =
    `${data.period.start || "Unknown"} → ${data.period.end || "Unknown"}`;
  $("#footer-date").textContent =
    `Search snapshot: ${data.generated_at?.slice(0, 10) || "unavailable"}`;
}
function priorityList(pages) {
  return (
    pages
      .map(
        (p, i) =>
          `<article class="priority-item"><span class="rank">${String(i + 1).padStart(2, "0")}</span><div>${pageButton(p)}<p>${esc(p.actions[0])}</p><div class="row-meta">${badge(p.confidence, "amber")}${badge(p.business_value >= 3 ? "Buyer page" : "Supporting content", "gray")}${badge(local.tasks[p.path] || "To review", "gray")}</div></div>${badge(`${num(p.current.impressions)} impressions`, "gray")}</article>`,
      )
      .join("") || empty("No pages available yet.")
  );
}
function chart() {
  if (!data.daily.length)
    return empty("Daily trends will appear after a successful refresh.");
  const rows = [...data.daily].sort((a, b) => a.date.localeCompare(b.date)),
    max = Math.max(1, ...rows.map((r) => r.impressions));
  const points = rows
    .map(
      (r, i) =>
        `${20 + (i * 650) / Math.max(1, rows.length - 1)},${170 - (r.impressions / max) * 140}`,
    )
    .join(" ");
  return `<svg class="chart" viewBox="0 0 690 190" role="img" aria-label="Daily search impressions, maximum ${num(max)}"><path d="M20 30H670M20 100H670M20 170H670" stroke="#e4e8e0" fill="none" stroke-dasharray="4 4"/><polygon points="20,170 ${points} 670,170" fill="#e9f2ea"/><polyline points="${points}" stroke="#1d5548" stroke-width="2.5" fill="none" stroke-linejoin="round"/></svg><div class="chart-labels"><span>${rows[0].date}</span><span>${rows.at(-1).date}</span></div><details><summary>View daily data</summary>${table(
    ["Date", "Impressions", "Clicks"],
    rows.map((r) => [esc(r.date), num(r.impressions), num(r.clicks)]),
  )}</details>`;
}
function overview() {
  const m = data.overall,
    prev = data.previous_overall,
    leads = local.leads.filter(
      (r) => r.start === data.period.start && r.end === data.period.end,
    ),
    count = leads.length ? leads.reduce((s, r) => s + r.enquiries, 0) : null,
    issues = data.pages.reduce((n, p) => n + (p.audit.issues?.length || 0), 0);
  return `<div class="metrics">${metric("Organic clicks", num(m.clicks), delta(m.clicks, prev?.clicks))}${metric("Search impressions", num(m.impressions), delta(m.impressions, prev?.impressions))}${metric("Click-through rate", pct(m.ctr), "Clicks ÷ impressions")}${metric("Organic enquiries", num(count), count == null ? "Not connected · Add counts in Results" : "Manually recorded · matching date range")}</div><div class="layout"><div>${panel("Search visibility", chart(), "Daily impressions · current period", badge(`${data.period.days} days`, "gray"))}${panel("Where to focus next", priorityList(data.pages.slice(0, 4)), "Review these pages before expanding the content calendar.", '<a href="#priorities">All priorities ↗</a>')}</div><div>${panel("From search to enquiry", '<div class="flow"><span>Discover</span>→<span>Improve</span>→<span>Publish</span>→<span>Measure</span></div><div class="insight"><h3>One page. One useful change.</h3><p>Open a page brief, review buyer questions, and log the date when the change goes live.</p></div><p class="chart-caption">Before/after changes are observations. Demand, seasonality and other changes can affect results.</p><a href="#results" class="secondary">Track a change</a>')}${panel("Website checks", `<div class="big-number">${issues}</div><p class="chart-caption">Findings across ${inventory.pages?.length || 0} crawled pages. Findings need review; this is not a Google ranking score.</p><a href="#health" class="text-button">Review site health ↗</a>`)}${panel("Data you can trust", '<div class="issue">Exact query matching for tracked terms after refresh.</div><div class="issue">No query data does not mean a page never ranks.</div><div class="issue">Low sample sizes stay visible in recommendations.</div>')}</div></div>`;
}
function priorities() {
  return panel(
    "Your next improvements",
    `<div class="callout">Priority combines business relevance, observed search demand and website findings. Scores organize work; they do not predict extra clicks. ${data.legacy ? "Search evidence is historical until the pipeline refreshes." : ""}</div>${priorityList(data.pages.slice(0, 30))}`,
  );
}
function pagesTable(pages) {
  return pages.length
    ? table(
        [
          "Page / topic",
          "Impressions",
          "Clicks",
          "Avg. position",
          "Change",
          "Evidence",
        ],
        pages.map((p) => [
          pageButton(p) + `<small>${esc(p.path)} · ${esc(p.topic)}</small>`,
          num(p.current.impressions),
          num(p.current.clicks),
          num(p.current.position),
          p.click_change == null ? "—" : num(p.click_change),
          badge(p.confidence, "amber"),
        ]),
      )
    : empty("No pages match these filters.");
}
function pagesView() {
  return panel(
    "Page inventory",
    `<div class="toolbar"><label for="page-search" class="sr-only">Search pages</label><input id="page-search" type="search" placeholder="Find a page, topic, or query…"><label for="page-filter" class="sr-only">Filter pages</label><select id="page-filter"><option value="all">All pages</option><option value="commercial">Buyer pages</option><option value="issues">With findings</option><option value="unassigned">Unassigned topics</option></select></div><div id="page-table">${pagesTable(data.pages)}</div>`,
    "Open a page for its queries, brief, technical findings, and link suggestions.",
  );
}
function topics() {
  return `<div class="layout"><div>${panel("Topic ownership", editorial.topics.map((t) => `<div class="topic-card"><h3>${esc(t.topic)}</h3>${badge(t.intent, "gray")}<p><button class="text-button" data-page="${esc(t.page)}">${esc(t.page)}</button></p><p class="muted">Preferred destination · related articles should support this page when their intent matches.</p></div>`).join(""), "Starting assignments are editable in data/editorial.json.")}${panel(
    "Unassigned pages",
    data.pages
      .filter((p) => p.topic === "Unassigned")
      .map((p) => `<div class="issue">${pageButton(p)}</div>`)
      .join("") || empty("All pages have an assigned topic."),
  )}</div><div>${panel("Possible query overlap", data.overlap_candidates.length ? data.overlap_candidates.map((o) => `<div class="topic-card"><h3>${esc(o.query)}</h3>${o.pages.map((p) => `<p>${esc(new URL(p.url).pathname)} · ${num(p.impressions)} impressions</p>`).join("")}<p class="muted">${esc(o.verdict)}</p></div>`).join("") : empty(data.legacy ? "Needs query + page data from a successful refresh." : "No candidates met the review threshold in this period."))}${panel("Before creating a page", '<ol class="number-list"><li>Check the actual query and buyer intent.</li><li>Review whether an existing page already answers it.</li><li>Improve that page or give the new one a distinct purpose.</li><li>Use original company evidence and verified facts.</li></ol>')}</div></div>`;
}
function allChanges() {
  return [
    ...new Map(
      [...(editorial.changes || []), ...local.changes].map((c) => [
        c.id || `${c.page}:${c.published_at}:${c.summary}`,
        c,
      ]),
    ).values(),
  ];
}
function pageOptions() {
  return data.pages
    .map((p) => `<option value="${esc(p.path)}">${esc(p.path)}</option>`)
    .join("");
}
function results() {
  const changes = allChanges();
  return `<div class="layout"><div>${panel("Log a published change", `<form id="change-form" class="form-grid"><label>Page<select name="page" required>${pageOptions()}</select></label><label>Published date<input name="published_at" type="date" max="${new Date().toISOString().slice(0, 10)}" required></label><label class="full">What changed?<textarea name="summary" maxlength="1200" placeholder="Example: clarified sampling steps and added quality-control photos." required></textarea></label><label>Change type<select name="type"><option>Content update</option><option>Title / description</option><option>Internal links</option><option>Technical fix</option></select></label><label>Owner<input name="owner" maxlength="100" placeholder="Optional"></label><div class="full"><button class="primary">Save change</button></div></form><p class="content-status">Saved in this browser. Export a backup to keep your work. Automatic follow-ups require syncing exported changes to data/editorial.json and refreshing the pipeline.</p>`)}${panel(
    "Published changes",
    changes.length
      ? changes
          .map((c) => {
            const r = data.change_results.find((r) => r.change.id === c.id);
            return `<article class="topic-card"><h3>${esc(c.summary)}</h3><p>${esc(c.page)} · ${esc(c.published_at)}</p>${r?.windows ? r.windows.map((w) => `<div class="issue">${w.days} days: ${esc(w.status)}${w.before ? `<br>Clicks ${num(w.before.clicks)} → ${num(w.after.clicks)} · impressions ${num(w.before.impressions)} → ${num(w.after.impressions)}` : ` · through ${esc(w.ready_on)}`}</div>`).join("") : badge("Export + sync to calculate follow-ups", "amber")}</article>`;
          })
          .join("")
      : empty(
          "No published changes logged yet. Draft briefs are not counted as published work.",
        ),
  )}</div><div>${panel(
    "Organic enquiries",
    `<p class="chart-caption">Record aggregate enquiries attributed to organic search. Use consistent dates and landing pages. Leave customer names and contact details out.</p><form id="lead-form" class="form-grid"><label>Period start<input name="start" type="date" required value="${esc(data.period.start)}"></label><label>Period end<input name="end" type="date" required value="${esc(data.period.end)}"></label><label class="full">Landing page<select name="page"><option value="*">Whole website</option>${pageOptions()}</select></label><label>Enquiries<input name="enquiries" type="number" min="0" step="1" required></label><label>Qualified enquiries<input name="qualified" type="number" min="0" step="1" required></label><div class="full"><button class="secondary">Save counts</button></div></form>${
      local.leads.length
        ? table(
            ["Period / page", "Enquiries", "Qualified"],
            local.leads.map((r) => [
              `${esc(r.start)} → ${esc(r.end)}<small>${esc(r.page)}</small>`,
              num(r.enquiries),
              num(r.qualified),
            ]),
          )
        : '<p class="content-status">Not connected to analytics. No enquiries are assumed.</p>'
    }`,
  )}${panel("Keep your work", '<div class="toolbar"><button class="secondary" id="export-work">Export workspace</button><label class="secondary">Import backup<input id="import-work" type="file" accept="application/json" hidden></label></div><p class="chart-caption">Backups include changes, task statuses and aggregate enquiries. Matching record IDs are updated on import.</p>')}${panel("How results are measured", '<div class="issue">28- and 56-day windows compare equal periods before and after publication.</div><div class="issue">Fewer than 20 clicks in either window is marked inconclusive.</div><div class="issue">No causal lift or revenue claim is made from a before/after comparison.</div>')}</div></div>`;
}
function health() {
  const pages = data.pages.filter((p) => p.audit.issues?.length);
  return panel(
    "Website findings",
    `<p class="content-status">Content crawl: ${esc(inventory.generated_at?.slice(0, 10) || "not run")}. Index inspection is separate from crawlability.</p>${(inventory.warnings || []).map((w) => `<div class="callout">${esc(w)}</div>`).join("")}${
      pages.length
        ? table(
            ["Page", "Findings", "Index status"],
            pages.map((p) => [
              pageButton(p),
              p.audit.issues
                .map((i) => `<div class="issue">${esc(i)}</div>`)
                .join(""),
              esc(p.index_status),
            ]),
          )
        : empty(
            "No findings available. Check crawl status before interpreting this as a clean site.",
          )
    }<details><summary>What this checks</summary><p>HTTP status, same-site redirects, metadata, headings, canonicals, noindex, known template leftovers, duplicate metadata, and broken links to crawled pages. It does not replace a full security, accessibility, backlink, or Core Web Vitals audit.</p></details>`,
  );
}
function queryTable(rows) {
  return rows.length
    ? table(
        ["Query", "Impressions", "Clicks", "CTR", "Avg. position"],
        [...rows]
          .sort((a, b) => b.impressions - a.impressions)
          .map((q) => [
            esc(q.query),
            num(q.impressions),
            num(q.clicks),
            pct(q.ctr),
            num(q.position),
          ]),
      )
    : empty("No matching query data in this period.");
}
function keywords() {
  return (
    panel(
      "Observed queries",
      `<div class="toolbar"><label class="sr-only" for="query-search">Search queries</label><input id="query-search" type="search" placeholder="Search actual queries…"><label class="sr-only" for="brand-filter">Brand filter</label><select id="brand-filter"><option value="nonbrand">Non-brand</option><option value="all">All queries</option><option value="brand">Contains Petra</option></select></div><div id="query-table">${queryTable(data.queries.filter((q) => !q.branded))}</div>`,
      "Brand mentions are separated for review, not automatically classified as another company.",
    ) +
    panel(
      "Tracked target terms",
      table(
        ["Keyword", "Impressions", "Clicks", "Avg. position", "Status"],
        Object.entries(data.tracked_keywords || {}).map(([q, m]) => [
          esc(q),
          num(m.impressions),
          num(m.clicks),
          m.avg_position ? num(m.avg_position) : "—",
          badge(!m.impressions ? "No query data" : m.status, "gray"),
        ]),
      ),
      "Exact matching in v2. Legacy snapshots used phrase matching.",
    )
  );
}
function showPage(path) {
  const p = data.pages.find((p) => p.path === path);
  if (!p) return;
  activePage = p;
  const b = p.brief || {},
    a = p.audit || {};
  $("#page-detail").innerHTML =
    `<h2 id="detail-title">${esc(label(p.path))}</h2><p><a class="text-button" href="${esc(p.url)}" target="_blank" rel="noopener">View website page ↗</a></p><div class="row-meta">${badge(p.confidence, "amber")}${badge(p.intent, "gray")}${badge(p.index_status, "gray")}</div><div class="metrics">${metric("Impressions", num(p.current.impressions))}${metric("Clicks", num(p.current.clicks))}${metric("Average position", num(p.current.position))}${metric("CTR", pct(p.current.ctr))}</div>${data.legacy ? '<div class="callout">These page metrics use the legacy snapshot’s longer window, not the overview period.</div>' : ""}${panel("Why this page", p.evidence.map((e) => `<div class="issue">${esc(e)}</div>`).join(""))}${panel("Content brief", `<div class="fact-grid"><div class="fact"><small>Suggested title · draft</small>${esc(b.suggested_title || "Review intent before selecting a title")}</div><div class="fact"><small>Suggested H1 · draft</small>${esc(b.suggested_h1 || "Review query evidence first")}</div></div><h3 style="margin-top:22px">Buyer questions to review</h3><ul class="number-list">${(b.buyer_questions || []).map((q) => `<li>${esc(q)}</li>`).join("")}</ul>${b.query_review?.length ? `<h3>Queries to check against body content</h3><p class="chart-caption">${b.query_review.map(esc).join(" · ")}</p>` : ""}<div class="callout">${esc(b.note)}</div><button class="secondary" id="download-brief">Download brief</button>`)}${panel("Queries bringing this page into search", p.queries.length ? queryTable(p.queries) : empty("No query-to-page rows available. This does not prove the page has no visibility."))}${panel(
      "Internal-link suggestions",
      b.internal_links?.length
        ? table(
            ["Source", "Suggested anchor", "Evidence"],
            b.internal_links.map((l) => [
              esc(l.source),
              esc(l.anchor),
              esc(l.reason),
            ]),
          )
        : empty(
            "No supported suggestions yet. A content crawl and relevant source pages are required.",
          ),
    )}${panel("Current content & technical checks", `<div class="fact-grid"><div class="fact"><small>Current title</small>${esc(a.title || "Not available")}</div><div class="fact"><small>Current meta description</small>${esc(a.description || "Not available")}</div></div><p class="content-status">${num(a.word_count)} extracted words · ${num(a.incoming_links?.length)} incoming links from crawled pages. Word count is descriptive, not a quality score.</p>${(a.issues || []).map((i) => `<div class="issue">${esc(i)}</div>`).join("")}<details><summary>Extracted headings</summary>${(a.headings || []).map((h) => `<p>${esc(h.level)} · ${esc(h.text)}</p>`).join("")}</details>`)}${panel("Work status", `<label for="task-status" class="sr-only">Page work status</label><select id="task-status">${["To review", "In progress", "Ready to publish", "Published"].map((s) => `<option ${local.tasks[p.path] === s ? "selected" : ""}>${s}</option>`).join("")}</select><p class="content-status">Saved in this browser. Log the publication date in Changes & results to measure the outcome.</p>`)}`;
  $("#page-dialog").showModal();
}
function labHealth() {
  return (
    health() +
    panel(
      "Mobile lab checks",
      performanceData.reports?.length
        ? table(
            ["Page", "Performance", "Accessibility", "SEO", "Checked"],
            performanceData.reports.map((r) => [
              esc(new URL(r.url).pathname),
              num(r.scores.performance),
              num(r.scores.accessibility),
              num(r.scores.seo),
              esc(r.fetched_at?.slice(0, 10)),
            ]),
          )
        : empty(
            "Lighthouse results are not available yet. The weekly performance workflow will populate this section.",
          ),
      "Lighthouse lab scores, not field Core Web Vitals or ranking predictions.",
    )
  );
}
function render() {
  const view = Object.hasOwn(views, location.hash.slice(1))
    ? location.hash.slice(1)
    : "overview";
  $("#view-title").textContent = views[view][0];
  $("#view-subtitle").textContent = views[view][1];
  document.querySelectorAll("nav a").forEach((a) => {
    if (a.dataset.view === view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  $("#content").innerHTML = {
    overview,
    priorities,
    pages: pagesView,
    topics,
    results,
    health: labHealth,
    keywords,
  }[view]();
}
function mergeRecords(a, b) {
  return [...new Map([...a, ...b].map((r) => [r.id, r])).values()];
}
function validateLeadOverlap(records) {
  for (let i = 0; i < records.length; i++) {
    for (let j = i + 1; j < records.length; j++) {
      const a = records[i], b = records[j];
      if (a.start <= b.end && b.start <= a.end &&
          (a.page === '*' || b.page === '*' || a.page === b.page)) {
        throw Error('Backup contains overlapping enquiry counts. Resolve the overlap before importing.');
      }
    }
  }
  return records;
}
function validDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
function validateBackup(v) {
  if (
    v.version !== 2 ||
    !Array.isArray(v.changes) ||
    !Array.isArray(v.leads) ||
    v.changes.length > 1000 ||
    v.leads.length > 1000
  )
    throw Error("Invalid workspace backup");
  for (const c of v.changes)
    if (
      typeof c.id !== "string" ||
      !safePath(c.page) ||
      !validDate(c.published_at) ||
      c.published_at > new Date().toISOString().slice(0, 10) ||
      typeof c.summary !== "string" ||
      c.summary.length > 1200
    )
      throw Error("Invalid change record");
  for (const r of v.leads)
    if (
      typeof r.id !== "string" ||
      !validDate(r.start) ||
      !validDate(r.end) ||
      r.start > r.end ||
      !Number.isInteger(r.enquiries) ||
      !Number.isInteger(r.qualified) ||
      r.qualified < 0 ||
      r.enquiries < r.qualified ||
      !(r.page === "*" || safePath(r.page))
    )
      throw Error("Invalid enquiry record");
  const tasks = {};
  for (const [path, status] of Object.entries(v.tasks || {}))
    if (
      safePath(path) &&
      ["To review", "In progress", "Ready to publish", "Published"].includes(
        status,
      )
    )
      tasks[path] = status;
  return { ...v, tasks };
}
document.addEventListener("click", (event) => {
  const b = event.target.closest("[data-page]");
  if (b) showPage(b.dataset.page);
  if (event.target.id === "close-dialog") {
    $("#page-dialog").close();
    render();
  }
  if (event.target.id === "export-work")
    download(
      "petra-workspace.json",
      JSON.stringify(
        {
          version: 2,
          changes: allChanges(),
          tasks: local.tasks,
          leads: local.leads,
        },
        null,
        2,
      ),
    );
  if (event.target.id === "download-brief" && activePage) {
    const p = activePage,
      b = p.brief;
    download(
      `petra-${p.path.replace(/[^a-z0-9]/gi, "-")}-brief.md`,
      `# ${p.topic}\n\nPage: ${p.url}\nSnapshot: ${data.generated_at}\nConfidence: ${p.confidence}\n\n## Suggested title\n${b.suggested_title || "Review required"}\n\n## Suggested H1\n${b.suggested_h1 || "Review required"}\n\n## Buyer questions\n${b.buyer_questions.map((q) => "- " + q).join("\n")}\n\n## Query evidence\n${p.queries.map((q) => `- ${q.query}: ${q.impressions} impressions, ${q.clicks} clicks, position ${q.position}`).join("\n") || "Unavailable"}\n\n## Suggested internal links\n${b.internal_links.map((l) => `- ${l.source} → ${p.path}: ${l.anchor}`).join("\n") || "None supported yet"}\n\n${b.note}\n`,
      "text/markdown",
    );
  }
});
document.addEventListener("input", (event) => {
  if (["page-search", "page-filter"].includes(event.target.id)) {
    const q = $("#page-search").value.toLowerCase(),
      f = $("#page-filter").value;
    $("#page-table").innerHTML = pagesTable(
      data.pages.filter(
        (p) =>
          `${p.path} ${p.topic} ${p.queries.map((q) => q.query).join(" ")}`
            .toLowerCase()
            .includes(q) &&
          (f === "all" ||
            (f === "commercial" && p.business_value >= 3) ||
            (f === "issues" && p.audit.issues?.length) ||
            (f === "unassigned" && p.topic === "Unassigned")),
      ),
    );
  }
  if (["query-search", "brand-filter"].includes(event.target.id)) {
    const q = $("#query-search").value.toLowerCase(),
      f = $("#brand-filter").value;
    $("#query-table").innerHTML = queryTable(
      data.queries.filter(
        (r) =>
          r.query.toLowerCase().includes(q) &&
          (f === "all" ||
            (f === "brand" && r.branded) ||
            (f === "nonbrand" && !r.branded)),
      ),
    );
  }
});
document.addEventListener("change", async (event) => {
  if (event.target.id === "task-status" && activePage) {
    local.tasks[activePage.path] = event.target.value;
    save();
    toast("Work status saved in this browser.");
  }
  if (event.target.id === "import-work") {
    try {
      const f = event.target.files[0];
      if (!f || f.size > 2000000) throw Error("Choose a backup under 2 MB");
      const v = validateBackup(JSON.parse(await f.text()));
      const mergedLeads = validateLeadOverlap(mergeRecords(local.leads, v.leads));
      local.changes = mergeRecords(local.changes, v.changes);
      local.leads = mergedLeads;
      local.tasks = { ...local.tasks, ...v.tasks };
      save();
      render();
      toast("Workspace imported.");
    } catch (e) {
      toast(e.message);
    }
  }
});
document.addEventListener("submit", (event) => {
  if (!["change-form", "lead-form"].includes(event.target.id)) return;
  event.preventDefault();
  const v = Object.fromEntries(new FormData(event.target));
  if (event.target.id === "change-form") {
    if (!v.summary.trim()) return toast("Describe the published change.");
    local.changes.push({ id: crypto.randomUUID(), ...v });
  } else {
    v.enquiries = Number(v.enquiries);
    v.qualified = Number(v.qualified);
    if (v.start > v.end || v.qualified > v.enquiries)
      return toast(
        "Check dates and counts: qualified cannot exceed total enquiries.",
      );
    if (
      local.leads.some(
        (r) =>
          r.start <= v.end &&
          v.start <= r.end &&
          (r.page === "*" || v.page === "*" || r.page === v.page) &&
          !(r.start === v.start && r.end === v.end && r.page === v.page),
      )
    )
      return toast(
        "This overlaps existing counts. Use non-overlapping dates or separate pages.",
      );
    v.id = `${v.start}:${v.end}:${v.page}`;
    local.leads = mergeRecords(local.leads, [v]);
  }
  save();
  render();
  toast("Saved in this browser. Export a backup to keep your work.");
});
window.addEventListener("hashchange", () => {
  if (data) {
    render();
    window.scrollTo(0, 0);
  }
});
async function loadJSON(path, optional = false) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) {
    if (optional && r.status === 404) return { pages: [] };
    throw Error(`Could not load ${path} (HTTP ${r.status})`);
  }
  return r.json();
}
(async () => {
  try {
    const [raw, ed, inv, perf] = await Promise.all([
      loadJSON("data/latest.json"),
      loadJSON("data/editorial.json"),
      loadJSON("data/content.json", true),
      loadJSON("data/performance.json", true),
    ]);
    editorial = ed;
    inventory = inv;
    performanceData = perf;
    data = normalize(raw);
    freshness();
    render();
  } catch (e) {
    $("#status").className = "banner error";
    $("#status").textContent = e.message;
    $("#content").innerHTML = empty(
      "Could not load the workspace. Retry or check the update workflow.",
    );
  }
})();
