/* RiskShield AI — frontend
   Every page reads from and writes to the FastAPI backend under /api.
   There is no local mock data here: what you see is what the agent
   pipeline (detect -> investigate -> decide -> check -> execute -> verify)
   actually did, persisted in the backend's database. */

let policiesCache = null;

// ---------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------

function money(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function statusClass(status) {
  return (
    {
      "Pending approval": "status-pending",
      Investigating: "status-investigating",
      Resolved: "status-resolved",
      Escalated: "status-escalated",
      Monitoring: "status-monitoring",
    }[status] || "status-investigating"
  );
}

function topSignalLabel(signals) {
  if (!signals || !signals.length) return "No anomalies";
  const fired = signals.filter((s) => s.points > 0).sort((a, b) => b.points - a.points);
  if (!fired.length) return "Within normal range";
  return fired.slice(0, 2).map((s) => s.name).join(" + ");
}

function bandWord(score) {
  if (score >= 60) return "elevated";
  if (score >= 30) return "moderate";
  return "low";
}

// ---------------------------------------------------------------------
// navigation
// ---------------------------------------------------------------------

const PAGE_TITLES = {
  overview: "Risk Overview",
  transactions: "Transaction Intelligence",
  investigations: "AI Investigations",
  simulator: "Risk Simulator",
  analytics: "Risk Analytics",
  policies: "Policy Guard",
  audit: "Audit Trail",
};

function showPage(id) {
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === id));
  document.querySelectorAll(".nav-item[data-page]").forEach((n) => n.classList.toggle("active", n.dataset.page === id));
  document.getElementById("pageTitle").textContent = PAGE_TITLES[id] || "Risk Overview";
  loadPage(id);
}
document.querySelectorAll(".nav-item[data-page]").forEach((n) => n.addEventListener("click", () => showPage(n.dataset.page)));

async function loadPage(id) {
  try {
    if (id === "overview") await refreshOverview();
    else if (id === "transactions") await renderTransactions();
    else if (id === "investigations") await renderInvestigationCards();
    else if (id === "analytics") await renderAnalytics();
    else if (id === "policies") await loadPolicies();
    else if (id === "audit") await renderAudit();
  } catch (e) {
    toast("Could not reach the RiskShield backend: " + e.message);
  }
}

// ---------------------------------------------------------------------
// overview
// ---------------------------------------------------------------------

function streamRowHtml(t) {
  return `<div class="stream-row"><span class="txid">${t.id}</span><span class="customer">${t.customer_name || "Simulation"}<small style="display:block;color:#718091;font-weight:400">${t.location} · ${t.device_known === false ? "New" : "Known"} device</small></span><span class="amount">${money(t.amount)}</span><span class="pill ${t.risk_level}">${t.risk_score}/100</span></div>`;
}

function donutGradient(dist) {
  const p1 = dist.low;
  const p2 = dist.low + dist.medium;
  return `conic-gradient(var(--accent) 0 ${p1}%, var(--warning) ${p1}% ${p2}%, var(--danger) ${p2}% 100%)`;
}

function insightText(d) {
  const entries = Object.entries(d.category_bars || {});
  if (!entries.length) return "No activity yet — generate a transaction to see live signal.";
  const top = entries.sort((a, b) => b[1] - a[1])[0];
  if (!top || top[1] === 0) return "No risk category is trending up right now.";
  return `${top[0]} risk is the largest contributor to current exposure (${Math.round(top[1])}/100).`;
}

async function renderInvestigationTable() {
  const rows = await api("/api/investigations");
  const top = rows.slice(0, 6);
  document.getElementById("investigationTable").innerHTML = top.length
    ? `<table class="table"><thead><tr><th>Incident</th><th>Risk</th><th>AI status</th><th>Recommended action</th></tr></thead><tbody>${top
        .map(
          (x) =>
            `<tr><td><b>${x.id}</b><div style="color:#718091;margin-top:3px">${x.title}</div></td><td><span class="pill ${x.level}">${x.score}/100</span></td><td class="agent-status">✦ ${x.status}</td><td>${x.action_label}</td></tr>`
        )
        .join("")}</tbody></table>`
    : `<div class="empty-note">No investigations yet — generate a transaction to see the agent in action.</div>`;
  return rows;
}

async function refreshOverview() {
  const [d, , txRows] = await Promise.all([
    api("/api/analytics/overview"),
    renderInvestigationTable(),
    api("/api/transactions?limit=6"),
  ]);

  document.getElementById("overallRisk").innerHTML = `${d.overall_risk}<span>/100</span>`;
  document.getElementById("riskSummary").textContent =
    `Current portfolio exposure is ${bandWord(d.overall_risk)}, based on ${d.tx_count} scored transaction${d.tx_count === 1 ? "" : "s"}.`;
  document.getElementById("txCount").textContent = d.tx_count.toLocaleString("en-IN");
  document.getElementById("highRisk").textContent = d.high_risk_count;
  document.getElementById("activeInvestigations").textContent = d.active_investigations;
  document.getElementById("autoActions").textContent = d.autonomous_actions;

  document.getElementById("legendLow").textContent = d.distribution.low + "%";
  document.getElementById("legendMedium").textContent = d.distribution.medium + "%";
  document.getElementById("legendHigh").textContent = d.distribution.high + "%";
  document.getElementById("donutTotal").textContent = d.tx_count;
  document.getElementById("riskDonut").style.background = donutGradient(d.distribution);

  document.getElementById("aiInsight").textContent = insightText(d);

  const scores = d.trend.slice(-12).map((t) => t.score);
  const maxScore = Math.max(10, ...scores);
  document.getElementById("sparkline").innerHTML = scores.length
    ? scores.map((s) => `<i style="height:${Math.max(6, (s / maxScore) * 100)}%"></i>`).join("")
    : `<span class="muted" style="font-size:10px">No data yet</span>`;

  document.getElementById("stream").innerHTML = txRows.length
    ? txRows.slice(0, 5).map(streamRowHtml).join("")
    : `<div class="empty-note">No transactions yet — generate one to see live scoring.</div>`;
}

// ---------------------------------------------------------------------
// transactions
// ---------------------------------------------------------------------

async function renderTransactions() {
  const q = document.getElementById("searchTx").value.trim();
  const level = document.getElementById("riskFilter").value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (level && level !== "all") params.set("level", level);

  const rows = await api("/api/transactions?" + params.toString());
  document.getElementById("transactionsTable").innerHTML = rows.length
    ? `<table class="table"><thead><tr><th>Transaction</th><th>Customer</th><th>Amount</th><th>Location</th><th>Risk</th><th>Signal</th></tr></thead><tbody>${rows
        .map(
          (t) =>
            `<tr><td><b>${t.id}</b></td><td>${t.customer_name || "—"}</td><td>${money(t.amount)}</td><td>${t.location}</td><td><span class="pill ${t.risk_level}">${t.risk_score}/100</span></td><td>${topSignalLabel(t.signals)}</td></tr>`
        )
        .join("")}</tbody></table>`
    : `<div class="empty-note">No transactions match your filters.</div>`;
}

async function generateTransaction() {
  const btn = document.getElementById("generateBtn");
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Scoring…";
  try {
    const res = await api("/api/transactions/generate", { method: "POST" });
    toast(`${res.transaction.id} generated · ${res.transaction.risk_score}/100 ${res.transaction.risk_level} risk`);
    showPage("transactions");
  } catch (e) {
    toast("Generation failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

// ---------------------------------------------------------------------
// investigations
// ---------------------------------------------------------------------

function verifyRowHtml(x) {
  if (x.after_score == null) return "";
  return `<div class="verify-row"><span>Verification</span><span>${x.before_score} → ${x.after_score} · ${x.verification_passed ? "Passed" : "Failed, escalated"}</span></div>`;
}

async function renderInvestigationCards() {
  const rows = await api("/api/investigations");
  document.getElementById("investigationBadge").textContent = rows.filter((r) =>
    ["Investigating", "Pending approval"].includes(r.status)
  ).length;

  document.getElementById("investigationCards").innerHTML = rows.length
    ? rows
        .map((x) => {
          const canApprove = x.status === "Pending approval";
          return `<div class="invest-card">
            <div class="card-top"><div><span class="pill ${statusClass(x.status)}">${x.status}</span><h3>${x.title}</h3><span class="sub">${x.id} · ${x.transaction_id}</span></div><div class="score">${x.score}</div></div>
            <div class="evidence">${x.evidence.map((e) => `<div>${e}</div>`).join("")}</div>
            <div class="root-cause"><strong>Why</strong>${x.root_cause}</div>
            <div class="recommend"><strong>AI recommendation</strong>${x.action_label}</div>
            ${verifyRowHtml(x)}
            ${canApprove ? `<button class="primary" style="margin-top:12px;width:100%" onclick="approveInvestigation('${x.id}')">Review &amp; approve action</button>` : ""}
          </div>`;
        })
        .join("")
    : `<div class="empty-note">No investigations yet — generate a transaction or run a scenario in the Risk Simulator.</div>`;
}

async function approveInvestigation(id) {
  try {
    const res = await api(`/api/investigations/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver: "Compliance Analyst" }),
    });
    toast(
      res.result.passed
        ? `${id}: action approved & verified — risk ${res.result.before_score} → ${res.result.after_score}`
        : `${id}: action approved, verification failed — escalated to review`
    );
    await renderInvestigationCards();
  } catch (e) {
    toast("Approval failed: " + e.message);
  }
}

// ---------------------------------------------------------------------
// simulator
// ---------------------------------------------------------------------

function updateOutputs() {
  document.getElementById("amountOut").textContent = money(document.getElementById("amount").value);
  document.getElementById("velocityOut").textContent = document.getElementById("velocity").value + " transactions / hour";
}
document.getElementById("amount").addEventListener("input", updateOutputs);
document.getElementById("velocity").addEventListener("input", updateOutputs);

const STAGE_LABEL = {
  detect: "Retrieved risk signals and computed a score",
  investigate: "Gathered evidence and identified the likely root cause",
  decide: "Selected a policy-aware recommended action",
  check: "Checked the action against the autonomous-action allowlist",
  execute: "Executed the action (simulated)",
  verify: "Re-scored the transaction to verify risk was actually reduced",
  approve: "Action approved by a human reviewer",
};

function renderSimResult(res) {
  const t = res.transaction;
  const inv = res.investigation;
  const auditTrail = res.audit_trail || [];
  const fired = (t.signals || []).filter((s) => s.points > 0).sort((a, b) => b.points - a.points);

  const logHtml = auditTrail
    .map((a, i) => `<div><b>${String(i + 1).padStart(2, "0")}</b> ${STAGE_LABEL[a.stage] || a.details}</div>`)
    .join("");

  const actionLabel = inv ? inv.action_label : "Continue monitoring";
  const canExecute = inv && ["Investigating", "Pending approval"].includes(inv.status);
  const approvalNote =
    inv && inv.requires_approval
      ? `<div class="muted" style="margin:8px 0">This action sits outside the autonomous allowlist under current policy. Executing it here simulates a human approving it.</div>`
      : "";

  document.getElementById("simResult").innerHTML = `
    <div class="analysis-header"><div><div class="eyebrow">AI RISK ASSESSMENT</div><h2>Transaction risk profile</h2></div><div class="risk-score-large">${t.risk_score}<span>/100</span></div></div>
    <div style="margin:20px 0"><span class="pill ${t.risk_level}">${t.risk_level.toUpperCase()} RISK</span></div>
    <h3 style="font-size:11px">Risk signals</h3>
    ${
      fired.length
        ? fired
            .map(
              (s) =>
                `<div class="signal"><span>${s.name}</span><span style="text-align:right;color:#aeb9c6">${s.points} pts</span><div class="signal-track" style="grid-column:1/-1"><i style="width:${Math.min(100, (s.points / s.weight) * 100)}%"></i></div></div>`
            )
            .join("")
        : `<p class="muted">No anomaly signals fired.</p>`
    }
    ${inv ? `<div class="root-cause"><strong>Why</strong>${inv.root_cause}</div>` : ""}
    <div class="agent-log"><h3 style="font-size:11px">Investigation Agent</h3>${logHtml}</div>
    <div class="recommend-action">
      <strong style="font-size:11px">✦ Recommended action</strong>
      <p style="margin:6px 0;color:#c3ced8;font-size:11px">${actionLabel}</p>
      ${approvalNote}
      ${canExecute ? `<button class="primary" onclick="executeSimulation('${t.id}')">Execute safe simulation</button>` : verifyRowHtml(inv || {})}
    </div>`;
}

async function analyzeScenario() {
  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Analyzing…";
  try {
    const body = {
      amount: Number(document.getElementById("amount").value),
      velocity: Number(document.getElementById("velocity").value),
      history: document.getElementById("history").value,
      device: document.getElementById("device").value,
      location: document.getElementById("location").value,
      beneficiary: document.getElementById("beneficiary").value,
      time: document.getElementById("time").value,
    };
    const res = await api("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    renderSimResult(res);
  } catch (e) {
    toast("Analysis failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

async function executeSimulation(txId) {
  try {
    const res = await api(`/api/simulate/${txId}/execute`, { method: "POST" });
    toast(
      `Mitigation executed. Risk ${res.result.before_score} → ${res.result.after_score}/100. ${res.result.passed ? "Verification passed." : "Verification failed — escalated."}`
    );
    renderSimResult(res);
  } catch (e) {
    toast("Execution failed: " + e.message);
  }
}

function loadHighRisk() {
  document.getElementById("amount").value = 87500;
  document.getElementById("velocity").value = 6;
  document.getElementById("history").value = "normal";
  document.getElementById("device").value = "new";
  document.getElementById("location").value = "unusual";
  document.getElementById("beneficiary").value = "new";
  document.getElementById("time").value = "unusual";
  updateOutputs();
  analyzeScenario();
}

// ---------------------------------------------------------------------
// analytics
// ---------------------------------------------------------------------

async function renderAnalytics() {
  const d = await api("/api/analytics/overview");

  document.getElementById("categoryBars").innerHTML = Object.entries(d.category_bars)
    .map(([k, v]) => `<div><span>${k}</span><b style="width:${v}%"></b><em>${Math.round(v)}</em></div>`)
    .join("");

  const h = d.operational_health;
  const ring = document.getElementById("scoreRing");
  ring.innerHTML = `${Math.round(h.autonomous_action_rate)}<span>AUTONOMY</span>`;
  ring.style.background = `radial-gradient(circle at center, var(--panel) 58%, transparent 59%), conic-gradient(var(--accent) 0 ${h.autonomous_action_rate}%, #1d2731 ${h.autonomous_action_rate}%)`;

  document.getElementById("healthRows").innerHTML = `
    <div class="score-row"><span>Autonomous action rate</span><b>${h.autonomous_action_rate}%</b></div>
    <div class="score-row"><span>Verification pass rate</span><b>${h.verification_pass_rate}%</b></div>
    <div class="score-row"><span>Escalation rate</span><b>${h.escalation_rate}%</b></div>
    <div class="score-row"><span>Resolved cases</span><b>${h.resolved_cases}</b></div>`;

  const labels = document.getElementById("trendLabels");
  if (d.trend.length) {
    labels.innerHTML = `<span>${new Date(d.trend[0].time).toLocaleTimeString()}</span><span>${new Date(d.trend[d.trend.length - 1].time).toLocaleTimeString()}</span>`;
  }
}

// ---------------------------------------------------------------------
// policy guard
// ---------------------------------------------------------------------

function renderPolicyStatus(p) {
  const autonomousCount = [
    p.autonomy_flag_transaction,
    p.autonomy_request_verification,
    p.autonomy_hold_transaction,
    p.autonomy_freeze_account,
  ].filter(Boolean).length;
  document.getElementById("policyStatus").innerHTML = `
    <div>✓ <span>${autonomousCount} of 4 high-impact actions on the autonomous allowlist</span></div>
    <div>✓ <span>Actions outside the allowlist require human approval before executing</span></div>
    <div>✓ <span>Every stage — detect, investigate, decide, check, execute, verify — is logged to the audit trail</span></div>
    <div>✓ <span>Verification runs after every mitigation, whether autonomous or human-approved</span></div>`;
}

async function loadPolicies() {
  const p = await api("/api/policies");
  policiesCache = p;
  document.getElementById("p1").value = p.threshold_low_medium;
  document.getElementById("p2").value = p.threshold_medium_high;
  document.getElementById("p3").value = p.threshold_high_critical;
  document.getElementById("toggleFlag").checked = p.autonomy_flag_transaction;
  document.getElementById("toggleVerify").checked = p.autonomy_request_verification;
  document.getElementById("toggleHold").checked = p.autonomy_hold_transaction;
  document.getElementById("toggleFreeze").checked = p.autonomy_freeze_account;
  renderPolicyStatus(p);
}

async function savePolicies() {
  const body = {
    threshold_low_medium: Number(document.getElementById("p1").value),
    threshold_medium_high: Number(document.getElementById("p2").value),
    threshold_high_critical: Number(document.getElementById("p3").value),
    autonomy_flag_transaction: document.getElementById("toggleFlag").checked,
    autonomy_request_verification: document.getElementById("toggleVerify").checked,
    autonomy_hold_transaction: document.getElementById("toggleHold").checked,
    autonomy_freeze_account: document.getElementById("toggleFreeze").checked,
  };
  try {
    const p = await api("/api/policies", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    policiesCache = p;
    renderPolicyStatus(p);
    toast("Policy Guard configuration saved — takes effect immediately");
  } catch (e) {
    toast("Save failed: " + e.message);
  }
}

// ---------------------------------------------------------------------
// audit trail
// ---------------------------------------------------------------------

async function renderAudit() {
  const rows = await api("/api/audit?limit=150");
  document.getElementById("auditTable").innerHTML = rows.length
    ? `<table class="table"><thead><tr><th>Time</th><th>Stage</th><th>Actor</th><th>Transaction</th><th>Details</th></tr></thead><tbody>${rows
        .map(
          (a) =>
            `<tr><td>${new Date(a.timestamp).toLocaleTimeString()}</td><td class="agent-status">${a.stage}</td><td>${a.actor}</td><td class="txid">${a.transaction_id || "—"}</td><td>${a.details}</td></tr>`
        )
        .join("")}</tbody></table>`
    : `<div class="empty-note">No audit events yet.</div>`;
}

// ---------------------------------------------------------------------
// notifications, health, live stream, boot
// ---------------------------------------------------------------------

document.getElementById("notificationBtn").addEventListener("click", async () => {
  try {
    const rows = await api("/api/investigations?status=Pending%20approval");
    toast(rows.length ? `${rows.length} investigation(s) awaiting approval` : "No investigations awaiting approval");
  } catch (e) {
    toast("Could not reach the backend");
  }
});

async function checkHealth() {
  const dot = document.getElementById("engineDot");
  const liveDot = document.getElementById("liveDot");
  try {
    await api("/api/health");
    dot.classList.remove("offline");
    liveDot.classList.remove("offline");
    document.getElementById("engineStatus").textContent = "AI Engine Online";
    document.getElementById("engineSub").textContent = "All services operational";
    document.getElementById("liveLabel").textContent = "Live monitoring";
  } catch (e) {
    dot.classList.add("offline");
    liveDot.classList.add("offline");
    document.getElementById("engineStatus").textContent = "Backend unreachable";
    document.getElementById("engineSub").textContent = "Start the FastAPI server — see README";
    document.getElementById("liveLabel").textContent = "Offline";
  }
}

function connectLiveStream() {
  if (typeof EventSource === "undefined") return;
  try {
    const es = new EventSource("/api/stream");
    es.onmessage = (e) => {
      try {
        const t = JSON.parse(e.data);
        toast(`Live monitor: ${t.id} scored ${t.risk_score}/100${t.investigation_opened ? " · investigation opened" : ""}`);
        const active = document.querySelector(".page.active")?.id;
        if (active === "overview") refreshOverview();
        else if (active === "transactions") renderTransactions();
        else if (active === "investigations") renderInvestigationCards();
      } catch (err) { /* ignore malformed events */ }
    };
  } catch (e) { /* live stream just won't update; rest of the app still works */ }
}

updateOutputs();
checkHealth();
refreshOverview();
connectLiveStream();
setInterval(checkHealth, 15000);
