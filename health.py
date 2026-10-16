"""Health model: per-project latest run + trend, fleet roll-up.

Trend (needs >= 2 runs, else "new"):
  delta = latest.headline - previous.headline
  improving if delta >  +0.02
  declining  if delta <  -0.02
  steady     otherwise

Fleet roll-up:
  critical  if any project is critical
  warning   if any project is warning or declining
  all-green otherwise

Every project contributes its latest findings; severity critical/high
findings are surfaced as fleet-level alerts with evidence quotes.
"""

from __future__ import annotations

TREND_EPS = 0.02

STATUS_ORDER = {"green": 0, "warning": 1, "critical": 2}
FLEET_STATUS = {0: "all-green", 1: "warning", 2: "critical"}


def project_health(summaries: list) -> dict:
    """summaries: adapter outputs for one tool, oldest first."""
    if not summaries:
        return {"tool": None, "runs": 0, "trend": "new", "status": "green",
                "latest": None, "delta": None, "history": []}
    tool = summaries[0]["tool"]
    latest = summaries[-1]
    history = [
        {
            "run_id": s["run_id"],
            "ts": s["ts"],
            "headline": s["headline"],
            "status": s["status"],
            "findings": s.get("findings", []),
        }
        for s in summaries
    ]
    if len(summaries) >= 2:
        # round: 0.92 - 0.90 is 0.020000000000000004 in float, which would
        # slip past the > 0.02 improving check without this.
        delta = round(latest["headline"] - summaries[-2]["headline"], 9)
        trend = (
            "improving" if delta > TREND_EPS
            else "declining" if delta < -TREND_EPS
            else "steady"
        )
    else:
        delta, trend = None, "new"
    return {
        "tool": tool,
        "runs": len(summaries),
        "trend": trend,
        "delta": delta,
        "status": latest["status"],
        "latest": latest,
        "history": history,
    }


def fleet_health(store, as_of: str | None = None) -> dict:
    """Whole-fleet health view. as_of defaults to the latest run ts (deterministic)."""
    manifest = store.manifest()
    tools = sorted({r["tool"] for r in manifest})
    projects = [project_health(store.runs_for(t)) for t in tools]

    worst = 0
    alerts = []
    for p in projects:
        worst = max(worst, STATUS_ORDER[p["status"]])
        if p["trend"] == "declining":
            worst = max(worst, STATUS_ORDER["warning"])
        for f in p["latest"].get("findings", []):
            if f["severity"] in ("critical", "high"):
                alerts.append(
                    {
                        "tool": p["tool"],
                        "run_id": p["latest"]["run_id"],
                        "severity": f["severity"],
                        "title": f["title"],
                        "evidence": f["evidence"],
                    }
                )
    alerts.sort(key=lambda a: (a["tool"], a["severity"], a["title"]))

    if as_of is None:
        as_of = max((r["ts"] for r in manifest), default=None)
    return {
        "status": FLEET_STATUS[worst],
        "projects": projects,
        "alerts": alerts,
        "n_runs": len(manifest),
        "n_tools": len(tools),
        "as_of": as_of,
    }


def check_exit_code(fleet: dict) -> int:
    """CI exit code: 0 all-green, 1 warning, 2 critical."""
    return {"all-green": 0, "warning": 1, "critical": 2}[fleet["status"]]
