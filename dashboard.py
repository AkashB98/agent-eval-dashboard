"""Zero-dependency fleet dashboard: one inline HTML/SVG page.

render_fleet(fleet) -> str: deterministic HTML (same fleet -> byte-identical).
render_run(summary) -> str: drill-down page for one run.
All dynamic strings are HTML-escaped; the page carries a SIMULATED DATA
banner whenever ingested artifacts are marked simulated.
"""

from __future__ import annotations

import html

from adapters import TOOL_TITLES

_STATUS_COLOR = {"green": "#1a7f37", "warning": "#9a6700", "critical": "#cf222e"}
_FLEET_COLOR = {"all-green": "#1a7f37", "warning": "#9a6700", "critical": "#cf222e"}
_TREND_ARROW = {"improving": "&#8599;", "steady": "&#8594;", "declining": "&#8600;", "new": "&#9679;"}


def _esc(x) -> str:
    return html.escape(str(x), quote=True)


def _sparkline(headlines: list) -> str:
    """Tiny SVG trend line, 0..1 mapped onto a 100x28 box."""
    w, h = 100, 28
    pts = []
    n = len(headlines)
    for i, v in enumerate(headlines):
        x = 4 + (w - 8) * (i / (n - 1)) if n > 1 else w / 2
        y = h - 3 - (h - 6) * max(0.0, min(1.0, v))
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="2.5" fill="#0969da"/>'
        for x, y in (p.split(",") for p in pts)
    )
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="headline trend"><polyline points="{poly}" fill="none" '
        f'stroke="#0969da" stroke-width="2"/>{dots}</svg>'
    )


def _finding_html(f: dict) -> str:
    color = {"critical": "#cf222e", "high": "#cf222e", "medium": "#9a6700",
             "low": "#57606a", "info": "#57606a"}.get(f["severity"], "#57606a")
    return (
        f'<div class="finding" style="border-left:4px solid {color}">'
        f'<b>[{_esc(f["severity"])}]</b> {_esc(f["title"])}'
        f'<div class="evidence">&ldquo;{_esc(f["evidence"])}&rdquo;</div></div>'
    )


def _project_card(p: dict, simulated: bool) -> str:
    latest = p["latest"]
    color = _STATUS_COLOR[p["status"]]
    headlines = [s["headline"] for s in p.get("history", [])]
    rows = []
    for s in p.get("history", []):
        inner = "".join(_finding_html(f) for f in s.get("findings", []))
        if not inner:
            inner = "<p class='muted'>no findings</p>"
        rows.append(
            f'<details class="run"><summary>{_esc(s["run_id"])} &middot; {_esc(s["ts"])} '
            f'&middot; headline {_esc(round(s["headline"], 3))} '
            f'&middot; <span style="color:{_STATUS_COLOR[s["status"]]}">{_esc(s["status"])}</span>'
            f"</summary>{inner}</details>"
        )
    findings = "".join(_finding_html(f) for f in latest.get("findings", []))
    return (
        f'<section class="card" id="card-{_esc(p["tool"])}">'
        f'<h2><span class="dot" style="background:{color}"></span>'
        f'{_esc(TOOL_TITLES.get(p["tool"], p["tool"]))}'
        f' <small class="muted">{_esc(p["tool"])}</small></h2>'
        f'<div class="headrow"><div class="headline">{_esc(round(latest["headline"], 3))}'
        f'<div class="label">{_esc(latest["headline_label"])}</div></div>'
        f'<div class="trend">{_TREND_ARROW[p["trend"]]} {_esc(p["trend"])}'
        f'<div class="label">over {p["runs"]} runs</div></div>'
        f'<div>{_sparkline(headlines)}<div class="label">headline trend</div></div></div>'
        f'<table class="metrics">' + "".join(
            f"<tr><td>{_esc(k)}</td><td><b>{_esc(v)}</b></td></tr>"
            for k, v in latest["metrics"].items()
        ) + "</table>"
        + (f"<h3>Findings ({len(latest['findings'])})</h3>" + findings
           if findings else "<p class='muted'>No findings on the latest run.</p>")
        + f"<h3>Run history</h3>" + ("".join(rows) or "<p class='muted'>No runs yet.</p>")
        + "</section>"
    )


def render_fleet(fleet: dict, simulated: bool = False) -> str:
    """Full dashboard page for a fleet_health() dict."""
    color = _FLEET_COLOR[fleet["status"]]
    for p in fleet["projects"]:
        pass
    cards = "\n".join(_project_card(p, simulated) for p in fleet["projects"])
    alerts = "".join(
        f'<div class="finding" style="border-left:4px solid '
        f'{"#cf222e" if a["severity"]=="critical" else "#9a6700"}">'
        f'<b>[{_esc(a["severity"])}]</b> {_esc(a["tool"])} &mdash; {_esc(a["title"])}'
        f'<div class="evidence">&ldquo;{_esc(a["evidence"])}&rdquo;</div></div>'
        for a in fleet["alerts"]
    )
    banner = (
        '<div class="sim">SIMULATED DATA &mdash; this view is built from fictional '
        "sample artifacts, never personal data.</div>" if simulated else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-eval-dashboard &mdash; fleet health</title>
<style>
body{{font-family:-apple-system,system-ui,sans-serif;max-width:1080px;margin:0 auto;padding:24px;color:#1f2328;background:#f6f8fa}}
h1{{font-size:1.6em}} h2{{font-size:1.2em}} h3{{font-size:1em;margin:14px 0 6px}}
.muted{{color:#57606a}} .label{{font-size:.75em;color:#57606a}}
.card{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:16px 20px;margin:16px 0}}
.dot{{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:8px}}
.headrow{{display:flex;gap:32px;align-items:center;margin:8px 0}}
.headline{{font-size:2em;font-weight:700}} .trend{{font-size:1.2em}}
.metrics{{border-collapse:collapse;margin:8px 0}} .metrics td{{border:1px solid #d0d7de;padding:4px 10px;font-size:.9em}}
.finding{{background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:8px 12px;margin:8px 0;font-size:.9em}}
.evidence{{color:#57606a;font-style:italic;margin-top:4px;word-break:break-word}}
.sim{{background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:10px 14px;font-weight:600}}
.statusline{{font-size:1.1em;padding:10px 14px;border-radius:6px;color:#fff;background:{color};display:inline-block}}
.run summary{{cursor:pointer;padding:6px 0}} .run{{border-top:1px solid #eaeef2}}
</style>
</head>
<body>
{banner}
<h1>Agent eval dashboard</h1>
<p class="muted">One page showing whether the whole agent stack is healthy: red-team grades,
replay verdicts, anomaly findings, validator drift, firewall scans, and attack coverage &mdash;
across runs, with trends.</p>
<p><span class="statusline">fleet: {fleet["status"]} &middot; {fleet["n_tools"]} tools &middot;
{fleet["n_runs"]} runs &middot; as of {_esc(fleet["as_of"])}</span></p>
<h2>Fleet alerts ({len(fleet["alerts"])})</h2>
{alerts or "<p class='muted'>No critical/high alerts. Fleet is quiet.</p>"}
{cards}
<hr><p class="muted">agent-eval-dashboard &mdash; zero-dependency mission control for agent evals.</p>
</body>
</html>
"""


def render_run(summary: dict, simulated: bool = False) -> str:
    """Drill-down page for a single run summary."""
    color = _STATUS_COLOR[summary["status"]]
    findings = "".join(_finding_html(f) for f in summary.get("findings", []))
    banner = (
        '<div class="sim">SIMULATED DATA</div>' if simulated else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{_esc(summary["run_id"])}</title>
<style>body{{font-family:-apple-system,system-ui,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#1f2328}}
.finding{{border:1px solid #d0d7de;border-radius:6px;padding:8px 12px;margin:8px 0}}
.evidence{{color:#57606a;font-style:italic;margin-top:4px;word-break:break-word}}
.muted{{color:#57606a}}.sim{{background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:10px 14px;font-weight:600}}</style>
</head><body>
{banner}
<h1><span style="color:{color}">&#9679;</span> {_esc(summary["run_id"])}</h1>
<p class="muted">{_esc(summary["tool"])} &middot; {_esc(summary["ts"])}</p>
<p>Headline: <b>{_esc(round(summary["headline"], 3))}</b> ({_esc(summary["headline_label"])})</p>
<h2>Findings ({len(summary.get("findings", []))})</h2>
{findings or "<p class='muted'>No findings.</p>"}
<p><a href="/">back to fleet</a></p>
</body></html>
"""
