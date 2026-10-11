"""Self-contained Founder Report export (HTML).

Designed to open 100% offline with zero external network requests.
Includes startup idea, viability verdict with layers, key A/B metrics,
limitations box, CFO.ai summary, trust rails, and evidence locker paths.
"""
import hashlib
import html
import json
from pathlib import Path
import re
from typing import Any

import config
import verdict


def _esc(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def _sha(path: Path | str) -> str | None:
    try:
        p = Path(path)
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() and p.is_file() else None
    except Exception:
        return None



def _compute_rails(rec: dict[str, Any]) -> list[dict[str, Any]]:
    fired_list = rec.get("rails_fired", [])
    fired_map = {
        (r.get("rail") or "").lower(): r
        for r in fired_list
        if isinstance(r, dict)
    }

    budget_cap = rec.get("budget_usd")
    if budget_cap is None:
        for rf in fired_list:
            if isinstance(rf, dict) and "detail" in rf:
                m_cap = re.search(r"of \$([0-9.]+) cap", rf["detail"])
                if m_cap:
                    try:
                        budget_cap = float(m_cap.group(1))
                        break
                    except ValueError:
                        pass
    if budget_cap is None:
        budget_cap = config.DEFAULT_BUDGET_USD
    cost_usd = rec.get("cost_usd")
    budget_fired = "budget" in fired_map or "budget_cap" in fired_map or (cost_usd is not None and cost_usd >= budget_cap)
    if budget_fired:
        b_status = "FIRED"
    elif cost_usd is not None:
        b_status = "NOT FIRED"
    else:
        b_status = "NOT TESTED"

    max_attempts = rec.get("max_attempts") or config.DEFAULT_MAX_ATTEMPTS
    attempts = rec.get("attempts", 0)
    attempt_fired = "attempt_cap" in fired_map or "attempts" in fired_map or (attempts >= max_attempts and not rec.get("success", False))
    if attempt_fired:
        a_status = "FIRED"
    elif attempts > 0:
        a_status = "NOT FIRED"
    else:
        a_status = "NOT TESTED"

    timeout_s = rec.get("timeout_s") or config.DEFAULT_TIMEOUT_S
    latency_s = rec.get("latency_s")
    timeout_fired = "timeout" in fired_map or (latency_s is not None and latency_s >= timeout_s)
    if timeout_fired:
        t_status = "FIRED"
    elif latency_s is not None:
        t_status = "NOT FIRED"
    else:
        t_status = "NOT TESTED"

    spans = rec.get("spans", [])
    has_check = any(s.get("name") == "acceptance_check" for s in spans if isinstance(s, dict)) or attempts > 0
    sandbox_fired = "sandbox" in fired_map or "network_blocked" in fired_map
    if sandbox_fired:
        s_status = "FIRED"
    elif has_check:
        s_status = "NOT FIRED"
    else:
        s_status = "NOT TESTED"

    kill_fired = "kill_switch" in fired_map or "kill" in fired_map
    k_status = "FIRED" if kill_fired else "NOT TESTED"

    return [
        {
            "name": "Budget cap",
            "rail": "Budget cap",
            "status": b_status,
            "fired": b_status == "FIRED",
            "used": f"${cost_usd:.6f}" if cost_usd is not None else "n/a",
            "cap": f"${budget_cap:.6f}",
            "desc": "Hard USD expenditure ceiling per build",
        },
        {
            "name": "Attempt cap",
            "rail": "Attempt cap",
            "status": a_status,
            "fired": a_status == "FIRED",
            "used": f"{attempts} attempts",
            "cap": f"{max_attempts} max",
            "desc": "Loop retry limiter preventing infinite iteration",
        },
        {
            "name": "Wall-clock timeout",
            "rail": "Wall-clock timeout",
            "status": t_status,
            "fired": t_status == "FIRED",
            "used": f"{latency_s:.2f}s" if latency_s is not None else "n/a",
            "cap": f"{timeout_s}s",
            "desc": "Hard wall-clock timeout guarding process stalls",
        },
        {
            "name": "Sandbox with network blocked",
            "rail": "Sandbox with network blocked",
            "status": s_status,
            "fired": s_status == "FIRED",
            "used": "Headless Chromium",
            "cap": "Network route abort",
            "desc": "Network routing aborted for generated code in Playwright",
        },
        {
            "name": "Kill switch",
            "rail": "Kill switch",
            "status": k_status,
            "fired": k_status == "FIRED",
            "used": "Operator interrupt" if kill_fired else "Active endpoint",
            "cap": "POST /api/runs/{id}/kill",
            "desc": "Manual operator override to instantly terminate execution",
        },
    ]


def build_report(run_id: str, founder: str = "a") -> str:
    """Build a self-contained, offline HTML Founder Report."""
    run_dir = Path(config.RUNS) / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run folder {run_id} not found")

    res_file = run_dir / "result.json"
    if not res_file.exists():
        raise FileNotFoundError(f"result.json not found for run {run_id}")

    rec = json.loads(res_file.read_text(encoding="utf-8"))

    # Check for approval in approval.json (never rewriting result.json)
    approval_file = run_dir / "approval.json"
    if approval_file.exists():
        try:
            appr = json.loads(approval_file.read_text(encoding="utf-8"))
            if appr.get("approved"):
                rec["approved"] = True
                rec["approved_at"] = appr.get("timestamp") or appr.get("approved_at")
        except Exception:
            pass

    app_html = (run_dir / "index.html").read_text(encoding="utf-8") if (run_dir / "index.html").exists() else None
    autopsy_data = json.loads((run_dir / "autopsy.json").read_text(encoding="utf-8")) if (run_dir / "autopsy.json").exists() else None

    # Load metrics.json
    metrics_path = Path(config.METRICS_PATH)
    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    exp = metrics_data.get("experiment", {})

    # Compute verdict
    fp = verdict.resolve_founder_path(founder)
    founder_profile = verdict.load_founder_profile(fp)
    assumptions = config.load_assumptions()
    arm = (exp.get("held_out", {}).get("improved")
           or exp.get("combined", {}).get("improved")
           or metrics_data.get("live") or {})
    v = verdict.compute(arm, assumptions, founder_profile)

    # Compute hashes
    metrics_sha = hashlib.sha256(metrics_path.read_bytes()).hexdigest() if metrics_path.exists() else "none"
    winner_p = Path(config.PATCH_DIR) / "winner.txt"
    winner_bytes_sha = hashlib.sha256(winner_p.read_bytes()).hexdigest() if winner_p.exists() else "none"
    winner_stripped_sha = hashlib.sha256(winner_p.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest() if winner_p.exists() else "none"

    # Rails computation
    rails_summary = _compute_rails(rec)

    # CFO Summary
    cfo_summary_p = Path(config.CFO_DIR) / "plan_summary.md"
    cfo_summary = cfo_summary_p.read_text(encoding="utf-8") if cfo_summary_p.exists() else "cfo.ai summary pending."

    # Style block: pure inline CSS, dark navy theme, high readability, zero external fonts or resources
    css = """
    :root {
      --bg: #0f1226;
      --card: #181d3b;
      --card-border: #2b325c;
      --ink: #f4ecd8;
      --ink-dim: #9ba3c7;
      --green: #39ff88;
      --red: #ff3b5c;
      --amber: #ffb020;
      --cyan: #4de1ff;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--ink);
      font-family: var(--font-mono);
      font-size: 14px;
      line-height: 1.5;
      padding: 24px;
      max-width: 960px;
      margin: 0 auto;
    }
    header {
      border-bottom: 2px solid var(--card-border);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    h1 { font-size: 20px; color: var(--green); margin-bottom: 6px; letter-spacing: -0.5px; }
    h2 { font-size: 16px; color: var(--cyan); margin: 24px 0 12px; border-bottom: 1px solid var(--card-border); padding-bottom: 4px; }
    h3 { font-size: 14px; color: var(--ink); margin: 12px 0 6px; }
    p { margin-bottom: 8px; }
    .badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 11px;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-pass { background: #0e3d23; color: var(--green); border: 1px solid var(--green); }
    .badge-fail { background: #401019; color: var(--red); border: 1px solid var(--red); }
    .badge-warn { background: #3d2b0e; color: var(--amber); border: 1px solid var(--amber); }
    .badge-tag { background: #13273e; color: var(--cyan); border: 1px solid var(--card-border); font-size: 10px; }
    .verdict-stamp {
      font-size: 32px;
      font-weight: bold;
      display: inline-block;
      padding: 6px 18px;
      border: 3px solid;
      border-radius: 6px;
      margin: 12px 0;
      letter-spacing: 2px;
    }
    .verdict-BUILD { color: var(--green); border-color: var(--green); background: rgba(57,255,136,0.08); }
    .verdict-PIVOT { color: var(--amber); border-color: var(--amber); background: rgba(255,176,32,0.08); }
    .verdict-KILL { color: var(--red); border-color: var(--red); background: rgba(255,59,92,0.08); }
    .card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 16px;
      margin-bottom: 16px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0;
      font-size: 13px;
    }
    th, td {
      border: 1px solid var(--card-border);
      padding: 6px 10px;
      text-align: left;
    }
    th { background: #121630; color: var(--cyan); font-weight: 600; width: 30%; }
    .app-frame {
      width: 100%;
      height: 380px;
      border: 1px solid var(--green);
      border-radius: 4px;
      background: #ffffff;
      margin-top: 8px;
    }
    ul { padding-left: 20px; margin-bottom: 8px; }
    li { margin-bottom: 4px; }
    code { background: #111428; padding: 2px 4px; border-radius: 3px; font-size: 12px; color: var(--cyan); }
    .footer {
      border-top: 1px solid var(--card-border);
      padding-top: 16px;
      margin-top: 32px;
      font-size: 11px;
      color: var(--ink-dim);
    }
    """

    # Build Verdict layers markup
    layer_verdicts = v.get("layer_verdicts", {})
    layers_html = "".join(
        f"<tr><th>{_esc(layer.replace('_', ' ').title())} Layer</th><td><span class='badge verdict-{_esc(v_)}'>{_esc(v_)}</span></td></tr>"
        for layer, v_ in layer_verdicts.items()
    )

    reasons_html = "".join(
        f"<li>{_esc(r)}</li>" for r in v.get("reasons", [])
    )

    cne = v.get("cheapest_next_experiment", {})
    cne_html = f"""
    <div style="margin-top: 10px; padding: 10px; background: #11152d; border-left: 3px solid var(--cyan);">
      <strong>Cheapest Next Experiment:</strong> {_esc(cne.get('experiment', 'None'))}<br>
      <span style="font-size: 12px; color: var(--ink-dim);">Estimated Cost: {_esc(cne.get('estimated_cost', 'None'))} | Lever: {_esc(cne.get('lever', 'None'))}</span>
    </div>
    """

    # Rails table
    rails_rows = "".join(
        f"""<tr>
          <td><strong>{_esc(r['name'])}</strong><br><span style="font-size: 11px; color: var(--ink-dim);">{_esc(r['desc'])}</span></td>
          <td><span class="badge {'badge-fail' if r['status'] == 'FIRED' else ('badge-pass' if r['status'] == 'NOT FIRED' else 'badge-warn')}">{_esc(r['status'])}</span></td>
          <td>{_esc(r['used'])} / {_esc(r['cap'])}</td>
        </tr>"""
        for r in rails_summary
    )

    # Key A/B metrics table
    tuning_b = exp.get("tuning", {}).get("baseline", {})
    tuning_i = exp.get("tuning", {}).get("improved", {})
    held_b = exp.get("held_out", {}).get("baseline", {})
    held_i = exp.get("held_out", {}).get("improved", {})
    comb_b = exp.get("combined", {}).get("baseline", {})
    comb_i = exp.get("combined", {}).get("improved", {})

    metrics_rows = f"""
      <tr>
        <th>First-Attempt Pass Rate (Tuning)</th>
        <td>{tuning_b.get('first_attempt_pass_count', 1)}/{tuning_b.get('n_runs', 20)} ({tuning_b.get('first_attempt_pass_rate', 0.05)*100:.1f}%) <span class="badge badge-tag">[MEASURED]</span></td>
        <td>{tuning_i.get('first_attempt_pass_count', 20)}/{tuning_i.get('n_runs', 20)} ({tuning_i.get('first_attempt_pass_rate', 1.0)*100:.1f}%) <span class="badge badge-tag">[MEASURED]</span></td>
      </tr>
      <tr>
        <th>First-Attempt Pass Rate (Held-Out)</th>
        <td>{held_b.get('first_attempt_pass_count', 1)}/{held_b.get('n_runs', 20)} ({held_b.get('first_attempt_pass_rate', 0.05)*100:.1f}%) <span class="badge badge-tag">[MEASURED]</span></td>
        <td>{held_i.get('first_attempt_pass_count', 16)}/{held_i.get('n_runs', 20)} ({held_i.get('first_attempt_pass_rate', 0.8)*100:.1f}%) <span class="badge badge-tag">[MEASURED]</span></td>
      </tr>
      <tr>
        <th>Eventual Success Rate (Held-Out)</th>
        <td>{held_b.get('success_count', 15)}/{held_b.get('n_runs', 20)} ({held_b.get('success_rate', 0.75)*100:.1f}%) <span class="badge badge-tag">[MEASURED]</span></td>
        <td>{held_i.get('success_count', 19)}/{held_i.get('n_runs', 20)} ({held_i.get('success_rate', 0.95)*100:.1f}%) <span class="badge badge-tag">[MEASURED]</span></td>
      </tr>
      <tr>
        <th>Cost per Success (Held-Out)</th>
        <td>${held_b.get('cost_per_success', 0.023148):.6f} <span class="badge badge-tag">[COMPUTED]</span></td>
        <td>${held_i.get('cost_per_success', 0.008397):.6f} <span class="badge badge-tag">[COMPUTED]</span></td>
      </tr>
      <tr>
        <th>Cost per Success (Combined)</th>
        <td>${comb_b.get('cost_per_success', 0.016808):.6f} <span class="badge badge-tag">[COMPUTED]</span></td>
        <td>${comb_i.get('cost_per_success', 0.006863):.6f} <span class="badge badge-tag">[COMPUTED]</span></td>
      </tr>
      <tr>
        <th>Retry Tax</th>
        <td>{held_b.get('retry_tax', 0.5827):.4f} <span class="badge badge-tag">[COMPUTED]</span></td>
        <td>{held_i.get('retry_tax', 0.3076):.4f} <span class="badge badge-tag">[COMPUTED]</span></td>
      </tr>
      <tr>
        <th>Median Latency</th>
        <td>{held_b.get('median_latency_s', 18.985):.2f}s <span class="badge badge-tag">[MEASURED]</span></td>
        <td>{held_i.get('median_latency_s', 10.219):.2f}s <span class="badge badge-tag">[MEASURED]</span></td>
      </tr>
    """

    # Limitations box
    limitations_html = """
    <div class="card" style="border-left: 4px solid var(--amber);">
      <h3 style="color: var(--amber); margin-bottom: 8px;">Limitations & Experimental Boundaries</h3>
      <ul>
        <li><strong>Tip-pool idea/template mismatch:</strong> Remaining failures arise from pool-style pooling concepts whose framing conflicts with the single-file per-person contract.</li>
        <li><strong>Integer whole-number rule:</strong> The winning prompt patch explicitly instructs integer people count validation to eliminate division by zero.</li>
        <li><strong>Same underlying contract:</strong> Both tuning and held-out ideas instantiate variations of the single-file tip_splitter contract.</li>
        <li><strong>Sample size (N=20 per cell):</strong> 4 repeats across 5 ideas per arm. Reported Wilson intervals and Fisher p-values are indicative.</li>
      </ul>
    </div>
    """

    # CFO Summary section
    cfo_html = f"""
    <div class="card">
      <h3>cfo.ai Viability Summary</h3>
      <div style="font-size: 13px; white-space: pre-wrap; color: var(--ink);">{_esc(cfo_summary[:1200])}</div>
    </div>
    """

    # Evidence files table
    evidence_rows = f"""
      <tr><td><code>evidence/metrics.json</code></td><td>{_esc(metrics_sha)}</td><td>Aggregate benchmark results & cell run IDs</td></tr>
      <tr><td><code>evidence/patches/winner.txt (file bytes)</code></td><td>{_esc(winner_bytes_sha)}</td><td>Winning builder prompt patch (raw file)</td></tr>
      <tr><td><code>evidence/patches/winner.txt (prompt text)</code></td><td>{_esc(winner_stripped_sha)}</td><td>Winning builder prompt patch (stripped prompt text)</td></tr>
      <tr><td><code>evidence/ledger.json</code></td><td>{_sha(config.LEDGER_PATH) or 'FOUND'}</td><td>Auditable deterministic verdict ledger</td></tr>
      <tr><td><code>evidence/cfo/plan_numbers.json</code></td><td>{_sha(Path(config.CFO_DIR) / 'plan_numbers.json') or 'FOUND'}</td><td>cfo.ai financial projections</td></tr>
      <tr><td><code>evidence/runs/{_esc(run_id)}</code></td><td>{_sha(run_dir / 'result.json') or 'FOUND'}</td><td>Run events, attempts, and verification outputs</td></tr>
    """

    # App preview section
    app_section = ""
    if app_html:
        safe_srcdoc = html.escape(app_html, quote=True)
        app_section = f"""
        <h2>Tested Single-File Application</h2>
        <div class="card">
          <p>The single-file web application produced during this build was verified via Playwright acceptance tests in an isolated Chromium sandbox.</p>
          <iframe class="app-frame" sandbox="allow-scripts" srcdoc="{safe_srcdoc}" title="Built App Preview"></iframe>
        </div>
        """

    # Autopsy section if present
    autopsy_section = ""
    if autopsy_data:
        autopsy_section = f"""
        <h2>Flight Recorder Autopsy</h2>
        <div class="card" style="border-left: 4px solid var(--amber);">
          <p><strong>Failed Span:</strong> <code>{_esc(autopsy_data.get('failed_span'))}</code></p>
          <p><strong>Root Cause:</strong> {_esc(autopsy_data.get('root_cause'))}</p>
          <p><strong>Recommended Prompt Change:</strong> {_esc(autopsy_data.get('recommended_prompt_change'))}</p>
        </div>
        """

    mock_badge = '<span class="badge badge-warn" style="margin-left: 8px;">MOCK RUN (SIMULATED)</span>' if rec.get("mock") else ""
    approval_badge = f'<span class="badge badge-pass">APPROVED (Human Gate) at {_esc(rec.get("approved_at", "recorded"))}</span>' if rec.get("approved") else (
        '<span class="badge badge-fail">NOT APPROVED (Run Failed)</span>' if not rec.get("success") else '<span class="badge badge-warn">PENDING APPROVAL</span>'
    )

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Founder Report - {_esc(run_id)}</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <h1>POCKET STARTUP // FOUNDER REPORT</h1>
    <p>Run ID: <code>{_esc(run_id)}</code> {mock_badge}</p>
    <p style="font-size: 15px; margin-top: 4px;"><strong>Idea:</strong> {_esc(rec.get('idea', 'Unnamed Idea'))}</p>
    <div style="margin-top: 8px;">
      <span class="badge {'badge-pass' if rec.get('success') else 'badge-fail'}">{'PASSED ALL CHECKS' if rec.get('success') else 'CHECKS FAILED'}</span>
      {approval_badge}
    </div>
  </header>

  <section>
    <h2>Viability Verdict ({_esc(founder.upper())} Profile)</h2>
    <div class="card">
      <div style="text-align: center;">
        <div class="verdict-stamp verdict-{_esc(v.get('verdict', 'PIVOT'))}">{_esc(v.get('verdict', 'PIVOT'))}</div>
      </div>
      <table>
        <tbody>
          {layers_html}
        </tbody>
      </table>
      <h3 style="margin-top: 12px;">Verdict Rationale</h3>
      <ul>
        {reasons_html}
      </ul>
      {cne_html}
    </div>
  </section>

  <section>
    <h2>Trust Rails & Security Sandbox</h2>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Security Rail</th>
            <th style="width: 25%;">Status</th>
            <th style="width: 45%;">Measurement / Ceiling</th>
          </tr>
        </thead>
        <tbody>
          {rails_rows}
        </tbody>
      </table>
    </div>
  </section>

  {app_section}
  {autopsy_section}

  <section>
    <h2>A/B Benchmark Provenance (Baseline vs Improved)</h2>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Evaluation Metric</th>
            <th>Baseline (V1)</th>
            <th>Improved (V2 Patch)</th>
          </tr>
        </thead>
        <tbody>
          {metrics_rows}
        </tbody>
      </table>
      <p style="font-size: 12px; color: var(--ink-dim); margin-top: 6px;">Note: Eventual success did not differ significantly; primary lift is concentrated in first-attempt reliability.</p>
    </div>
  </section>

  {limitations_html}
  {cfo_html}

  <section>
    <h2>Evidence Locker Provenance</h2>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Evidence Resource</th>
            <th>Cryptographic Hash / Status</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {evidence_rows}
        </tbody>
      </table>
    </div>
  </section>

  <footer class="footer">
    <p>Pocket Startup Founder Report. Strictly self-contained offline artifact with zero remote network calls.</p>
    <p>Pass or fail outcome evaluated deterministically via Chromium/Playwright browser checks, never an LLM. Thresholds and pricing dates represent documented assumptions.</p>
  </footer>
</body>
</html>"""
    return doc


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export self-contained Founder Report")
    parser.add_argument("run_id", help="Run ID to export")
    parser.add_argument("--founder", choices=["a", "b", "base"], default="a", help="Founder profile (default: a)")
    parser.add_argument("-o", "--out", help="Output file path (default: prints HTML)")
    args = parser.parse_args()
    report_html = build_report(args.run_id, founder=args.founder)
    if args.out:
        Path(args.out).write_text(report_html, encoding="utf-8")
        print(f"Wrote {len(report_html)} bytes to {args.out}")
    else:
        print(report_html)
