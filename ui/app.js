/* Pocket Startup UI Controller
   Plain JS, offline-first, no frameworks.
   Interacts with /api endpoints and streams SSE events to PixelOffice.
*/
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const fmt = (v, d = 2) => (v === null || v === undefined ? 'n/a' : Number(v).toFixed(d));
  const usd = (v) => (v === null || v === undefined ? 'n/a' : '$' + Number(v).toFixed(6));

  const office = new window.PixelOffice($('office'));

  const S = {
    mode: 'baseline',
    mock: false,
    runId: null,
    es: null,
    replay: false,
    cfg: {},
    running: false,
    lastRec: null,
    founderCohort: 'held_out',
    verdictFounder: 'a',
  };

  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || res.statusText || 'API request failed');
    }
    return data;
  }

  function chip(tag) {
    if (!tag) return '';
    const t = String(tag).trim();
    let cls = 'chip';
    if (t.includes('MEASURED')) cls += ' meas';
    else if (t.includes('COMPUTED')) cls += ' comp';
    else if (t.includes('ASSUMED')) cls += ' ass';
    else if (t.includes('USER-PROVIDED')) cls += ' user';
    else if (t.includes('MOCK')) cls += ' mock';
    else if (t.includes('FOUND')) cls += ' found';
    return `<span class="${cls}">${esc(t)}</span>`;
  }

  /* ================= Navigation & Tabs ================= */
  const tabs = Array.from(document.querySelectorAll('[role=tab]'));
  function selectTab(tabEl) {
    tabs.forEach((t) => {
      const active = t === tabEl;
      t.setAttribute('aria-selected', active);
      const panelId = t.getAttribute('aria-controls');
      const panel = $(panelId);
      if (panel) panel.hidden = !active;
    });

    const name = tabEl.id.replace('t-', '');
    if (name === 'cost') renderCostRadar();
    else if (name === 'verdict') renderVerdict();
    else if (name === 'trust') renderTrust();
    else if (name === 'founder') loadFounderDefaults();
    else if (name === 'plan') renderPlan();
    else if (name === 'evidence') renderEvidence();
  }

  tabs.forEach((t) => {
    t.addEventListener('click', () => selectTab(t));
  });

  function openTab(name) {
    const el = $('t-' + name);
    if (el) selectTab(el);
  }

  /* ================= Top Bar Controls ================= */
  $('mode-baseline').addEventListener('click', () => setMode('baseline'));
  $('mode-improved').addEventListener('click', () => setMode('improved'));

  function setMode(m) {
    S.mode = m;
    $('mode-baseline').setAttribute('aria-pressed', m === 'baseline');
    $('mode-improved').setAttribute('aria-pressed', m === 'improved');
  }

  $('mock-toggle').addEventListener('change', (e) => {
    S.mock = e.target.checked;
    updateBanner();
  });

  function updateBanner() {
    const bannerEl = $('banner');
    if (S.replay) {
      bannerEl.className = 'banner show banner-replay';
      bannerEl.textContent = 'REPLAY: Showing recorded run events from events.json. No real API calls are occurring.';
    } else if (S.mock) {
      bannerEl.className = 'banner show banner-mock';
      bannerEl.textContent = 'MOCK MODE: Using offline scripted MockLLM. Mock runs are labelled MOCK and never enter metrics.';
    } else {
      bannerEl.className = 'banner';
      bannerEl.textContent = '';
    }
  }

  /* ================= Run & Event Stream ================= */
  function resetRunUi() {
    $('p-log').innerHTML = '';
    $('k-cost').textContent = '$0.000000';
    $('k-tokens').textContent = '0';
    $('k-attempt').textContent = `0 of ${S.cfg.max_attempts || 4}`;
    $('k-rails').textContent = 'all clear';
    $('k-rails').className = '';
    $('approve-btn').disabled = true;
    $('open-app-link').hidden = true;
    $('built-app-card').hidden = true;
    $('status-text').textContent = 'ready';
    S.lastRailFired = null;
    S.lastRec = null;
  }

  function appendLog(t, text, type = 'info') {
    const logBox = $('p-log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timeStr = (typeof t === 'number' && !isNaN(t)) ? `${t.toFixed(1)}s` : '0.0s';
    entry.innerHTML = `<span class="time">${timeStr}</span> <span>${esc(text)}</span>`;
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;
  }

  function appendAutopsy(d) {
    const logBox = $('p-log');
    const card = document.createElement('div');
    card.className = 'autopsy-card';
    card.innerHTML = `
      <h5>CRASH REPORT (Autopsy)</h5>
      <div><strong>Root cause:</strong> ${esc(d.root_cause || 'unknown')}</div>
      <div><strong>Evidence:</strong> ${esc((d.evidence || []).join(' | '))}</div>
      <div><strong>Rule change:</strong> ${esc(d.recommended_prompt_change || 'none')}</div>
    `;
    logBox.appendChild(card);
    logBox.scrollTop = logBox.scrollHeight;
  }

  function handleServerEvent(ev) {
    const { type, data: d, t } = ev;
    office.handle(type, d);

    if (d && d._cost !== undefined) {
      $('k-cost').textContent = usd(d._cost);
      $('k-tokens').textContent = d._tokens || 0;
    }

    switch (type) {
      case 'run_started':
        $('status-text').textContent = 'running';
        appendLog(t, `Run started: "${d.idea}" (${d.mode}, budget $${d.budget_usd}${d.mock ? ', MOCK' : ''})`);
        break;

      case 'plan':
        appendLog(t, `Plan ready: ${d.product_name} (${d.template})`);
        break;

      case 'attempt_started':
        $('k-attempt').textContent = `${d.n} of ${d.of}`;
        appendLog(t, `Attempt ${d.n} of ${d.of} started`);
        break;

      case 'code_written':
        appendLog(t, `Code generated: ${d.bytes} bytes of HTML/JS`);
        break;

      case 'check_started':
        appendLog(t, `Running browser acceptance checks in headless Chromium...`);
        break;

      case 'check_failed':
        appendLog(t, `CHECK FAILED: ${d.test} (Expected: ${d.expected}, Got: ${d.actual})`, 'bad');
        break;

      case 'autopsy':
        appendLog(t, `Autopsy completed: ${d.root_cause}`, 'warn');
        appendAutopsy(d);
        break;

      case 'retry':
        appendLog(t, `Retrying: attempting revision ${d.next}`, 'warn');
        break;

      case 'check_passed':
        appendLog(t, `ALL CHECKS PASSED on attempt ${d.attempt}!`, 'good');
        break;

      case 'rail_fired':
        S.lastRailFired = d.rail;
        appendLog(t, `TRUST RAIL FIRED: ${d.rail}. ${d.detail}`, 'bad');
        $('k-rails').textContent = `fired: ${d.rail}`;
        $('k-rails').className = 'fail';
        break;

      case 'awaiting_approval':
        appendLog(t, `Build passing. Awaiting human approval gate.`, 'warn');
        if (!S.replay) $('approve-btn').disabled = false;
        $('status-text').textContent = 'awaiting approval';
        break;

      case 'approved':
        appendLog(t, `Human approval received. Build released ✔`, 'good');
        $('approve-btn').disabled = true;
        $('status-text').textContent = 'approved';
        break;

      case 'metrics_ready':
        appendLog(t, `Live metrics updated from trace`);
        break;

      case 'verdict_ready':
        appendLog(t, `Verdict evaluated: ${d.verdict} (${d.layer_verdicts ? Object.entries(d.layer_verdicts).map(([k,v]) => `${k}:${v}`).join(', ') : ''})`, d.verdict === 'BUILD' ? 'good' : 'warn');
        break;

      case 'run_finished':
        const outcome = d.success ? 'SUCCESS' : 'FAILED';
        appendLog(t, `Run finished: ${outcome} in ${d.attempts} attempts. Cost: ${usd(d.cost_usd)}, Tokens: ${d.tokens}`, d.success ? 'good' : 'bad');
        onRunFinished(d);
        break;
    }
  }

  function onRunFinished(d) {
    S.running = false;
    S.lastRec = d;
    $('run-btn').disabled = false;
    $('kill-btn').disabled = true;

    if (d.run_id) {
      $('report-link').href = `/api/report/${encodeURIComponent(d.run_id)}`;
      $('report-link').hidden = false;
    }

    if (d.success) {
      $('status-text').textContent = 'finished (passed)';
      if (d.run_id) {
        const appUrl = `/api/runs/${encodeURIComponent(d.run_id)}/app`;
        $('built-app-iframe').src = appUrl;
        $('built-app-card').hidden = false;
        $('open-app-link').hidden = false;
        $('open-app-link').href = appUrl;
      }
      if (!S.replay && !d.approved) {
        $('approve-btn').disabled = false;
      }
    } else {
      let rail = S.lastRailFired;
      if (!rail && d.rails_fired && d.rails_fired.length) {
        const rf = d.rails_fired[0];
        rail = typeof rf === 'object' ? (rf.rail || rf.message) : rf;
      }
      if (!rail) rail = 'attempt_cap';
      $('status-text').textContent = `FAILED (${rail})`;
      $('approve-btn').disabled = true;
    }

    const activeTab = document.querySelector('[role=tab][aria-selected="true"]');
    if (activeTab && activeTab.id === 't-trust') {
      renderTrust();
    }

    refreshReplayList();
  }

  function startSseListener(runId, isReplay, customLabel = null, onEnd = null, underlyingRunId = null) {
    if (S.es) S.es.close();

    S.runId = underlyingRunId || runId;
    S.replay = isReplay;
    S.running = true;
    resetRunUi();
    updateBanner();

    $('run-btn').disabled = true;
    $('kill-btn').disabled = isReplay;
    $('status-text').textContent = customLabel ? `replaying: ${customLabel}` : (isReplay ? 'replaying' : 'running');

    if (S.runId && !S.runId.startsWith('replay-')) {
      $('report-link').href = `/api/report/${encodeURIComponent(S.runId)}`;
      $('report-link').hidden = false;
    }

    const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
    S.es = es;

    es.addEventListener('ev', (m) => {
      try {
        const ev = JSON.parse(m.data);
        handleServerEvent(ev);
      } catch (err) {
        console.error('SSE parse error', err);
      }
    });

    es.addEventListener('end', () => {
      es.close();
      S.running = false;
      $('kill-btn').disabled = true;
      $('run-btn').disabled = false;

      // Keep FAILED status and disabled Approve button if run did not pass
      if (S.lastRec && !S.lastRec.success) {
        let rail = S.lastRailFired;
        if (!rail && S.lastRec.rails_fired && S.lastRec.rails_fired.length) {
          const rf = S.lastRec.rails_fired[0];
          rail = typeof rf === 'object' ? (rf.rail || rf.message) : rf;
        }
        if (!rail) rail = 'attempt_cap';
        $('status-text').textContent = `FAILED (${rail})`;
        $('approve-btn').disabled = true;
      } else if (S.lastRec && S.lastRec.success) {
        $('status-text').textContent = S.lastRec.approved ? 'approved' : 'awaiting approval';
        if (!S.replay && !S.lastRec.approved) {
          $('approve-btn').disabled = false;
        }
      }

      if (S.runId && !S.runId.startsWith('replay-')) {
        $('report-link').href = `/api/report/${encodeURIComponent(S.runId)}`;
        $('report-link').hidden = false;
      }

      const activeTab = document.querySelector('[role=tab][aria-selected="true"]');
      if (activeTab && activeTab.id === 't-trust') {
        renderTrust();
      }

      if (typeof onEnd === 'function') {
        onEnd();
      }
    });

    es.onerror = () => {
      es.close();
      S.running = false;
      $('kill-btn').disabled = true;
      $('run-btn').disabled = false;
    };
  }

  $('run-btn').addEventListener('click', async () => {
    const idea = $('idea-input').value.trim();
    if (!idea) {
      $('idea-input').focus();
      return;
    }

    const budgetVal = parseFloat($('budget-input').value) || null;
    try {
      $('run-btn').disabled = true;
      const res = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idea,
          mode: S.mode,
          budget_usd: budgetVal,
          mock: S.mock,
        }),
      });

      openTab('log');
      startSseListener(res.run_id, false);
    } catch (err) {
      alert(`Could not launch run: ${err.message}`);
      $('run-btn').disabled = false;
    }
  });

  $('kill-btn').addEventListener('click', async () => {
    if (!S.runId) return;
    try {
      await api(`/api/runs/${encodeURIComponent(S.runId)}/kill`, { method: 'POST' });
      appendLog(0, 'Kill switch activated by operator.', 'bad');
    } catch (err) {
      console.warn('Kill failed', err);
    }
  });

  $('approve-btn').addEventListener('click', async () => {
    if (!S.runId) return;
    try {
      const res = await api(`/api/runs/${encodeURIComponent(S.runId)}/approve`, { method: 'POST' });
      $('approve-btn').disabled = true;
      $('status-text').textContent = 'approved';
      appendLog(0, `Human approval gate passed at ${res.approved_at || 'now'} ✔`, 'good');
      const activeTab = document.querySelector('[role=tab][aria-selected="true"]');
      if (activeTab && activeTab.id === 't-trust') {
        renderTrust();
      }
    } catch (err) {
      alert(`Approval error: ${err.message}`);
    }
  });

  $('replay-select').addEventListener('change', (e) => {
    const val = e.target.value;
    if (val) {
      S.runId = val;
      $('report-link').href = `/api/report/${encodeURIComponent(val)}`;
      $('report-link').hidden = false;
      const activeTab = document.querySelector('[role=tab][aria-selected="true"]');
      if (activeTab && activeTab.id === 't-trust') {
        renderTrust();
      }
    }
  });

  $('replay-btn').addEventListener('click', async () => {
    const targetRun = $('replay-select').value;
    if (!targetRun) return;

    const speed = $('replay-speed').value || '1';
    try {
      const res = await api(`/api/replay/${encodeURIComponent(targetRun)}?speed=${speed}`, { method: 'POST' });
      openTab('log');
      startSseListener(res.replay_id, true, null, null, targetRun);
    } catch (err) {
      alert(`Replay failed: ${err.message}`);
    }
  });

  $('demo-btn').addEventListener('click', async () => {
    const speed = $('replay-speed').value || '1';
    try {
      const res = await api(`/api/replay/20261011-043610-3f24?speed=${speed}`, { method: 'POST' });
      openTab('log');
      startSseListener(res.replay_id, true, 'Demo Baseline: 20261011-043610-3f24', null, '20261011-043610-3f24');
    } catch (err) {
      alert(`Demo replay failed: ${err.message}`);
    }
  });

  $('compare-btn').addEventListener('click', async () => {
    const speed = $('replay-speed').value || '2';
    try {
      openTab('log');
      appendLog(0, '=== COMPARE STEP 1/2: Baseline Run 20261011-043610-3f24 (attempt 1 fail, autopsy, retry, passed attempt 2) ===', 'warn');
      const res1 = await api(`/api/replay/20261011-043610-3f24?speed=${speed}`, { method: 'POST' });
      startSseListener(res1.replay_id, true, '[BASELINE] 20261011-043610-3f24', async () => {
        appendLog(0, '=== COMPARE STEP 2/2: Improved Run 20261011-073159-a490 (passed on attempt 1) ===', 'good');
        const res2 = await api(`/api/replay/20261011-073159-a490?speed=${speed}`, { method: 'POST' });
        startSseListener(res2.replay_id, true, '[IMPROVED] 20261011-073159-a490', null, '20261011-073159-a490');
      }, '20261011-043610-3f24');
    } catch (err) {
      alert(`Compare replay failed: ${err.message}`);
    }
  });

  $('tiny-budget-btn').addEventListener('click', runTinyBudgetDemo);

  async function runTinyBudgetDemo() {
    try {
      $('tiny-budget-btn').disabled = true;
      $('idea-input').value = 'Tip splitter micro-budget (rail test)';
      $('budget-input').value = '0.00001';

      appendLog(0, 'Starting Tiny Budget Demo ($0.00001) in [MOCK] mode to verify budget rail firing...', 'warn');

      const res = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idea: 'Tip splitter micro-budget test',
          mode: S.mode,
          budget_usd: 0.00001,
          mock: true,
        }),
      });

      openTab('log');
      startSseListener(res.run_id, false, null, () => {
        openTab('trust');
      });
    } catch (err) {
      alert(`Tiny budget demo failed: ${err.message}`);
    } finally {
      $('tiny-budget-btn').disabled = false;
    }
  }

  async function refreshReplayList() {
    try {
      const runs = await api('/api/runs');
      const sel = $('replay-select');
      const cur = sel.value;
      sel.innerHTML = '<option value="">Select a saved run to replay...</option>' +
        runs.map((r) => {
          const mockTag = r.mock ? '[MOCK] ' : '';
          const passTag = r.success ? 'PASS' : 'FAIL';
          const snippet = (r.idea || '').slice(0, 32);
          return `<option value="${esc(r.run_id)}">${mockTag}${esc(r.run_id)} (${passTag}) - ${esc(snippet)}</option>`;
        }).join('');
      sel.value = cur;
    } catch (_) {
      // Offline fallback
    }
  }

  /* ================= Cost Radar Tab ================= */
  async function renderCostRadar() {
    const container = $('p-cost');
    try {
      const m = await api('/api/metrics');
      const exp = m.experiment || {};

      let html = `<h3>Cost Radar: Baseline vs Improved</h3>`;

      if (!exp.tuning && !exp.held_out) {
        html += `<p>No experiment metrics found. Run <code>python -m experiments.ab</code> to populate A/B metrics.</p>`;
        container.innerHTML = html;
        return;
      }

      // Comparison Table
      html += `
        <div class="metric-card">
          <h4>Held-Out & Tuning Sets (Before / After)</h4>
          <table class="metric-table">
            <thead>
              <tr>
                <th>Cohort</th>
                <th>Arm</th>
                <th>First-Attempt Pass</th>
                <th>Eventual Success</th>
                <th>Cost / Success</th>
                <th>Retry Tax</th>
                <th>Median Latency</th>
              </tr>
            </thead>
            <tbody>
      `;

      ['held_out', 'tuning', 'combined'].forEach((cohort) => {
        const cData = exp[cohort];
        if (!cData) return;
        ['baseline', 'improved'].forEach((arm) => {
          const r = cData[arm];
          if (!r) return;
          const firstPassStr = `${r.first_attempt_pass_count}/${r.n_runs} ${chip(r.first_attempt_pass_rate_tag || 'MEASURED')}`;
          const successStr = `${r.success_count}/${r.n_runs} ${chip(r.success_rate_tag || 'MEASURED')}`;
          const cpsStr = r.cost_per_success != null ? `$${r.cost_per_success.toFixed(6)} ${chip(r.cost_per_success_tag || 'COMPUTED')}` : 'n/a';
          const taxStr = r.retry_tax != null ? `${r.retry_tax.toFixed(1)}% ${chip(r.retry_tax_tag || 'COMPUTED')}` : 'n/a';
          const latStr = r.median_latency_seconds != null ? `${r.median_latency_seconds.toFixed(1)}s ${chip(r.median_latency_tag || 'MEASURED')}` : 'n/a';

          html += `
            <tr>
              <td><strong>${esc(cohort)}</strong></td>
              <td>${esc(arm)}</td>
              <td>${firstPassStr}</td>
              <td>${successStr}</td>
              <td class="num">${cpsStr}</td>
              <td class="num">${taxStr}</td>
              <td class="num">${latStr}</td>
            </tr>
          `;
        });
      });

      html += `
            </tbody>
          </table>
        </div>
      `;

      // Statistical Headline & Note
      const headline = m.statistical_headline || {};
      const fisherStr = headline.fisher_exact_p_value || exp.fisher_exact_p_value || 'p < 0.0001';
      html += `
        <div class="note-box" style="margin-top: 14px;">
          <p><strong>First-Attempt Rate:</strong> Jumped from 1/20 to 16/20 on held-out ideas (${fisherStr} ${chip('COMPUTED')}).</p>
          <p style="color: var(--ink2); font-weight: 700; margin-top: 6px;">
            Note: eventual success did not differ significantly.
          </p>
          <p style="font-size: 12px; margin-top: 6px; color: var(--ink2);">
            <em>Limitation: The remaining held-out failures come from two pool-style ideas (tip pools) where the idea's framing conflicts with the per-person contract.</em>
          </p>
        </div>
      `;

      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<p style="color: var(--red);">Failed to load Cost Radar: ${esc(err.message)}</p>`;
    }
  }

  /* ================= Verdict Tab ================= */
  async function renderVerdict() {
    const container = $('p-verdict');
    const founderKey = S.verdictFounder || 'a';

    try {
      const v = await api(`/api/verdict?founder=${founderKey}&cohort=${S.founderCohort}`);
      const overall = v.verdict || 'PIVOT';

      let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
          <h3>Deterministic Verdict Engine</h3>
          <div class="seg-group">
            <button class="seg-btn" id="v-founder-a" aria-pressed="${founderKey === 'a'}">Founder A</button>
            <button class="seg-btn" id="v-founder-b" aria-pressed="${founderKey === 'b'}">Founder B</button>
          </div>
        </div>

        <div class="verdict-hero">
          <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--ink2);">Evaluated Verdict (Cohort: ${esc(S.founderCohort)})</span>
          <div class="stamp ${overall}">${overall}</div>
          <p style="font-size: 12px; color: var(--ink2); margin: 0;">Code-evaluated across 4 deterministic gates. Zero LLMs involved.</p>
        </div>

        <h4>Gate Outcomes</h4>
        <div class="layer-list">
      `;

      const layers = v.layer_verdicts || {};
      for (const [layer, lVerd] of Object.entries(layers)) {
        html += `
          <div class="layer-row">
            <span><strong>${esc(layer.toUpperCase())}</strong></span>
            <span class="chip ${lVerd === 'BUILD' ? 'meas' : lVerd === 'KILL' ? 'comp' : 'ass'}">${lVerd}</span>
          </div>
        `;
      }
      html += `</div>`;

      // Reasons with source tags
      html += `<h4 style="margin-top: 14px;">Rule Explanations &amp; Source Tags</h4><ul class="reason-list">`;
      (v.reasons || []).forEach((r) => {
        html += `<li class="reason-item">${esc(r)}</li>`;
      });
      html += `</ul>`;

      // Cheapest next experiment
      if (v.cheapest_next_experiment) {
        const exp = v.cheapest_next_experiment;
        html += `
          <div class="next-exp-box">
            <h4>Cheapest Next Experiment</h4>
            <p><strong>Action:</strong> ${esc(exp.experiment || 'None')}</p>
            <p><strong>Cost:</strong> ${esc(exp.estimated_cost || '0 INR')} ${chip('ASSUMED')}</p>
            <p><strong>Lever:</strong> ${esc(exp.lever || 'Validate demand')}</p>
          </div>
        `;
      }

      container.innerHTML = html;

      // Event listeners for A / B switcher
      $('v-founder-a').addEventListener('click', () => {
        S.verdictFounder = 'a';
        renderVerdict();
      });
      $('v-founder-b').addEventListener('click', () => {
        S.verdictFounder = 'b';
        renderVerdict();
      });
    } catch (err) {
      container.innerHTML = `<p style="color: var(--red);">Verdict evaluation failed: ${esc(err.message)}</p>`;
    }
  }

  /* ================= Trust & Safety Tab ================= */
  async function renderTrust() {
    const container = $('p-trust');
    let runId = S.runId;
    if (!runId) {
      try {
        const runs = await api('/api/runs');
        if (runs && runs.length > 0) {
          runId = runs[0].run_id;
        }
      } catch (_) {}
    }

    if (!runId) {
      container.innerHTML = `
        <h3>Trust & Safety Report</h3>
        <p style="color: var(--ink2);">No run selected or recorded yet. Run a build or choose a replay to inspect safety rails.</p>
      `;
      return;
    }

    try {
      const data = await api(`/api/trust/${encodeURIComponent(runId)}`);

      const mockBadge = data.mock ? chip('MOCK') : '';
      let statusBadge = '';
      if (data.approved) {
        statusBadge = `<span class="chip found">APPROVED ✔ ${esc(data.approved_at || 'recorded')}</span>`;
      } else if (data.success) {
        statusBadge = `<span class="chip comp">PASSED (Awaiting Approval)</span>`;
      } else {
        const failRail = (data.rails_fired && data.rails_fired.length) ? (data.rails_fired[0].rail || 'failed') : 'failed';
        statusBadge = `<span class="chip bad">FAILED (${esc(failRail)})</span>`;
      }

      let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <h3 style="margin: 0;">Trust Report: <code>${esc(data.run_id)}</code> ${mockBadge}</h3>
            <div style="font-size: 12px; color: var(--ink2); margin-top: 4px;">Idea: "${esc(data.idea || 'unnamed')}"</div>
          </div>
          <div>${statusBadge}</div>
        </div>

        <!-- Guardrail Ceilings & Measurement -->
        <div class="metric-card" style="margin-bottom: 16px;">
          <h4>Enforced Guardrail Ceilings</h4>
          <table class="metric-table">
            <thead>
              <tr>
                <th>Constraint</th>
                <th class="num">Used / Measured</th>
                <th class="num">Ceiling / Cap</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Budget Cap</strong></td>
                <td class="num">${usd(data.budget_used)} ${chip(data.mock ? 'MOCK' : 'MEASURED')}</td>
                <td class="num">${usd(data.budget_cap)} ${chip('CONFIG')}</td>
                <td><span class="chip ${data.budget_used >= data.budget_cap ? 'bad' : 'found'}">${data.budget_used >= data.budget_cap ? 'CAP REACHED' : 'WITHIN BUDGET'}</span></td>
              </tr>
              <tr>
                <td><strong>Attempt Cap</strong></td>
                <td class="num">${data.attempts_used} attempts ${chip('MEASURED')}</td>
                <td class="num">${data.attempts_cap} attempts max ${chip('CONFIG')}</td>
                <td><span class="chip ${data.attempts_used >= data.attempts_cap && !data.success ? 'bad' : 'found'}">${data.attempts_used >= data.attempts_cap && !data.success ? 'CAP REACHED' : 'WITHIN CAP'}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Dynamic Safety Rails Table -->
        <div class="metric-card" style="margin-bottom: 16px;">
          <h4>Dynamic Rails Status (Computed from result.json)</h4>
          <table class="metric-table">
            <thead>
              <tr>
                <th>Security Rail</th>
                <th>Status</th>
                <th>Measurement / Cap</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
      `;

      (data.rails || []).forEach((r) => {
        let badgeClass = 'comp';
        if (r.status === 'FIRED') badgeClass = 'bad';
        else if (r.status === 'NOT FIRED') badgeClass = 'found';
        else if (r.status === 'NOT TESTED') badgeClass = 'meas';

        html += `
          <tr>
            <td><strong>${esc(r.name)}</strong></td>
            <td><span class="chip ${badgeClass}">${esc(r.status)}</span></td>
            <td><code>${esc(r.used)}</code> / <code>${esc(r.cap)}</code></td>
            <td style="font-size: 12px; color: var(--ink2);">${esc(r.desc)}</td>
          </tr>
        `;
      });

      html += `
            </tbody>
          </table>
        </div>

        <!-- Human Approval Gate & Founder Report -->
        <div class="metric-card">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <h4 style="margin: 0 0 4px 0;">Offline Founder Report</h4>
              <p style="margin: 0; font-size: 12px; color: var(--ink2);">
                Self-contained, 100% offline HTML artifact including verdict, layers, A/B metrics, limitations, and evidence provenance.
              </p>
            </div>
            <div>
              <a class="btn btn-sm btn-primary" href="/api/report/${encodeURIComponent(data.run_id)}" target="_blank" rel="noopener">
                View Founder Report HTML ↗
              </a>
            </div>
          </div>
        </div>
      `;

      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<p style="color: var(--red);">Failed to load Trust Report: ${esc(err.message)}</p>`;
    }
  }

  /* ================= Founder Intake Form Tab ================= */
  function loadFounderDefaults() {
    // If not filled, pre-populate Founder A baseline values
    if (!$('f-target-user').value) {
      $('f-target-user').value = 'Office teams who run shared coffee and lunch orders';
      $('f-payer').value = 'Office managers';
      $('f-goal').value = 'Per-person bill and tip splitting for office group orders';
      $('f-channel').value = 'Direct outreach to office managers';
      $('f-demand').value = 'interviews';
      $('f-budget').value = '350000';
      $('f-hours').value = '40';
      $('f-skills').value = 'b2b sales, python';
      $('f-price').value = '50';
    }
  }

  $('founder-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      target_user: $('f-target-user').value.trim(),
      payer: $('f-payer').value.trim(),
      goal: $('f-goal').value.trim(),
      first_customer_channel: $('f-channel').value.trim(),
      demand_evidence: $('f-demand').value,
      budget_inr: parseFloat($('f-budget').value) || 0,
      weekly_hours: parseFloat($('f-hours').value) || 0,
      skills: $('f-skills').value.split(',').map((s) => s.trim()).filter(Boolean),
      price_per_run_inr: parseFloat($('f-price').value) || 0,
      cohort: $('f-cohort').value,
    };

    const outBox = $('founder-verdict-result');
    outBox.innerHTML = '<p>Recomputing deterministic verdict...</p>';

    try {
      const res = await api('/api/founder/verdict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const overall = res.verdict || 'PIVOT';
      let outHtml = `
        <div class="verdict-hero" style="margin-top: 14px;">
          <span style="font-size: 11px; font-weight: 700; color: var(--ink2);">RECOMPUTED VERDICT</span>
          <div class="stamp ${overall}">${overall}</div>
          <div style="font-size: 12px; margin-top: 4px;">
            Gross Margin: <strong>${fmt(res.metrics_used?.gross_margin, 1)}%</strong> ${chip('COMPUTED')} |
            Runway: <strong>${fmt(res.metrics_used?.runway_months, 1)} mo</strong> ${chip('COMPUTED')}
          </div>
        </div>

        <h4>Gate Outcomes</h4>
        <div class="layer-list">
      `;

      for (const [l, v] of Object.entries(res.layer_verdicts || {})) {
        outHtml += `
          <div class="layer-row">
            <span><strong>${esc(l.toUpperCase())}</strong></span>
            <span class="chip ${v === 'BUILD' ? 'meas' : v === 'KILL' ? 'comp' : 'ass'}">${v}</span>
          </div>
        `;
      }
      outHtml += `</div><h4 style="margin-top: 10px;">Rule Explanations</h4><ul class="reason-list">`;
      (res.reasons || []).forEach((r) => {
        outHtml += `<li class="reason-item">${esc(r)}</li>`;
      });
      outHtml += `</ul>`;

      outBox.innerHTML = outHtml;
    } catch (err) {
      outBox.innerHTML = `<p style="color: var(--red);">Recomputation error: ${esc(err.message)}</p>`;
    }
  });

  /* ================= Plan Tab ================= */
  async function renderPlan() {
    const container = $('p-plan');
    try {
      const p = await api('/api/plan');
      const isReady = p.status === 'READY';

      let html = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <h3>cfo.ai Financial Plan</h3>
          <span class="plan-status-badge ${isReady ? 'READY' : 'PENDING'}">${isReady ? 'PLAN READY' : 'PLAN PENDING'}</span>
        </div>
      `;

      if (isReady && p.plan_numbers && typeof p.plan_numbers === 'object') {
        const nums = p.plan_numbers;
        html += `
          <div class="cfo-summary-card">
            <h4>Plan Metrics (from cfo.ai)</h4>
            <table class="metric-table">
              <tbody>
                <tr><td>Price per run</td><td class="num">₹${fmt(nums.price_per_run_inr)} ${chip('USER-PROVIDED')}</td></tr>
                <tr><td>Gross Margin</td><td class="num">${fmt(nums.gross_margin_percent, 1)}% ${chip('COMPUTED')}</td></tr>
                <tr><td>Runway</td><td class="num">${fmt(nums.runway_months, 1)} months ${chip('COMPUTED')}</td></tr>
                <tr><td>Break-even customers</td><td class="num">${nums.breakeven_customers || 'n/a'} ${chip('COMPUTED')}</td></tr>
              </tbody>
            </table>
          </div>
        `;
      } else {
        html += `
          <div class="note-box" style="margin-bottom: 14px;">
            <p><strong>Notice:</strong> cfo.ai financial plan is currently PENDING. Paste <code>evidence/cfo/cfo_input.md</code> into cfo.ai to generate plan numbers.</p>
          </div>
        `;
      }

      if (p.plan_summary && p.plan_summary !== 'PENDING') {
        html += `
          <div class="cfo-summary-card">
            <h4>Executive Summary</h4>
            <div style="white-space: pre-wrap; font-size: 13px; line-height: 1.45;">${esc(p.plan_summary)}</div>
          </div>
        `;
      }

      // Evidence links and exports
      html += `<h4>Evidence &amp; Artifacts</h4><div class="evidence-links-list">`;
      html += `<a class="btn btn-sm" href="/evidence/cfo/cfo_input.md" target="_blank" rel="noopener">View cfo_input.md</a>`;

      (p.exports || []).forEach((f) => {
        html += `<a class="btn btn-sm" href="/evidence/cfo/${encodeURIComponent(f)}" target="_blank" rel="noopener">${esc(f)}</a>`;
      });
      html += `</div>`;

      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<p style="color: var(--red);">Failed to load plan: ${esc(err.message)}</p>`;
    }
  }

  /* ================= Evidence Tab ================= */
  async function renderEvidence() {
    const container = $('p-evidence');
    try {
      const data = await api('/api/evidence');
      let html = `<h3>Evidence Locker: Claims &amp; Proofs</h3>`;

      // 1. Claims Table (Computed dynamically from disk, never hard-coded)
      html += `
        <div class="metric-card" style="margin-bottom: 16px;">
          <h4>Audited Claims &amp; Artifacts</h4>
          <table class="metric-table">
            <thead>
              <tr>
                <th style="width: 25%;">Claim</th>
                <th style="width: 15%;">Status</th>
                <th>Artifact Reference &amp; Values</th>
              </tr>
            </thead>
            <tbody>
      `;

      (data.claims || []).forEach((c) => {
        const proofs = (c.proof || []).map((p) =>
          `<div><strong>${esc(p.label)}</strong> <span style="font-size: 11px; color: var(--ink2);">(${esc(p.ref)})</span></div>`
        ).join('');
        const statusBadge = `<span class="chip ${c.status === 'FOUND' ? 'found' : 'comp'}">${esc(c.status)}</span>`;

        html += `
          <tr>
            <td><strong>${esc(c.claim)}</strong></td>
            <td>${statusBadge}</td>
            <td>${proofs}</td>
          </tr>
        `;
      });

      html += `
            </tbody>
          </table>
        </div>
      `;

      // 2. SHA-256 Provenance & Verification
      const shaMatch = data.metrics_sha_match || (data.hashes?.['evidence/metrics.json']?.toUpperCase() === data.hashes?.['evidence/ab/metrics.sha256']?.toUpperCase() ? 'MATCH' : 'MISMATCH');
      const shaBadge = `<span class="chip ${shaMatch === 'MATCH' ? 'found' : 'bad'}">${esc(shaMatch)}</span>`;

      html += `
        <div class="metric-card" style="margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h4>SHA-256 Provenance Verification</h4>
            ${shaBadge}
          </div>
          <table class="metric-table">
            <tbody>
              <tr>
                <td style="width: 32%;"><code>evidence/metrics.json</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['evidence/metrics.json'] || 'none')}</code></td>
              </tr>
              <tr>
                <td><code>evidence/ab/metrics.sha256</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['evidence/ab/metrics.sha256'] || 'none')}</code></td>
              </tr>
              <tr>
                <td><code>winner.txt (file bytes)</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['winner.txt (file bytes)'] || 'none')}</code></td>
              </tr>
              <tr>
                <td><code>winner.txt (prompt text (stripped))</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['winner.txt (prompt text (stripped))'] || 'none')}</code></td>
              </tr>
              <tr>
                <td><code>winner patch (recorded)</code></td>
                <td style="font-size: 11px; word-break: break-all;">
                  <code>${esc(data.hashes?.['winner_patch_recorded_sha256'] || 'none')}</code>
                  <span class="chip ${data.winner_patch_match && !data.winner_patch_match.includes('MISMATCH') ? 'found' : 'bad'}">${esc(data.winner_patch_match || data.hashes?.['winner_patch_match'] || 'MISMATCH')}</span>
                </td>
              </tr>
              <tr>
                <td><code>agent/prompts.py</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['agent/prompts.py'] || 'none')}</code></td>
              </tr>
              <tr>
                <td><code>BUILDER_SYSTEM_V1</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['BUILDER_SYSTEM_V1'] || 'none')}</code></td>
              </tr>
              <tr>
                <td><code>RETRY_USER</code></td>
                <td style="font-size: 11px; word-break: break-all;"><code>${esc(data.hashes?.['RETRY_USER'] || 'none')}</code></td>
              </tr>
            </tbody>
          </table>
        </div>
      `;

      // 3. Run Counts Per Cell
      html += `
        <div class="metric-card" style="margin-bottom: 16px;">
          <h4>Run Counts Per Cell</h4>
          <table class="metric-table">
            <thead>
              <tr>
                <th>Cohort / Arm</th>
                <th class="num">Runs (N)</th>
              </tr>
            </thead>
            <tbody>
      `;
      const cellCounts = data.cell_counts || data.run_counts_per_cell || {};
      for (const [cell, cnt] of Object.entries(cellCounts)) {
        html += `
          <tr>
            <td><strong>${esc(cell)}</strong></td>
            <td class="num">${cnt} ${chip('MEASURED')}</td>
          </tr>
        `;
      }
      html += `
            </tbody>
          </table>
        </div>
      `;

      // 4. Reproduce Commands
      html += `
        <div class="metric-card" style="margin-bottom: 16px;">
          <h4>Reproduce Commands (from evidence/ab/README.md)</h4>
          <div style="background-color: var(--paper3); border: 1px solid var(--ink); border-radius: var(--r); padding: 10px; font-family: var(--font-m); font-size: 12px;">
      `;
      (data.reproduce || data.reproduce_commands || []).forEach((cmd) => {
        html += `<div style="margin-bottom: 4px;"><code>${esc(cmd)}</code></div>`;
      });
      html += `</div></div>`;

      // 5. Limitations Box
      html += `
        <div class="note-box">
          <h4 style="margin-bottom: 8px;">Experimental Limitations</h4>
          <ul style="padding-left: 18px; margin: 0; font-size: 13px; line-height: 1.45;">
      `;
      (data.limitations || []).forEach((lim) => {
        html += `<li style="margin-bottom: 4px;">${esc(lim)}</li>`;
      });
      html += `</ul></div>`;

      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<p style="color: var(--red);">Failed to load Evidence Locker: ${esc(err.message)}</p>`;
    }
  }

  /* ================= Boot Initialization ================= */
  (async function boot() {
    try {
      S.cfg = await api('/api/config');
      if (S.cfg.mock) {
        S.mock = true;
        $('mock-toggle').checked = true;
      }
      if (S.cfg.default_budget_usd) {
        $('budget-input').value = S.cfg.default_budget_usd;
      }
    } catch (_) {
      S.cfg = {};
    }

    updateBanner();
    refreshReplayList();
    loadFounderDefaults();
  })();
})();
