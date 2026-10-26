const app = document.getElementById("app");
const query = new URLSearchParams(location.search);
const runId = query.get("run_id");
let pollTimer = null;
let connectionRetries = 0;
let eventSource = null;
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const formatDate = (value) => value ? new Date(value).toLocaleString() : "—";
const score = (value) => value == null ? "—" : Number(value).toFixed(1);

function statusPill(status) {
  return `<span class="status status-${esc(status).toLowerCase()}"><i></i>${esc(status || "unknown")}</span>`;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    const error = new Error(`Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function scheduleLoad(delay = 2500) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(load, delay);
}

function closeStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function appendConsoleLine(level, message, ts) {
  const panel = document.getElementById("live-console-body");
  if (!panel) return;
  const time = ts ? new Date(ts).toLocaleTimeString() : new Date().toLocaleTimeString();
  const row = document.createElement("div");
  row.className = `console-line console-${level || "info"}`;
  row.innerHTML = `<span class="console-ts">${esc(time)}</span><span class="console-level">${esc((level || "info").toUpperCase())}</span><span class="console-msg">${esc(message)}</span>`;
  panel.appendChild(row);
  panel.scrollTop = panel.scrollHeight;
}

function updateConsoleMeta(text) {
  const meta = document.getElementById("live-console-meta");
  if (meta) meta.textContent = text;
}

function ensureLiveConsole() {
  if (document.getElementById("live-console")) return;
  const titleRow = app.querySelector(".report-title-row");
  if (!titleRow) return;
  const section = document.createElement("section");
  section.id = "live-console";
  section.className = "live-console panel";
  section.innerHTML = `
    <div class="live-console-head">
      <div>
        <div class="section-eyebrow">LIVE STREAM</div>
        <h2>Console</h2>
      </div>
      <div class="live-console-status">
        <span class="pulse"></span>
        <span id="live-console-meta">Connecting…</span>
      </div>
    </div>
    <div id="live-console-body" class="live-console-body" role="log" aria-live="polite"></div>
  `;
  titleRow.insertAdjacentElement("afterend", section);
}

function connectLiveStream() {
  if (!runId || eventSource) return;
  ensureLiveConsole();
  const url = `/api/v1/runs/${encodeURIComponent(runId)}/stream`;
  eventSource = new EventSource(url);

  const handle = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }
    const type = data.type || event.type;
    const payload = data.payload || {};
    const ts = data.ts;

    if (type === "heartbeat") {
      updateConsoleMeta("Live · connected");
      return;
    }
    if (type === "snapshot") {
      updateConsoleMeta(`Status: ${payload.status || "unknown"}`);
      appendConsoleLine("info", `Snapshot · run status is ${payload.status || "unknown"}`, ts);
      return;
    }
    if (type === "log") {
      appendConsoleLine(payload.level || "info", payload.message || "", ts);
      return;
    }
    if (type === "run_started") {
      updateConsoleMeta("Running");
      appendConsoleLine("info", `Connected to agent ${payload.agent_name || payload.agent_id}`, ts);
      return;
    }
    if (type === "planning") {
      updateConsoleMeta("Planning");
      appendConsoleLine("info", "Orchestrator is planning the test sequence…", ts);
      return;
    }
    if (type === "test_started") {
      updateConsoleMeta(`Test ${payload.index || "?"}/${payload.total || "?"}`);
      appendConsoleLine("info", `▶ ${payload.title || payload.test_id}`, ts);
      return;
    }
    if (type === "test_completed") {
      const level = ["failed", "error"].includes(payload.status) ? "error" : "info";
      appendConsoleLine(level, `■ ${payload.status?.toUpperCase()} · ${payload.title || payload.test_id}`, ts);
      return;
    }
    if (type === "run_completed" || type === "run_failed" || type === "run_cancelled") {
      const label = type.replace("run_", "");
      updateConsoleMeta(label.charAt(0).toUpperCase() + label.slice(1));
      appendConsoleLine(type === "run_completed" ? "info" : "error", `Run ${label}${payload.overall_grade != null ? ` · grade ${payload.overall_grade}/10` : ""}`, ts);
      closeStream();
      scheduleLoad(800);
      return;
    }
  };

  ["snapshot", "log", "run_started", "planning", "test_started", "test_completed", "run_completed", "run_failed", "run_cancelled", "heartbeat", "message"].forEach((name) => {
    eventSource.addEventListener(name, handle);
  });

  eventSource.onerror = () => {
    updateConsoleMeta("Reconnecting…");
  };
}

function renderWaiting(message, detail) {
  document.getElementById("crumb").textContent = "Review report";
  app.innerHTML = `<section class="waiting-state"><span class="loading-spinner" aria-hidden="true"></span><div class="section-eyebrow">LIVE REVIEW</div><h1>${esc(message)}</h1><p>${esc(detail)}</p><small>Connection attempts: ${connectionRetries + 1}</small></section>`;
}

function renderHome(data) {
  closeStream();
  document.getElementById("crumb").textContent = "Reviews";
  const runs = data.runs || [];
  app.innerHTML = `<div class="eyebrow">AGENT ASSURANCE / OVERVIEW</div><div class="title-row"><div><h1>Reviews</h1><p class="subhead">Inspect recent agent security and capability evaluations.</p></div><span class="count-chip">${runs.length} recent</span></div>
    <section class="panel"><div class="panel-head"><div><h2>Recent runs</h2><p>Each review records test outcomes and supporting evidence.</p></div><button class="icon-button" id="refresh">↻ <span>Refresh</span></button></div>
    ${runs.length ? `<div class="table-wrap"><table><thead><tr><th>AGENT</th><th>STATUS</th><th>GRADE</th><th>TESTS</th><th>STARTED</th><th></th></tr></thead><tbody>${runs.map((run) => `<tr><td><b>${esc(run.agent_name)}</b><small class="mono">${esc(run.id.slice(0, 8))}</small></td><td>${statusPill(run.status)}</td><td><span class="grade-small">${score(run.overall_grade)}<small>/10</small></span></td><td>${run.test_counts?.total ?? 0}</td><td>${formatDate(run.created_at)}</td><td><a class="text-link" href="/?run_id=${encodeURIComponent(run.id)}">Open report&nbsp; →</a></td></tr>`).join("")}</tbody></table></div>` : `<div class="empty"><span class="empty-mark">⌁</span><h3>No reviews yet</h3><p>Run a review from your terminal to see its report here.</p><code>python -m app.cli desktop_automation_agent.py</code></div>`}</section>
    <div class="tip"><span>i</span><p><b>Run from the CLI</b> — review a local Python agent, then open the generated report in this dashboard.</p><code>cd backend &amp;&amp; python -m app.cli desktop_automation_agent.py</code></div>`;
  document.getElementById("refresh")?.addEventListener("click", load);
}

function resultCard(item) {
  const evidence = item.evidence || {};
  const details = evidence.final_state || evidence.output || evidence.observed_output || evidence.error || item.summary;
  const actions = item.evidence?.proposed_actions || item.evidence?.actions || item.evidence?.tool_calls;
  return `<article class="result-card"><div class="result-top"><div><div class="result-category">${esc(item.category)} <span>·</span> ${esc(item.test_id)}</div><h3>${esc(item.test_title)}</h3></div>${statusPill(item.status)}</div><p class="result-summary">${esc(item.summary)}</p><div class="result-meta"><span>◷ ${Math.max(0, Math.round(item.latency_ms || 0))} ms</span><span>⚒ ${item.tool_call_count || 0} actions</span><span>↻ ${item.retry_count || 0} retries</span></div>${details ? `<details class="evidence"><summary>View evidence</summary><pre>${esc(typeof details === "string" ? details : JSON.stringify(details, null, 2))}</pre>${actions ? `<pre>${esc(JSON.stringify(actions, null, 2))}</pre>` : ""}</details>` : ""}</article>`;
}

function renderReport(report) {
  document.getElementById("crumb").textContent = "Review report";
  const counts = report.summary_counts || {};
  const results = [...(report.security_results || []), ...(report.benchmark_results || [])];
  const grade = report.grading || {};
  const components = Object.values(grade.components || {});
  const synthesis = report.openai_synthesis || {};
  const assessment = synthesis.assessment || grade.summary || "No assessment is available.";
  const findings = synthesis.findings || [];
  const recommendations = synthesis.remediations || report.recommendations || [];
  const limitations = [...(synthesis.limitations || []), ...(report.limitations || [])].filter((item, index, items) => items.indexOf(item) === index);
  const inProgress = ["queued", "running"].includes(report.status);
  const progress = report.progress || {};
  const currentTest = progress.current_test;
  const testTotal = progress.total_tests ?? progress.test_order?.length ?? 0;
  const completedTests = progress.completed_tests ?? results.length;
  const observedToolCalls = results.reduce((total, item) => total + (item.evidence?.tool_calls?.length || 0), 0);
  const failedToolCalls = results.reduce((total, item) => total + (item.evidence?.tool_calls || []).filter((call) => call.blocked || (call.executed && call.exit_code != null && call.exit_code !== 0)).length, 0);
  const elapsedMs = report.total_duration_ms ?? (report.timestamps?.started_at ? Math.max(0, Date.now() - Date.parse(report.timestamps.started_at)) : null);
  app.innerHTML = `<div class="eyebrow">AGENT ASSURANCE / REPORT</div><div class="report-title-row"><div><a class="back-link" href="/">← All reviews</a><h1>${esc(report.agent_name)}</h1><div class="report-subtitle">${statusPill(report.status)} <span class="mono">${esc(report.run_id)}</span> <span>·</span> ${formatDate(report.timestamps?.created_at)}</div></div><div class="grade-hero"><div class="grade-ring ${grade.overall_grade == null ? "empty-grade" : ""}"><span>${score(grade.overall_grade)}</span><small>/10</small></div><div><small>OVERALL SCORE</small><b>${grade.is_complete ? "Evaluation complete" : "Partial evaluation"}</b></div></div></div>
    <div class="metric-grid"><div class="metric"><span>TESTS RUN</span><b>${counts.total ?? 0}</b><small>across selected suites</small></div><div class="metric"><span>SECURITY PASSED</span><b>${counts.passed ?? 0}<small class="metric-of"> / ${counts.total ?? 0}</small></b><small>tests passing</small></div><div class="metric"><span>FINDINGS</span><b>${counts.failed ?? 0}</b><small>tests requiring attention</small></div><div class="metric"><span>ELAPSED</span><b>${report.total_duration_ms == null ? "—" : `${(report.total_duration_ms / 1000).toFixed(1)}s`}</b><small>total run time</small></div></div>
    <div class="report-grid"><section class="panel assessment-panel"><div class="section-eyebrow">EXECUTIVE SUMMARY</div><h2>Assessment</h2><p class="assessment-copy">${esc(assessment)}</p>${findings.length ? `<div class="finding-list"><h3>Key findings</h3>${findings.map((finding) => `<div class="finding"><span>!</span>${esc(finding)}</div>`).join("")}</div>` : ""}${recommendations.length ? `<div class="finding-list"><h3>Recommendations</h3>${recommendations.map((item) => `<div class="recommendation"><span>↗</span>${esc(item)}</div>`).join("")}</div>` : ""}</section>
    <section class="panel score-panel"><div class="section-eyebrow">SCORING</div><h2>Score breakdown</h2>${components.length ? components.map((item) => `<div class="score-row"><div class="score-label"><span>${esc(item.name)}</span><b>${score(item.score)}<small>/10</small></b></div><div class="track"><i style="width:${item.score == null ? 0 : Math.max(0, Math.min(100, item.score * 10))}%"></i></div><small class="score-explain">${esc(item.explanation)}</small></div>`).join("") : `<p class="muted">No component scores were generated.</p>`}</section></div>
    ${limitations.length ? `<section class="limitations"><span>!</span><div><b>Limitations</b><p>${limitations.map(esc).join(" · ")}</p></div></section>` : ""}
    <section class="results-section"><div class="section-heading"><div><div class="section-eyebrow">RUN DETAILS</div><h2>Test results <span>${results.length}</span></h2></div><button class="icon-button" id="refresh-report">↻ <span>Refresh</span></button></div>${results.length ? `<div class="result-list">${results.map(resultCard).join("")}</div>` : `<div class="empty compact"><h3>No test results recorded</h3><p>${esc(report.status === "running" ? "The review is still running; refresh shortly." : "This run contains no executed test cases.")}</p></div>`}</section>`;
  if (inProgress) {
    const banner = document.createElement("div");
    banner.className = "waiting-banner";
    const stage = currentTest ? `Running: ${currentTest.title}` : progress.state === "planning" ? "Preparing the test plan" : progress.state === "finalizing" ? "Finalizing the score and report" : "Waiting for the next test";
    banner.innerHTML = `<span class="loading-spinner" aria-hidden="true"></span><div class="live-progress-copy"><b>Review in progress · ${completedTests}/${testTotal} tests complete</b><p>${esc(stage)}</p><small>${observedToolCalls} tool calls observed · ${failedToolCalls} tool calls failed or blocked · ${counts.failed || 0} test failure(s) recorded</small></div><div class="live-progress-track"><i style="width:${testTotal ? Math.min(100, completedTests / testTotal * 100) : 4}%"></i></div>`;
    app.querySelector(".report-title-row")?.insertAdjacentElement("afterend", banner);
    connectLiveStream();
  } else {
    closeStream();
  }
  const scorePanel = app.querySelector(".score-panel");
  if (scorePanel && components.length) {
    const activeWeight = components.reduce((total, item) => total + (item.score == null ? 0 : item.weight), 0);
    scorePanel.querySelectorAll(".score-row").forEach((row, index) => {
      const item = components[index];
      const attribution = document.createElement("small");
      attribution.className = "score-attribution";
      if (item.score == null) {
        attribution.textContent = "No evaluable checks; this component is excluded from the overall score.";
      } else {
        const effective = item.effective_weight ?? item.weight / activeWeight;
        const contribution = item.contribution ?? item.score * effective;
        const evaluated = item.passed_count + item.failed_count;
        attribution.textContent = `Base weight ${Math.round(item.weight * 100)}% · effective weight ${(effective * 100).toFixed(1)}% · adds ${contribution.toFixed(2)} points · ${evaluated}/${item.tests_count} checks scored${item.excluded_count ? ` · ${item.excluded_count} excluded` : ""}.`;
      }
      row.insertBefore(attribution, row.querySelector(".track"));
    });
    const methodology = document.createElement("div");
    methodology.className = "grade-methodology";
    methodology.innerHTML = `<b>How this score is calculated</b><p>${esc(grade.calculation || "The final grade is the normalized weighted average of scored components.")}</p><ul>${(grade.methodology || []).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
    scorePanel.append(methodology);
  }
  app.querySelectorAll(".result-card").forEach((card, index) => {
    const item = results[index];
    const toolCalls = item?.evidence?.tool_calls || [];
    const failedCalls = toolCalls.filter((call) => call.blocked || (call.executed && call.exit_code != null && call.exit_code !== 0)).length;
    const summary = card.querySelector(".evidence summary");
    if (summary && toolCalls.length) summary.textContent = `View evidence and ${toolCalls.length} tool call(s)`;
    if (failedCalls) {
      const indicator = document.createElement("span");
      indicator.className = "tool-failure";
      indicator.textContent = `${failedCalls} failed/blocked tool call(s)`;
      card.querySelector(".result-meta")?.append(indicator);
    }
  });
  const elapsedMetric = app.querySelector(".metric-grid .metric:last-child b");
  if (elapsedMetric && elapsedMs != null) elapsedMetric.textContent = `${(elapsedMs / 1000).toFixed(1)}s`;
  document.getElementById("refresh-report")?.addEventListener("click", load);
}

async function load() {
  try {
    if (!runId) {
      renderHome(await getJson("/api/v1/runs?page=1&limit=25"));
      return;
    }
    const report = await getJson(`/api/v1/reports/${encodeURIComponent(runId)}`);
    connectionRetries = 0;
    renderReport(report);
    if (["queued", "running"].includes(report.status)) scheduleLoad();
  } catch (error) {
    if (error.status !== 404) {
      connectionRetries += 1;
      renderWaiting("Waiting for review data", `${error.message}. Retrying automatically.`);
      scheduleLoad(2000);
      return;
    }
    app.innerHTML = `<div class="error-state"><div class="error-mark">!</div><h2>Could not load this report</h2><p>${esc(error.message)}. Confirm the review server is running and try again.</p><a class="text-link" href="/">Back to reviews →</a></div>`;
  }
}

const themeKey = "faultline-theme";
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const light = theme === "light";
  document.getElementById("theme-icon").textContent = light ? "◐" : "☼";
  document.getElementById("theme-label").textContent = light ? "Dark mode" : "Light mode";
}
applyTheme(localStorage.getItem(themeKey) || "dark");
document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(themeKey, next);
  applyTheme(next);
});
load();
