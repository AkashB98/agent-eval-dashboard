"""Golden evals: pinned expectations over the full fixture fleet.

Writes evals/eval_report.json. Fully deterministic: no clocks, no uuids --
the report must be byte-identical across runs (md5 recorded in-report and
printed). Conventions from the sibling builds:

  python3 evals/run_evals.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from adapters import extract  # noqa: E402
from dashboard import render_fleet  # noqa: E402
from health import check_exit_code, fleet_health  # noqa: E402
from store import Store, canonical  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "eval_report.json")

results = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append({"name": name, "pass": bool(condition), "detail": detail})
    if not condition:
        print(f"FAIL {name}: {detail}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="evaldash-evals-")
    store = Store(tmp)
    for env in fixtures.make_all():
        store.ingest(env)
    fleet = fleet_health(store)

    # --- adapter pins -------------------------------------------------------
    rt = [extract(fixtures.make_run("ai-red-teaming-harness", i)) for i in range(3)]
    check("redteam_headlines", [s["headline"] for s in rt] == [0.9286, 0.9643, 1.0],
          str([s["headline"] for s in rt]))
    check("redteam_statuses", [s["status"] for s in rt] == ["warning", "green", "green"])
    check("redteam_failures_evidence",
          len(rt[0]["findings"]) == 2
          and all(f["severity"] == "critical" and f["evidence"].strip()
                  for f in rt[0]["findings"]))

    rp = [extract(fixtures.make_run("tool-call-trace-replay", i)) for i in range(3)]
    check("replay_headline_r1", abs(rp[1]["headline"] - 29 / 30) < 1e-9,
          str(rp[1]["headline"]))
    check("replay_drift_evidence",
          rp[1]["status"] == "warning"
          and rp[1]["metrics"]["drifted"] == 1
          and "status=processing" in rp[1]["findings"][0]["evidence"])

    an = extract(fixtures.make_run("trace-anomaly-detector", 2))
    check("anomaly_critical_warns",
          an["status"] == "warning" and an["headline"] == 1.0
          and any(f["severity"] == "critical" and "token_blowup" in f["title"]
                  for f in an["findings"]))

    va = [extract(fixtures.make_run("structured-output-validator", i)) for i in range(3)]
    check("validator_pass_rates", [s["headline"] for s in va] == [0.98, 0.90, 0.80])
    check("validator_critical",
          va[2]["status"] == "critical"
          and va[2]["breakdown"][0] == {"label": "type_mismatch", "value": 20})

    fw = extract(fixtures.make_run("prompt-injection-firewall", 0))
    check("firewall_all_green", fw["headline"] == 1.0 and fw["status"] == "green")
    fw1 = extract(fixtures.make_run("prompt-injection-firewall", 1))
    check("firewall_blocked_is_info",
          all(f["severity"] == "info" for f in fw1["findings"]))

    sy = [extract(fixtures.make_run("adversarial-prompt-synthesizer", i)) for i in range(3)]
    check("synth_quality", [s["headline"] for s in sy] == [1.0, 1.0, 0.8]
          and sy[2]["status"] == "warning"
          and "k=6" in sy[2]["findings"][0]["evidence"])

    # --- store pins ---------------------------------------------------------
    check("manifest_rows", len(store.manifest()) == 18)
    md5_before = store.store_md5()
    for env in fixtures.make_all():
        store.ingest(env)
    check("ingest_idempotent", store.store_md5() == md5_before)

    # --- health pins --------------------------------------------------------
    check("fleet_critical", fleet["status"] == "critical"
          and check_exit_code(fleet) == 2
          and fleet["n_tools"] == 6 and fleet["n_runs"] == 18)
    trends = {p["tool"]: p["trend"] for p in fleet["projects"]}
    check("fleet_trends", trends == {
        "ai-red-teaming-harness": "improving",
        "tool-call-trace-replay": "steady",
        "trace-anomaly-detector": "steady",
        "structured-output-validator": "declining",
        "prompt-injection-firewall": "steady",
        "adversarial-prompt-synthesizer": "declining",
    }, str(trends))
    check("fleet_alerts",
          len(fleet["alerts"]) == 5
          and all(a["evidence"].strip() for a in fleet["alerts"]),
          str(len(fleet["alerts"])))

    # --- dashboard pins -----------------------------------------------------
    page = render_fleet(fleet, simulated=True)
    check("dashboard_renders", "fleet: critical" in page and "SIMULATED DATA" in page)
    check("dashboard_deterministic",
          render_fleet(fleet, simulated=True) == page)

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    report = {
        "evals": "agent-eval-dashboard",
        "n_checks": total,
        "n_passed": passed,
        "all_passed": passed == total,
        "checks": results,
    }
    # md5 of the canonical report bytes (excluding the md5 field itself)
    report_md5 = hashlib.md5(canonical(report).encode("utf-8")).hexdigest()
    report["determinism"] = {
        "runs_required": 3,
        "md5": report_md5,
        "note": "byte-identical eval_report.json across 3 runs",
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(canonical(report) + "\n")

    print(f"evals: {passed}/{total} passed; report md5={report_md5}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
