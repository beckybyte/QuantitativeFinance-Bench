"""Finance-Bench results dashboard with visualizations.

Run:  python3 dashboard.py
Open: http://localhost:5050
"""

from __future__ import annotations

import json
import html as html_lib
from collections import defaultdict
from pathlib import Path

from flask import Flask, abort

app = Flask(__name__)
RESULTS_DIR = Path(__file__).parent / "results"
JOBS_DIR = Path(__file__).parent / "jobs"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _is_all_zero_run(results: list[dict], model: str) -> bool:
    model_results = [r for r in results if r.get("model") == model]
    if len(model_results) < 2:
        return False
    rewards = [r.get("reward", 0) for r in model_results if not r.get("error")]
    if not rewards:
        return True
    return all(r == 0.0 for r in rewards)


def load_all_results() -> list[dict]:
    """Load all valid results from results/ directory, filtering out all-zero runs."""
    all_results: list[dict] = []
    if not RESULTS_DIR.exists():
        return all_results

    for f in sorted(RESULTS_DIR.glob("run_*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        results = data.get("results", [])
        if not results:
            continue

        meta = data.get("meta", {})
        models_in_file = {r.get("model") for r in results}
        bad_models = {m for m in models_in_file if _is_all_zero_run(results, m)}

        for r in results:
            model = r.get("model")
            if model in bad_models:
                continue
            r["_file"] = f.name
            r["_meta"] = meta
            all_results.append(r)

    return all_results


def load_run_files() -> list[dict]:
    """Load run metadata for the logs view."""
    runs = []
    if not RESULTS_DIR.exists():
        return runs
    for f in sorted(RESULTS_DIR.glob("run_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        meta = data.get("meta", {})
        results = data.get("results", [])
        models_in_file = {r.get("model") for r in results}
        bad_models = {m for m in models_in_file if _is_all_zero_run(results, m)}
        n_valid = sum(1 for r in results
                      if r.get("model") not in bad_models
                      and not r.get("error") and r.get("reward") is not None)
        n_total = len(results)
        n_errors = sum(1 for r in results if r.get("error"))
        runs.append({
            "file": f.name,
            "meta": meta,
            "n_total": n_total,
            "n_valid": n_valid,
            "n_errors": n_errors,
            "n_invalid": sum(1 for r in results if r.get("model") in bad_models),
            "results": results,
        })
    return runs


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f1117; color: #e0e0e0; min-height: 100vh; }}
  a {{ color: #58a6ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .topbar {{ background: #161b22; border-bottom: 1px solid #30363d;
             padding: 14px 32px; display: flex; align-items: center; gap: 20px; }}
  .topbar h1 {{ font-size: 18px; font-weight: 600; color: #f0f6fc; }}
  .topbar a {{ color: #8b949e; font-size: 13px; }}
  .topbar a.active {{ color: #58a6ff; }}

  .container {{ max-width: 1400px; margin: 0 auto; padding: 32px 24px; }}
  h2 {{ font-size: 20px; font-weight: 600; color: #f0f6fc; margin-bottom: 20px; }}
  h3 {{ font-size: 15px; font-weight: 600; color: #f0f6fc; margin-bottom: 12px; }}
  .subtitle {{ color: #8b949e; font-size: 13px; margin-bottom: 20px; margin-top: -12px; }}

  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
           padding: 20px; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .stat-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  .stat-label {{ font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }}
  .stat-value {{ font-size: 28px; font-weight: 700; color: #f0f6fc; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 8px 12px; color: #8b949e; font-weight: 500;
        border-bottom: 1px solid #30363d; font-size: 11px; text-transform: uppercase;
        position: sticky; top: 0; background: #161b22; z-index: 1; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #21262d; vertical-align: middle; }}
  tr:hover td {{ background: #1c2128; }}
  .mono {{ font-family: 'SF Mono', Consolas, monospace; font-size: 12px; }}

  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px;
            font-size: 12px; font-weight: 600; }}
  .badge-pass {{ background: #1f4a2a; color: #3fb950; border: 1px solid #238636; }}
  .badge-fail {{ background: #4a1f1f; color: #f85149; border: 1px solid #da3633; }}
  .badge-warn {{ background: #3d2e00; color: #d29922; border: 1px solid #9e6a03; }}
  .badge-na   {{ background: #2a2a2a; color: #8b949e; border: 1px solid #444; }}

  .progress-bar {{ height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; }}
  .progress-fill {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}

  .heatmap-cell {{ display: inline-block; width: 100%; text-align: center; padding: 4px 0;
                   font-size: 11px; font-weight: 600; border-radius: 3px; }}

  pre {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
         padding: 16px; overflow-x: auto; font-size: 12px; line-height: 1.6;
         color: #e0e0e0; font-family: 'SF Mono', Consolas, monospace; white-space: pre-wrap; }}
  .section {{ margin-bottom: 40px; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="topbar">
  <h1>Finance-Bench</h1>
  <a href="/" {nav_home}>Overview</a>
  <a href="/leaderboard" {nav_leaderboard}>Leaderboard</a>
  <a href="/heatmap" {nav_heatmap}>Heatmap</a>
  <a href="/models" {nav_models}>Models</a>
  <a href="/tasks" {nav_tasks}>Tasks</a>
  <a href="/logs" {nav_logs}>Logs</a>
  <a href="/jobs" {nav_jobs}>Jobs</a>
  <a href="#" onclick="exportPage(); return false;" style="margin-left:auto;background:#238636;color:#fff;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:600">Export PNG</a>
</div>
<div class="container">
{body}
</div>
<script>
function exportPage() {{
  var btn = document.querySelector('.topbar a[onclick]');
  btn.textContent = 'Exporting...';
  html2canvas(document.querySelector('.container'), {{
    backgroundColor: '#0f1117',
    scale: 2,
    useCORS: true,
    logging: false,
  }}).then(function(canvas) {{
    var link = document.createElement('a');
    link.download = 'finance-bench-' + window.location.pathname.replace(/\\//g, '-').replace(/^-/, '') + '.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
    btn.textContent = 'Export PNG';
  }}).catch(function() {{ btn.textContent = 'Export PNG'; }});
}}
</script>
</body>
</html>"""


def render(title: str, body: str, active: str = "") -> str:
    navs = {}
    for key in ["home", "leaderboard", "heatmap", "models", "tasks", "logs", "jobs"]:
        navs[f"nav_{key}"] = 'class="active"' if key == active else ""
    return HTML_BASE.format(title=title, body=body, **navs)


def score_color(val: float) -> str:
    """Return a CSS background color for a reward value 0..1."""
    if val >= 0.9:
        return "#1f4a2a"
    elif val >= 0.7:
        return "#1a3a20"
    elif val >= 0.5:
        return "#3d2e00"
    elif val >= 0.3:
        return "#4a2a00"
    elif val > 0.0:
        return "#4a1f1f"
    else:
        return "#2a1515"


def score_text_color(val: float) -> str:
    if val >= 0.7:
        return "#3fb950"
    elif val >= 0.5:
        return "#d29922"
    else:
        return "#f85149"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    results = load_all_results()
    if not results:
        return render("Finance-Bench", '<p style="color:#8b949e;text-align:center;padding:60px">No results yet. Run: python3 benchmark.py</p>', "home")

    # Aggregate per model
    model_data = defaultdict(lambda: {"rewards": [], "costs": [], "tasks": set(), "rounds": defaultdict(int)})
    for r in results:
        model = r.get("model", "?")
        task = r.get("task", "?")
        if not r.get("error") and r.get("reward") is not None:
            model_data[model]["rewards"].append(r["reward"])
            model_data[model]["tasks"].add(task)
            model_data[model]["rounds"][task] += 1
        if r.get("cost_usd"):
            model_data[model]["costs"].append(r["cost_usd"])

    # Sort by mean reward descending
    leaderboard = []
    for model, d in model_data.items():
        mean = sum(d["rewards"]) / len(d["rewards"]) if d["rewards"] else 0
        cost = sum(d["costs"])
        n_tasks = len(d["tasks"])
        n_runs = len(d["rewards"])
        min_rounds = min(d["rounds"].values()) if d["rounds"] else 0
        leaderboard.append({
            "model": model, "mean": mean, "cost": cost,
            "n_tasks": n_tasks, "n_runs": n_runs, "min_rounds": min_rounds,
        })
    leaderboard.sort(key=lambda x: -x["mean"])

    # Stats
    n_models = len(leaderboard)
    n_tasks = len({r.get("task") for r in results})
    n_runs = len(results)
    total_cost = sum(r.get("cost_usd") or 0 for r in results)

    stats_html = f"""
    <div class="grid">
      <div class="stat-box"><div class="stat-label">Models</div><div class="stat-value">{n_models}</div></div>
      <div class="stat-box"><div class="stat-label">Tasks</div><div class="stat-value">{n_tasks}</div></div>
      <div class="stat-box"><div class="stat-label">Total Runs</div><div class="stat-value">{n_runs}</div></div>
      <div class="stat-box"><div class="stat-label">Total Cost</div><div class="stat-value">${total_cost:.2f}</div></div>
    </div>"""

    # Leaderboard bar chart
    bar_models = [l["model"] for l in leaderboard]
    bar_scores = [l["mean"] for l in leaderboard]
    bar_colors = [score_text_color(s) for s in bar_scores]

    chart_html = f"""
    <div class="section">
      <h2>Model Leaderboard</h2>
      <div id="leaderboard-chart" style="height:400px"></div>
      <script>
        Plotly.newPlot('leaderboard-chart', [{{
          type: 'bar',
          x: {json.dumps(bar_scores)},
          y: {json.dumps(bar_models)},
          orientation: 'h',
          marker: {{ color: {json.dumps(bar_colors)} }},
          text: {json.dumps([f"{s:.1%}" for s in bar_scores])},
          textposition: 'outside',
          textfont: {{ color: '#e0e0e0', size: 12 }},
          hovertemplate: '%{{y}}: %{{x:.1%}}<extra></extra>',
        }}], {{
          paper_bgcolor: '#161b22',
          plot_bgcolor: '#161b22',
          font: {{ color: '#e0e0e0' }},
          margin: {{ l: 200, r: 60, t: 10, b: 40 }},
          xaxis: {{ range: [0, 1.05], gridcolor: '#30363d', tickformat: '.0%' }},
          yaxis: {{ autorange: 'reversed', gridcolor: '#30363d' }},
        }}, {{ responsive: true, toImageButtonOptions: {{ format: 'png', filename: 'finance-bench-chart', height: 800, width: 1400, scale: 2 }} }});
      </script>
    </div>"""

    # Leaderboard table
    table_rows = []
    for i, l in enumerate(leaderboard):
        rank = i + 1
        sc = l["mean"]
        color = score_text_color(sc)
        agent_type = "agentic" if l["model"].startswith(("claude-code-", "agent-", "oh-", "codex-", "gemini-cli-")) else "single-API"
        progress = l["min_rounds"] / 3
        progress_color = "#3fb950" if progress >= 1 else "#d29922" if progress >= 0.33 else "#f85149"
        table_rows.append(f"""<tr>
          <td style="font-weight:600;color:#8b949e">{rank}</td>
          <td><a href="/model/{l['model']}">{l['model']}</a></td>
          <td><span class="badge {'badge-pass' if agent_type == 'agentic' else 'badge-na'}">{agent_type}</span></td>
          <td style="color:{color};font-weight:700;font-size:15px">{sc:.1%}</td>
          <td>{l['n_tasks']}</td>
          <td>{l['n_runs']}</td>
          <td>${l['cost']:.4f}</td>
          <td style="min-width:80px">
            <div class="progress-bar"><div class="progress-fill" style="width:{progress*100:.0f}%;background:{progress_color}"></div></div>
            <span style="font-size:11px;color:#8b949e">{l['min_rounds']}/3 rounds</span>
          </td>
        </tr>""")

    table_html = f"""
    <div class="section">
      <div class="card" style="padding:0;overflow-x:auto">
      <table>
        <thead><tr><th>#</th><th>Model</th><th>Type</th><th>Mean Score</th><th>Tasks</th><th>Runs</th><th>Cost</th><th>Progress</th></tr></thead>
        <tbody>{"".join(table_rows)}</tbody>
      </table>
      </div>
    </div>"""

    return render("Finance-Bench", stats_html + chart_html + table_html, "home")


@app.route("/leaderboard")
def leaderboard():
    results = load_all_results()
    if not results:
        return render("Leaderboard", '<p style="color:#8b949e;text-align:center;padding:60px">No results yet.</p>', "leaderboard")

    # Classify each result as agentic or api
    def get_mode(r):
        agent = r.get("agent", "finance-zero")
        return "agentic" if agent in ("claude-code", "finance-agent", "openhands", "codex", "gemini-cli") or r.get("model", "").startswith(("agent-", "oh-", "codex-", "gemini-cli-", "claude-code-")) else "api"

    # Aggregate per model
    model_data = defaultdict(lambda: {"rewards": [], "costs": [], "tasks": set(),
                                       "rounds": defaultdict(int), "mode": "api"})
    for r in results:
        model = r.get("model", "?")
        task = r.get("task", "?")
        mode = get_mode(r)
        model_data[model]["mode"] = mode
        if not r.get("error") and r.get("reward") is not None:
            model_data[model]["rewards"].append(r["reward"])
            model_data[model]["tasks"].add(task)
            model_data[model]["rounds"][task] += 1
        if r.get("cost_usd"):
            model_data[model]["costs"].append(r["cost_usd"])

    # Split into two groups
    api_models = []
    agentic_models = []
    for model, d in model_data.items():
        mean = sum(d["rewards"]) / len(d["rewards"]) if d["rewards"] else 0
        cost = sum(d["costs"])
        min_rounds = min(d["rounds"].values()) if d["rounds"] else 0
        entry = {"model": model, "mean": mean, "cost": cost,
                 "n_tasks": len(d["tasks"]), "n_runs": len(d["rewards"]),
                 "min_rounds": min_rounds, "mode": d["mode"]}
        if d["mode"] == "agentic":
            agentic_models.append(entry)
        else:
            api_models.append(entry)
    api_models.sort(key=lambda x: -x["mean"])
    agentic_models.sort(key=lambda x: -x["mean"])

    def build_table(entries, mode_label):
        if not entries:
            return f'<p style="color:#8b949e">No {mode_label} results yet.</p>'
        rows = []
        for i, e in enumerate(entries):
            rank = i + 1
            sc = e["mean"]
            color = score_text_color(sc)
            progress = e["min_rounds"] / 3
            prog_color = "#3fb950" if progress >= 1 else "#d29922" if progress >= 0.33 else "#f85149"
            cost_str = f"${e['cost']:.4f}" if e["cost"] > 0 else "free*"
            rows.append(f"""<tr>
              <td style="font-weight:600;color:#8b949e">{rank}</td>
              <td><a href="/model/{e['model']}">{e['model']}</a></td>
              <td style="color:{color};font-weight:700;font-size:16px">{sc:.1%}</td>
              <td>{e['n_tasks']}</td>
              <td>{e['n_runs']}</td>
              <td>{cost_str}</td>
              <td style="min-width:80px">
                <div class="progress-bar"><div class="progress-fill" style="width:{progress*100:.0f}%;background:{prog_color}"></div></div>
                <span style="font-size:11px;color:#8b949e">{e['min_rounds']}/3</span>
              </td>
            </tr>""")
        return f"""<div class="card" style="padding:0;overflow-x:auto">
        <table>
          <thead><tr><th>#</th><th>Model</th><th>Mean Score</th><th>Tasks</th><th>Runs</th><th>Cost</th><th>Progress</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table></div>"""

    def build_chart(entries, chart_id):
        if not entries:
            return ""
        models = [e["model"] for e in entries]
        scores = [e["mean"] for e in entries]
        colors = [score_text_color(s) for s in scores]
        return f"""
        <div id="{chart_id}" style="height:{max(250, len(entries)*40)}px;margin-bottom:20px"></div>
        <script>
          Plotly.newPlot('{chart_id}', [{{
            type: 'bar', orientation: 'h',
            x: {json.dumps(scores)},
            y: {json.dumps(models)},
            marker: {{ color: {json.dumps(colors)} }},
            text: {json.dumps([f"{s:.1%}" for s in scores])},
            textposition: 'outside',
            textfont: {{ color: '#e0e0e0', size: 12 }},
            hovertemplate: '%{{y}}: %{{x:.1%}}<extra></extra>',
          }}], {{
            paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
            font: {{ color: '#e0e0e0' }},
            margin: {{ l: 200, r: 60, t: 10, b: 40 }},
            xaxis: {{ range: [0, 1.1], gridcolor: '#30363d', tickformat: '.0%' }},
            yaxis: {{ autorange: 'reversed', gridcolor: '#30363d' }},
          }}, {{ responsive: true, toImageButtonOptions: {{ format: 'png', filename: 'finance-bench-chart', height: 800, width: 1400, scale: 2 }} }});
        </script>"""

    # Head-to-head data
    all_entries = (agentic_models + api_models)[:]
    all_entries.sort(key=lambda x: -x["mean"])
    comp_models = [e["model"] for e in all_entries]
    comp_scores = [e["mean"] for e in all_entries]
    comp_colors = ["#a371f7" if e["mode"] == "agentic" else "#58a6ff" for e in all_entries]

    # Build page with tab buttons
    body = """
    <h2>Leaderboard</h2>
    <div style="display:flex;gap:8px;margin-bottom:24px">
      <button class="tab-btn active" onclick="switchTab('all')" id="btn-all"
        style="padding:8px 20px;border-radius:6px;border:1px solid #30363d;background:#238636;color:#fff;font-weight:600;font-size:13px;cursor:pointer">
        All Models</button>
      <button class="tab-btn" onclick="switchTab('agentic')" id="btn-agentic"
        style="padding:8px 20px;border-radius:6px;border:1px solid #30363d;background:#21262d;color:#e0e0e0;font-weight:600;font-size:13px;cursor:pointer">
        Agentic</button>
      <button class="tab-btn" onclick="switchTab('api')" id="btn-api"
        style="padding:8px 20px;border-radius:6px;border:1px solid #30363d;background:#21262d;color:#e0e0e0;font-weight:600;font-size:13px;cursor:pointer">
        Single API</button>
    </div>
    """

    # All panel
    body += f"""<div id="panel-all" class="tab-panel">
      <p class="subtitle"><span style="color:#a371f7">Purple = Agentic</span> &nbsp; <span style="color:#58a6ff">Blue = Single API</span></p>
      <div id="chart-all" style="height:{max(350, len(all_entries)*35)}px;margin-bottom:20px"></div>
      {build_table(all_entries, "all")}
    </div>"""

    # Agentic panel
    body += f"""<div id="panel-agentic" class="tab-panel" style="display:none">
      <p class="subtitle">Multi-turn agents that read files, write code, execute, and debug</p>
      <div id="chart-agentic" style="height:{max(250, len(agentic_models)*45)}px;margin-bottom:20px"></div>
      {build_table(agentic_models, "agentic")}
    </div>"""

    # API panel
    body += f"""<div id="panel-api" class="tab-panel" style="display:none">
      <p class="subtitle">Finance-Zero: one LLM call with task prompt, no iteration</p>
      <div id="chart-api" style="height:{max(250, len(api_models)*40)}px;margin-bottom:20px"></div>
      {build_table(api_models, "API")}
    </div>"""

    # Charts + tab switching JS
    ag_models = [e["model"] for e in agentic_models]
    ag_scores = [e["mean"] for e in agentic_models]
    ag_colors = [score_text_color(s) for s in ag_scores]
    ap_models = [e["model"] for e in api_models]
    ap_scores = [e["mean"] for e in api_models]
    ap_colors = [score_text_color(s) for s in ap_scores]

    body += f"""
    <script>
    var chartData = {{
      all: {{
        x: {json.dumps(comp_scores)}, y: {json.dumps(comp_models)},
        colors: {json.dumps(comp_colors)},
        text: {json.dumps([f"{s:.1%}" for s in comp_scores])}
      }},
      agentic: {{
        x: {json.dumps(ag_scores)}, y: {json.dumps(ag_models)},
        colors: {json.dumps(ag_colors)},
        text: {json.dumps([f"{s:.1%}" for s in ag_scores])}
      }},
      api: {{
        x: {json.dumps(ap_scores)}, y: {json.dumps(ap_models)},
        colors: {json.dumps(ap_colors)},
        text: {json.dumps([f"{s:.1%}" for s in ap_scores])}
      }}
    }};
    var chartLayout = {{
      paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
      font: {{ color: '#e0e0e0' }},
      margin: {{ l: 200, r: 60, t: 10, b: 40 }},
      xaxis: {{ range: [0, 1.1], gridcolor: '#30363d', tickformat: '.0%' }},
      yaxis: {{ autorange: 'reversed', gridcolor: '#30363d' }},
    }};
    function renderChart(tab) {{
      var d = chartData[tab];
      Plotly.newPlot('chart-' + tab, [{{
        type: 'bar', orientation: 'h',
        x: d.x, y: d.y,
        marker: {{ color: d.colors }},
        text: d.text,
        textposition: 'outside',
        textfont: {{ color: '#e0e0e0', size: 12 }},
        hovertemplate: '%{{y}}: %{{x:.1%}}<extra></extra>',
      }}], chartLayout, {{ responsive: true, toImageButtonOptions: {{ format: 'png', filename: 'finance-bench-chart', height: 800, width: 1400, scale: 2 }} }});
    }}
    function switchTab(tab) {{
      ['all','agentic','api'].forEach(function(t) {{
        document.getElementById('panel-' + t).style.display = t === tab ? 'block' : 'none';
        var btn = document.getElementById('btn-' + t);
        btn.style.background = t === tab ? '#238636' : '#21262d';
        btn.style.color = t === tab ? '#fff' : '#e0e0e0';
      }});
      renderChart(tab);
    }}
    // Initial render
    renderChart('all');
    </script>"""

    return render("Leaderboard", body, "leaderboard")


@app.route("/heatmap")
def heatmap():
    results = load_all_results()
    if not results:
        return render("Heatmap", '<p style="color:#8b949e;text-align:center;padding:60px">No results yet.</p>', "heatmap")

    # Build model × task matrix
    model_task = defaultdict(lambda: defaultdict(list))
    for r in results:
        if not r.get("error") and r.get("reward") is not None:
            model_task[r["model"]][r["task"]].append(r["reward"])

    all_tasks = sorted({r["task"] for r in results})
    # Sort models by mean score
    model_means = {}
    for model, tasks in model_task.items():
        all_rewards = [v for vs in tasks.values() for v in vs]
        model_means[model] = sum(all_rewards) / len(all_rewards) if all_rewards else 0
    all_models = sorted(model_means.keys(), key=lambda m: -model_means[m])

    # Build z-matrix
    z = []
    text = []
    for model in all_models:
        row = []
        text_row = []
        for task in all_tasks:
            scores = model_task[model].get(task, [])
            if scores:
                avg = sum(scores) / len(scores)
                row.append(avg)
                text_row.append(f"{avg:.2f} ({len(scores)}r)")
            else:
                row.append(None)
                text_row.append("--")
        z.append(row)
        text.append(text_row)

    heatmap_html = f"""
    <div class="section">
      <h2>Task x Model Heatmap</h2>
      <p class="subtitle">Average reward across valid rounds. Hover for details.</p>
      <div id="heatmap-chart" style="height:{max(400, len(all_models)*35 + 100)}px"></div>
      <script>
        Plotly.newPlot('heatmap-chart', [{{
          type: 'heatmap',
          z: {json.dumps(z)},
          x: {json.dumps(all_tasks)},
          y: {json.dumps(all_models)},
          text: {json.dumps(text)},
          texttemplate: '%{{text}}',
          textfont: {{ size: 10, color: '#fff' }},
          colorscale: [
            [0, '#4a1f1f'],
            [0.3, '#4a2a00'],
            [0.5, '#3d2e00'],
            [0.7, '#1a3a20'],
            [1, '#1f6a3a']
          ],
          zmin: 0, zmax: 1,
          hoverongaps: false,
          hovertemplate: '%{{y}} x %{{x}}<br>Score: %{{z:.2f}}<extra></extra>',
          colorbar: {{ tickformat: '.0%', title: 'Reward' }},
        }}], {{
          paper_bgcolor: '#161b22',
          plot_bgcolor: '#161b22',
          font: {{ color: '#e0e0e0', size: 11 }},
          margin: {{ l: 200, r: 80, t: 10, b: 120 }},
          xaxis: {{ tickangle: -45, gridcolor: '#30363d', side: 'bottom' }},
          yaxis: {{ gridcolor: '#30363d' }},
        }}, {{ responsive: true, toImageButtonOptions: {{ format: 'png', filename: 'finance-bench-chart', height: 800, width: 1400, scale: 2 }} }});
      </script>
    </div>"""

    return render("Heatmap", heatmap_html, "heatmap")


@app.route("/models")
def models_list():
    results = load_all_results()
    model_data = defaultdict(lambda: {"rewards": [], "costs": [], "errors": 0, "tasks": set(),
                                       "input_tokens": 0, "output_tokens": 0, "elapsed": []})
    for r in results:
        model = r.get("model", "?")
        model_data[model]["tasks"].add(r.get("task"))
        if r.get("error"):
            model_data[model]["errors"] += 1
        elif r.get("reward") is not None:
            model_data[model]["rewards"].append(r["reward"])
        if r.get("cost_usd"):
            model_data[model]["costs"].append(r["cost_usd"])
        model_data[model]["input_tokens"] += r.get("n_input_tokens") or 0
        model_data[model]["output_tokens"] += r.get("n_output_tokens") or 0
        if r.get("elapsed_sec"):
            model_data[model]["elapsed"].append(r["elapsed_sec"])

    rows = []
    sorted_models = sorted(model_data.items(), key=lambda x: -(sum(x[1]["rewards"])/len(x[1]["rewards"]) if x[1]["rewards"] else 0))
    for model, d in sorted_models:
        mean = sum(d["rewards"]) / len(d["rewards"]) if d["rewards"] else 0
        color = score_text_color(mean)
        cost = sum(d["costs"])
        perfect = sum(1 for r in d["rewards"] if r >= 1.0)
        zero = sum(1 for r in d["rewards"] if r == 0.0)
        total_time = sum(d["elapsed"])
        avg_time = total_time / len(d["elapsed"]) if d["elapsed"] else 0
        in_tok = d["input_tokens"]
        out_tok = d["output_tokens"]
        tok_str = f"{(in_tok+out_tok)/1000:.0f}k" if (in_tok+out_tok) > 0 else "--"
        time_str = f"{avg_time:.0f}s" if avg_time > 0 else "--"
        rows.append(f"""<tr>
          <td><a href="/model/{model}">{model}</a></td>
          <td style="color:{color};font-weight:700">{mean:.1%}</td>
          <td>{len(d['tasks'])}</td>
          <td>{len(d['rewards'])}</td>
          <td style="color:#3fb950">{perfect}</td>
          <td style="color:#f85149">{zero}</td>
          <td>{d['errors']}</td>
          <td>${cost:.4f}</td>
          <td class="mono">{tok_str}</td>
          <td class="mono">{time_str}</td>
        </tr>""")

    body = f"""
    <h2>All Models</h2>
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Model</th><th>Mean</th><th>Tasks</th><th>Runs</th><th>Perfect</th><th>Zero</th><th>Errors</th><th>Cost</th><th>Tokens</th><th>Avg Time</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>"""
    return render("Models", body, "models")


@app.route("/model/<model_name>")
def model_detail(model_name: str):
    results = load_all_results()
    model_results = [r for r in results if r.get("model") == model_name]
    if not model_results:
        abort(404)

    # Per-task breakdown
    task_data = defaultdict(lambda: {"rewards": [], "errors": 0, "subtests": []})
    for r in model_results:
        task = r.get("task", "?")
        if r.get("error"):
            task_data[task]["errors"] += 1
        elif r.get("reward") is not None:
            task_data[task]["rewards"].append(r["reward"])
        if r.get("subtests"):
            task_data[task]["subtests"] = r["subtests"]

    all_rewards = [r for d in task_data.values() for r in d["rewards"]]
    mean = sum(all_rewards) / len(all_rewards) if all_rewards else 0
    color = score_text_color(mean)

    # Stats
    stats = f"""
    <div class="grid">
      <div class="stat-box"><div class="stat-label">Mean Score</div><div class="stat-value" style="color:{color}">{mean:.1%}</div></div>
      <div class="stat-box"><div class="stat-label">Tasks</div><div class="stat-value">{len(task_data)}</div></div>
      <div class="stat-box"><div class="stat-label">Total Runs</div><div class="stat-value">{len(all_rewards)}</div></div>
      <div class="stat-box"><div class="stat-label">Perfect Scores</div><div class="stat-value" style="color:#3fb950">{sum(1 for r in all_rewards if r >= 1.0)}</div></div>
    </div>"""

    # Task table
    task_rows = []
    for task in sorted(task_data.keys()):
        d = task_data[task]
        rewards = d["rewards"]
        if rewards:
            avg = sum(rewards) / len(rewards)
            tc = score_text_color(avg)
            scores_str = ", ".join(f"{r:.2f}" for r in rewards)
            task_rows.append(f"""<tr>
              <td><a href="/task/{task}">{task}</a></td>
              <td style="color:{tc};font-weight:700">{avg:.2f}</td>
              <td>{len(rewards)}</td>
              <td class="mono" style="font-size:11px;color:#8b949e">{scores_str}</td>
              <td>{d['errors']}</td>
            </tr>""")
        else:
            task_rows.append(f"""<tr>
              <td><a href="/task/{task}">{task}</a></td>
              <td style="color:#8b949e">--</td>
              <td>0</td>
              <td>--</td>
              <td>{d['errors']}</td>
            </tr>""")

    # Bar chart of per-task scores
    tasks_sorted = sorted(task_data.keys(), key=lambda t: -(sum(task_data[t]["rewards"])/len(task_data[t]["rewards"]) if task_data[t]["rewards"] else 0))
    chart_tasks = tasks_sorted
    chart_scores = [sum(task_data[t]["rewards"])/len(task_data[t]["rewards"]) if task_data[t]["rewards"] else 0 for t in chart_tasks]
    chart_colors = [score_text_color(s) for s in chart_scores]

    chart = f"""
    <div id="model-chart" style="height:400px;margin-bottom:20px"></div>
    <script>
      Plotly.newPlot('model-chart', [{{
        type: 'bar',
        x: {json.dumps(chart_tasks)},
        y: {json.dumps(chart_scores)},
        marker: {{ color: {json.dumps(chart_colors)} }},
        text: {json.dumps([f"{s:.2f}" for s in chart_scores])},
        textposition: 'outside',
        textfont: {{ color: '#e0e0e0', size: 11 }},
      }}], {{
        paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
        font: {{ color: '#e0e0e0' }},
        margin: {{ l: 50, r: 20, t: 10, b: 120 }},
        xaxis: {{ tickangle: -45, gridcolor: '#30363d' }},
        yaxis: {{ range: [0, 1.1], gridcolor: '#30363d', tickformat: '.0%' }},
      }}, {{ responsive: true, toImageButtonOptions: {{ format: 'png', filename: 'finance-bench-chart', height: 800, width: 1400, scale: 2 }} }});
    </script>"""

    table = f"""
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Task</th><th>Mean</th><th>Rounds</th><th>Individual Scores</th><th>Errors</th></tr></thead>
      <tbody>{"".join(task_rows)}</tbody>
    </table>
    </div>"""

    return render(model_name, f"<h2>{model_name}</h2>" + stats + chart + table, "models")


@app.route("/tasks")
def tasks_list():
    results = load_all_results()
    task_data = defaultdict(lambda: {"rewards": [], "models": set()})
    for r in results:
        task = r.get("task", "?")
        if not r.get("error") and r.get("reward") is not None:
            task_data[task]["rewards"].append(r["reward"])
            task_data[task]["models"].add(r["model"])

    # Sort by mean (hardest first)
    sorted_tasks = sorted(task_data.items(),
                          key=lambda x: sum(x[1]["rewards"])/len(x[1]["rewards"]) if x[1]["rewards"] else 0)

    rows = []
    for task, d in sorted_tasks:
        mean = sum(d["rewards"]) / len(d["rewards"]) if d["rewards"] else 0
        color = score_text_color(mean)
        perfect = sum(1 for r in d["rewards"] if r >= 1.0)
        zero = sum(1 for r in d["rewards"] if r == 0.0)
        rows.append(f"""<tr>
          <td><a href="/task/{task}">{task}</a></td>
          <td style="color:{color};font-weight:700">{mean:.1%}</td>
          <td>{len(d['models'])}</td>
          <td>{len(d['rewards'])}</td>
          <td style="color:#3fb950">{perfect}</td>
          <td style="color:#f85149">{zero}</td>
        </tr>""")

    body = f"""
    <h2>Task Difficulty Ranking</h2>
    <p class="subtitle">Sorted by mean score across all models (hardest first)</p>
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Task</th><th>Mean</th><th>Models</th><th>Runs</th><th>Perfect</th><th>Zero</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>"""
    return render("Tasks", body, "tasks")


@app.route("/task/<task_name>")
def task_detail(task_name: str):
    results = load_all_results()
    task_results = [r for r in results if r.get("task") == task_name]
    if not task_results:
        abort(404)

    # Per-model breakdown
    model_data = defaultdict(lambda: {"rewards": [], "errors": 0})
    for r in task_results:
        model = r.get("model", "?")
        if r.get("error"):
            model_data[model]["errors"] += 1
        elif r.get("reward") is not None:
            model_data[model]["rewards"].append(r["reward"])

    sorted_models = sorted(model_data.items(),
                           key=lambda x: -(sum(x[1]["rewards"])/len(x[1]["rewards"]) if x[1]["rewards"] else 0))

    rows = []
    chart_models = []
    chart_scores = []
    for model, d in sorted_models:
        rewards = d["rewards"]
        if rewards:
            avg = sum(rewards) / len(rewards)
            tc = score_text_color(avg)
            scores_str = ", ".join(f"{r:.2f}" for r in rewards)
            chart_models.append(model)
            chart_scores.append(avg)
        else:
            avg = 0
            tc = "#8b949e"
            scores_str = "--"
        rows.append(f"""<tr>
          <td><a href="/model/{model}">{model}</a></td>
          <td style="color:{tc};font-weight:700">{avg:.2f}</td>
          <td>{len(rewards)}</td>
          <td class="mono" style="font-size:11px;color:#8b949e">{scores_str}</td>
          <td>{d['errors']}</td>
        </tr>""")

    chart_colors = [score_text_color(s) for s in chart_scores]
    chart = f"""
    <div id="task-chart" style="height:400px;margin-bottom:20px"></div>
    <script>
      Plotly.newPlot('task-chart', [{{
        type: 'bar',
        x: {json.dumps(chart_scores)},
        y: {json.dumps(chart_models)},
        orientation: 'h',
        marker: {{ color: {json.dumps(chart_colors)} }},
        text: {json.dumps([f"{s:.2f}" for s in chart_scores])},
        textposition: 'outside',
        textfont: {{ color: '#e0e0e0', size: 11 }},
      }}], {{
        paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
        font: {{ color: '#e0e0e0' }},
        margin: {{ l: 200, r: 60, t: 10, b: 40 }},
        xaxis: {{ range: [0, 1.1], gridcolor: '#30363d', tickformat: '.0%' }},
        yaxis: {{ autorange: 'reversed', gridcolor: '#30363d' }},
      }}, {{ responsive: true, toImageButtonOptions: {{ format: 'png', filename: 'finance-bench-chart', height: 800, width: 1400, scale: 2 }} }});
    </script>"""

    table = f"""
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Model</th><th>Mean</th><th>Rounds</th><th>Individual Scores</th><th>Errors</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>"""

    return render(task_name, f"<h2>{task_name}</h2>" + chart + table, "tasks")


@app.route("/logs")
def logs():
    runs = load_run_files()

    rows = []
    for r in runs:
        meta = r["meta"]
        tag = meta.get("tag", "--")
        models = ", ".join(meta.get("models", [])[:3])
        if len(meta.get("models", [])) > 3:
            models += f" +{len(meta['models'])-3}"
        wall = meta.get("wall_time_sec", 0)
        wall_str = f"{wall/60:.1f}m" if wall else "--"
        started = meta.get("started_at", "--")[:19].replace("T", " ")

        valid_badge = f'<span class="badge badge-pass">{r["n_valid"]} valid</span>'
        error_badge = f'<span class="badge badge-fail">{r["n_errors"]} err</span>' if r["n_errors"] else ""
        invalid_badge = f'<span class="badge badge-warn">{r["n_invalid"]} invalid</span>' if r["n_invalid"] else ""

        rows.append(f"""<tr>
          <td><a href="/log/{r['file']}" class="mono">{r['file']}</a></td>
          <td>{tag}</td>
          <td class="mono" style="font-size:11px">{models}</td>
          <td>{r['n_total']}</td>
          <td>{valid_badge} {error_badge} {invalid_badge}</td>
          <td>{wall_str}</td>
          <td class="mono" style="font-size:11px;color:#8b949e">{started}</td>
        </tr>""")

    body = f"""
    <h2>Run Logs</h2>
    <p class="subtitle">All result files from benchmark.py runs</p>
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>File</th><th>Tag</th><th>Models</th><th>Total</th><th>Status</th><th>Wall Time</th><th>Started</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>"""
    return render("Logs", body, "logs")


@app.route("/log/<filename>")
def log_detail(filename: str):
    filepath = RESULTS_DIR / filename
    if not filepath.exists():
        abort(404)
    data = json.loads(filepath.read_text())
    meta = data.get("meta", {})
    results = data.get("results", [])

    models_in_file = {r.get("model") for r in results}
    bad_models = {m for m in models_in_file if _is_all_zero_run(results, m)}

    meta_html = f"""
    <h2 class="mono">{filename}</h2>
    <div class="card">
      <pre>{html_lib.escape(json.dumps(meta, indent=2, ensure_ascii=False))}</pre>
    </div>"""

    if bad_models:
        meta_html += f"""
        <div class="card" style="border-color:#da3633">
          <h3 style="color:#f85149">Invalid (all-zero) models in this run</h3>
          <p style="color:#8b949e;margin-top:8px">{", ".join(sorted(bad_models))}</p>
        </div>"""

    rows = []
    for r in sorted(results, key=lambda x: (x.get("model", ""), x.get("task", ""))):
        model = r.get("model", "?")
        task = r.get("task", "?")
        reward = r.get("reward")
        error = r.get("error")
        is_bad = model in bad_models

        if is_bad:
            badge = '<span class="badge badge-warn">INVALID</span>'
        elif error:
            badge = f'<span class="badge badge-fail">ERROR</span>'
        elif reward is not None and reward >= 0.9:
            badge = f'<span class="badge badge-pass">{reward:.2f}</span>'
        elif reward is not None:
            badge = f'<span class="badge badge-na">{reward:.2f}</span>'
        else:
            badge = '<span class="badge badge-na">--</span>'

        cost = f"${r.get('cost_usd', 0) or 0:.4f}"
        elapsed = f"{r.get('elapsed_sec', 0):.0f}s"
        err_msg = html_lib.escape(str(error)[:80]) if error else ""

        rows.append(f"""<tr style="{'opacity:0.4' if is_bad else ''}">
          <td><a href="/model/{model}">{model}</a></td>
          <td><a href="/task/{task}">{task}</a></td>
          <td>{badge}</td>
          <td class="mono">{cost}</td>
          <td class="mono">{elapsed}</td>
          <td style="color:#f85149;font-size:11px">{err_msg}</td>
        </tr>""")

    table = f"""
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Model</th><th>Task</th><th>Score</th><th>Cost</th><th>Time</th><th>Error</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>"""

    return render(filename, meta_html + table, "logs")


# ---------------------------------------------------------------------------
# Harbor jobs browser (legacy)
# ---------------------------------------------------------------------------

def load_json_safe(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


@app.route("/jobs")
def jobs_index():
    if not JOBS_DIR.exists():
        return render("Jobs", '<p style="color:#8b949e;text-align:center;padding:60px">No harbor jobs found.</p>', "jobs")

    runs = sorted([d for d in JOBS_DIR.iterdir() if d.is_dir()], reverse=True)

    rows = []
    for run in runs[:100]:  # limit display
        result = load_json_safe(run / "result.json")
        cfg = load_json_safe(run / "config.json")
        agent = cfg.get("agent", {}).get("name", "--")

        evals = result.get("stats", {}).get("evals", {})
        mean = None
        n_trials = 0
        for v in evals.values():
            n_trials = v.get("n_trials", 0)
            try:
                mean = v["metrics"][0]["mean"]
            except (KeyError, IndexError):
                pass

        if mean is not None:
            sc_color = score_text_color(mean)
            score_html = f'<span style="color:{sc_color};font-weight:700">{mean:.1%}</span>'
        else:
            score_html = '<span style="color:#8b949e">--</span>'

        rows.append(f"""<tr>
          <td><a href="/job/{run.name}" class="mono">{run.name}</a></td>
          <td>{agent}</td>
          <td>{n_trials}</td>
          <td>{score_html}</td>
        </tr>""")

    table = f"""
    <h2>Harbor Jobs</h2>
    <p class="subtitle">Direct harbor run results (legacy view)</p>
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Run ID</th><th>Agent</th><th>Trials</th><th>Score</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>"""
    return render("Jobs", table, "jobs")


@app.route("/job/<run_id>")
def job_detail(run_id: str):
    run_dir = JOBS_DIR / run_id
    if not run_dir.exists():
        abort(404)

    result = load_json_safe(run_dir / "result.json")
    cfg = load_json_safe(run_dir / "config.json")
    agent = cfg.get("agent", {}).get("name", "--")
    model = cfg.get("model", "--")

    evals = result.get("stats", {}).get("evals", {})
    rewards_map = {}
    exceptions = {}
    for v in evals.values():
        for score_str, task_list in v.get("reward_stats", {}).get("reward", {}).items():
            for tid in task_list:
                tname = tid.rsplit("__", 1)[0]
                rewards_map[tname] = float(score_str)
        for exc_type, task_list in v.get("exception_stats", {}).items():
            for tid in task_list:
                tname = tid.rsplit("__", 1)[0]
                exceptions[tname] = exc_type

    header = f"""
    <h2 class="mono">{run_id}</h2>
    <div class="grid">
      <div class="stat-box"><div class="stat-label">Agent</div><div class="stat-value" style="font-size:16px">{agent}</div></div>
      <div class="stat-box"><div class="stat-label">Model</div><div class="stat-value" style="font-size:16px">{model}</div></div>
    </div>"""

    task_rows = []
    for task in sorted(set(list(rewards_map.keys()) + list(exceptions.keys()))):
        if task in exceptions:
            badge = f'<span class="badge badge-fail">{exceptions[task]}</span>'
            score_str = "ERROR"
        else:
            score = rewards_map.get(task, 0)
            tc = score_text_color(score)
            badge = f'<span style="color:{tc};font-weight:700">{score:.2f}</span>'
            score_str = f"{score:.2f}"

        # Check for task directory
        task_dirs = [d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith(task)]
        link = f'<a href="/job/{run_id}/task/{task_dirs[0].name}">{task}</a>' if task_dirs else task

        task_rows.append(f"<tr><td>{link}</td><td>{badge}</td></tr>")

    table = f"""
    <div class="card" style="padding:0;overflow-x:auto">
    <table>
      <thead><tr><th>Task</th><th>Score</th></tr></thead>
      <tbody>{"".join(task_rows)}</tbody>
    </table>
    </div>"""

    # Raw result.json
    raw = f"""
    <h3 style="margin-top:20px">result.json</h3>
    <div class="card" style="padding:0">
      <pre>{html_lib.escape(json.dumps(result, indent=2, ensure_ascii=False))}</pre>
    </div>"""

    return render(f"Job {run_id}", header + table + raw, "jobs")


@app.route("/job/<run_id>/task/<task_dir>")
def job_task_detail(run_id: str, task_dir: str):
    d = JOBS_DIR / run_id / task_dir
    if not d.exists():
        abort(404)

    task_name = task_dir.rsplit("__", 1)[0]
    reward_file = d / "verifier" / "reward.txt"
    reward = reward_file.read_text().strip() if reward_file.exists() else "?"

    header = f"""
    <div style="margin-bottom:8px"><a href="/job/{run_id}">Back to {run_id}</a></div>
    <h2>{task_name}</h2>
    <p class="subtitle">Reward: {reward}</p>"""

    # ctrf
    ctrf = load_json_safe(d / "verifier" / "ctrf.json")
    tests = ctrf.get("results", {}).get("tests", [])
    test_rows = []
    for t in tests:
        s = t.get("status", "?")
        is_pass = s == "passed"
        dot = '<span style="color:#3fb950">&#9679;</span>' if is_pass else '<span style="color:#f85149">&#9679;</span>'
        name = t.get("name", "").split("::")[-1]
        test_rows.append(f"<tr><td>{dot}</td><td class='mono'>{html_lib.escape(name)}</td><td>{s}</td></tr>")

    test_table = ""
    if test_rows:
        test_table = f"""
        <h3>Test Details</h3>
        <div class="card" style="padding:0;margin-bottom:20px">
        <table>
          <thead><tr><th></th><th>Test</th><th>Status</th></tr></thead>
          <tbody>{"".join(test_rows)}</tbody>
        </table>
        </div>"""

    # stdout
    stdout_file = d / "verifier" / "test-stdout.txt"
    stdout = html_lib.escape(stdout_file.read_text()) if stdout_file.exists() else "(no output)"
    stdout_html = f"""
    <h3>Test Output</h3>
    <div class="card" style="padding:0"><pre>{stdout}</pre></div>"""

    # result.json
    result_data = load_json_safe(d / "result.json")
    result_html = f"""
    <h3 style="margin-top:20px">result.json</h3>
    <div class="card" style="padding:0"><pre>{html_lib.escape(json.dumps(result_data, indent=2, ensure_ascii=False))}</pre></div>"""

    return render(task_name, header + test_table + stdout_html + result_html, "jobs")


if __name__ == "__main__":
    print("Finance-Bench Dashboard -> http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=True)
