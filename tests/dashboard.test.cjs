const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const SITE = "https://petrajewelryfactory.com";
const source = fs.readFileSync(path.join(__dirname, "../assets/dashboard.js"), "utf8");
const audit = (url, status = 200) => ({ url, final_url: url, crawl_status: "checked", http_status: status, issues: status === 200 ? [] : [`HTTP ${status}`] });
const page = (url, clicks = 1) => ({
  url, path: "/", current: { clicks, impressions: clicks * 10 }, previous: {},
  audit: audit(url), brief: { suggested_title: "Saved draft", internal_links: [], buyer_questions: [], note: "Draft" },
  queries: [], evidence: [], actions: [], topic: "Unassigned", confidence: "Low sample",
});
const snapshot = (pages) => ({ schema_version: 2, generated_at: "2026-11-05T00:00:00Z", pages, period: { start: "2026-10-06", end: "2026-11-02" } });

function workspace(raw, inv = {}, attempt = {}) {
  const elements = {};
  const context = vm.createContext({
    URL, Date, setTimeout, clearTimeout,
    localStorage: { getItem: () => null },
    document: { addEventListener() {}, querySelector: (selector) => elements[selector] ||= { showModal() {} } },
    window: { addEventListener() {} },
    fetch: () => new Promise(() => {}),
    raw, inv, attempt,
  });
  vm.runInContext(source, context);
  vm.runInContext("editorial = {topics: [], changes: []}; inventory = inv; crawlAttempt = attempt; data = normalize(raw);", context);
  return { elements, run: (expression) => vm.runInContext(expression, context) };
}

test("fragment workspaces retain separate clicks, links and task identities", () => {
  const root = page(SITE + "/", 8), fragment = page(SITE + "/#/services", 1);
  const { run, elements } = workspace(snapshot([root, fragment]));
  assert.equal(run("data.pages[1].path"), "/#/services");
  assert.equal(run("data.pages[0].current.clicks"), 8);
  assert.equal(run("data.pages[1].current.clicks"), 1);
  assert.equal(run("data.url_collisions[0].request_url"), SITE + "/");
  run("local.tasks['/'] = 'Published'; showPage('/#/services')");
  assert.equal(run("activePage.url"), fragment.url);
  assert.equal(run("local.tasks['/#/services']"), undefined);
  assert.match(elements["#page-detail"].innerHTML, /Brief on hold/);
  assert.doesNotMatch(elements["#page-detail"].innerHTML, /id="download-brief"/);
});

test("failed fresh crawl overrides saved audits without refreshing search timestamps or metrics", () => {
  const url = SITE + "/private-label/", raw = snapshot([page(url, 4)]);
  const attempt = { attempted_at: "2026-11-16T00:00:00Z", status: "failed", pages: [audit(url, 404)], blockers: ["Required page: HTTP 404"], warnings: [], coverage: { html_ok: 0, recorded: 1 } };
  const { run, elements } = workspace(raw, { generated_at: "2026-11-05T00:00:00Z", pages: [audit(url)] }, attempt);
  assert.equal(run("data.pages[0].audit.http_status"), 404);
  assert.equal(run("data.pages[0].brief.status"), "blocked");
  assert.equal(run("data.generated_at"), raw.generated_at);
  assert.equal(run("data.pages[0].current.clicks"), 4);
  assert.equal(raw.pages[0].audit.http_status, 200);
  run("freshness()");
  assert.match(elements["#status"].textContent, /Search data is stale/);
  assert.match(run("health()"), /2026-11-16/);
  assert.match(run("health()"), /failed/);
});

test("a partial attempt cannot reuse a missing page's successful historical audit", () => {
  const { run } = workspace(snapshot([page(SITE + "/private-label/")]), {}, { attempted_at: "2026-11-16T00:00:00Z", status: "failed", pages: [] });
  assert.equal(run("data.pages[0].audit.crawl_status"), "not_checked");
  assert.equal(run("data.pages[0].brief.status"), "blocked");
});

test("crawl-only discovered pages have unknown search metrics and no invented draft", () => {
  const { run } = workspace(snapshot([]), { generated_at: "2026-11-16T00:00:00Z", pages: [audit(SITE + "/new-page/")] });
  assert.equal(run("data.pages[0].current.clicks"), null);
  assert.equal(run("data.pages[0].brief.suggested_title"), undefined);
  assert.equal(run("data.pages[0].brief.status"), "blocked");
});

test("missing health report is unknown and older attempts cannot override a newer inventory", () => {
  const { run } = workspace(snapshot([page(SITE + "/")]), { generated_at: "2026-11-16T00:00:00Z", pages: [audit(SITE + "/")] }, { attempted_at: "2026-11-01T00:00:00Z", status: "failed", pages: [audit(SITE + "/", 403)] });
  assert.equal(run("data.pages[0].audit.http_status"), 200);
  assert.match(run("health()"), /Health gate has not run/);
  assert.doesNotMatch(run("health()"), /Check: passed/);
});

test("unsafe link sources are removed and diagnostics are escaped", () => {
  const root = page(SITE + "/"), missing = page(SITE + "/missing/");
  root.brief.internal_links = [{ source: "/missing/", anchor: "Factory", reason: "Related" }];
  const { run } = workspace(snapshot([root, missing]), {}, { attempted_at: "2026-11-16T00:00:00Z", status: "failed", pages: [audit(root.url), audit(missing.url, 404)], blockers: ["<img onerror=alert(1)>"] });
  assert.equal(run("data.pages[0].brief.internal_links.length"), 0);
  assert.match(run("health()"), /&lt;img onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(run("health()"), /<img/);
});

test("Lighthouse age is visible independently from crawl and search age", () => {
  const { run } = workspace(snapshot([]));
  run("performanceData = { reports: [{url: SITE + '/', fetched_at: '2026-09-07T00:00:00Z', scores: {performance: 90, accessibility: 90, seo: 90}}] }");
  assert.match(run("labHealth()"), /2026-09-07 · stale/);
});

test('fact review requires evidence; unknown revokes an earlier value', () => {
  const {run} = workspace(snapshot([]));
  run("workspaceData = {fact_fields:{moq:'MOQ',waterproof:'Waterproof'},capability_fields:['waterproof']}");
  assert.equal(run("validateReview('fact_reviews','moq',{status:'unknown',value:'made up'}).value"), null);
  assert.throws(()=>run("validateReview('fact_reviews','moq',{status:'confirmed',value:'made up'})"), /evidence/);
  run("fact = {status:'confirmed',value:'Fixture limitation',public_safe:true,source_url:'https://evidence.example/proof',reviewer:'Fixture reviewer',reviewed_at:'2026-11-15'}");
  assert.throws(()=>run("validateReview('fact_reviews','waterproof',fact)"), /supported/);
  assert.equal(run("validateReview('fact_reviews','waterproof',{...fact,supported:false}).supported"),false);
  assert.equal(run("publicReference('https://evidence.example/?token=secret')"),false);
  assert.equal(run("canonicalDestination('/%2e%2e/private-label/')"),false);
});

test('term approval requires SERP evidence and a real destination',()=>{
  const {run}=workspace(snapshot([]));
  run("workspaceData = {terms:[{keyword:'fixture'}]}; term={status:'approved',reason:'Fixture',approved_page:'/#/private-label',intent:'commercial',page_type:'supplier_landing',reviewer:'Fixture',reviewed_at:'2026-11-15',serp:{urls:['https://evidence.example/supplier'],checked_at:'2026-11-15',market:'Fixture',device:'desktop',page_type:'supplier_landing'}}");
  assert.throws(()=>run("validateReview('term_reviews','fixture',term)"),/destination/);
  assert.equal(run("validateReview('term_reviews','fixture',{...term,approved_page:'/private-label/'}).status"),'approved');
  assert.throws(()=>run("validateReview('term_reviews','fixture',{...term,approved_page:'/private-label/',intent:'informational'})"),/intent/);
});

test('local review changes hold downloads until reviewed import and rebuild',()=>{
  const {run}=workspace(snapshot([]));
  run("inventory.generated_at = new Date().toISOString(); workspaceData={generated_at:inventory.generated_at,sources:{crawl:inventory.generated_at}};");
  assert.equal(run('Boolean(currentPack())'),true);
  run("local.review = {fact_reviews:{moq:{status:'unknown',value:null}}}");
  assert.equal(run('Boolean(currentPack())'),false);
  assert.equal(run('workspaceBackup().review.fact_reviews.moq.value'),null);
});

test('weekly review escapes source text and handles missing report',()=>{
  const {run}=workspace(snapshot([]));
  assert.match(run('weeklyReview()'),/Build the weekly review/);
  run("workspaceData={generated_at:'2026-11-16',terms:[],facts:{},fact_fields:{},draft_pack:{packets:[]},sources:{search:'2026-11-16'},alerts:[{severity:'warning',message:'<img onerror=1>',next_action:'Review',owner:'Fixture'}]}");
  assert.match(run('weeklyReview()'),/&lt;img onerror=1&gt;/);
  assert.doesNotMatch(run('weeklyReview()'),/<img/);
});

test('browser backup validates reviewed fields and preserves them for explicit public import',()=>{
  const {run}=workspace(snapshot([]));
  run("workspaceData={fact_fields:{moq:'MOQ'}}");
  assert.equal(run("validateBackup({version:2,changes:[],leads:[],review:{fact_reviews:{moq:{status:'unknown',value:'discard'}}}}).review.fact_reviews.moq.value"),null);
  assert.throws(()=>run("validateBackup({version:2,changes:[],leads:[],review:{fact_reviews:{moq:{status:'confirmed',value:'unsupported'}}}})"),/evidence/);
});

test('a Python-normalized review clears pending state despite JSON key order and generated term fields',()=>{
  const {run}=workspace(snapshot([]));
  run("workspaceData={fact_fields:{moq:'MOQ'}}; local.review={fact_reviews:{moq:{status:'unknown',value:null}}}; editorial.fact_reviews={moq:{value:null,status:'unknown'}}");
  assert.equal(run('pendingReviews()'),false);
});

test("daily traffic can update the overview without redating page evidence", () => {
  const {run, elements} = workspace(snapshot([]));
  run(`globalThis.fixture = {verified_on:"2026-11-18", daily:Array.from({length:28}, (_,i) => ({
    date:new Date(Date.UTC(2026,9,20+i)).toISOString().slice(0,10), clicks:i===0?2:0, impressions:i===0?27:1
  }))}; searchSummary = dailySummary(fixture); freshness(searchSummary)`);
  assert.equal(run("searchSummary.overall.clicks"), 2);
  assert.equal(run("searchSummary.overall.impressions"), 54);
  assert.match(elements["#period"].textContent, /2026-11-16/);
  run("freshness(data)");
  assert.match(elements["#period"].textContent, /2026-11-02/);
  assert.equal(run("dailySummary({ ...fixture, daily:fixture.daily.slice(1) })"), null);
  assert.equal(run("fixture.daily[7].clicks = -1; dailySummary(fixture)"), null);
});
