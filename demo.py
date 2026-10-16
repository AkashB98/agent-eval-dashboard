"""One-command end-to-end demo: generate -> ingest -> health -> serve.

Builds DETERMINISTIC fictional artifacts for all 6 sibling tools (invented
Helios Home / Helios Cloud sample data only -- never anything personal),
ingests them into a throwaway store, asserts the whole pipeline, and
smoke-tests the live dashboard + JSON API on localhost.

Asserts internally, so the demo doubles as a smoke test:

  1. artifact generation is deterministic (byte-identical md5 twice)
  2. all 18 runs ingest; re-ingesting changes nothing (idempotent)
  3. fleet rolls up to "critical" (the validator regressed: 0.80 pass rate)
  4. trends match the story: red-team improving, validator declining,
     replay steady, firewall steady, anomaly steady, synthesizer declining
  5. every finding on the latest validator run carries an evidence quote
  6. the live server answers / , /api/status and /api/run/<id>

Run:  python3 demo.py
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import urllib.request
from http.server import HTTPServer

import fixtures
from dashboard import render_fleet
from health import check_exit_code, fleet_health, project_health
from server import make_handler
from store import Store, canonical


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _get(url: str):
    import urllib.error

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main(smoke_serve: bool = True) -> None:
    # 1. deterministic artifacts -------------------------------------------------
    runs_a = fixtures.make_all()
    runs_b = fixtures.make_all()
    md5_a = _md5(canonical(runs_a))
    md5_b = _md5(canonical(runs_b))
    assert md5_a == md5_b, (md5_a, md5_b)
    assert len(runs_a) == 18
    assert all(r["simulated"] for r in runs_a)
    print(f"artifacts: {len(runs_a)} runs, md5={md5_a} (byte-identical replay)")

    # 2. ingest, idempotent ------------------------------------------------------
    with tempfile.TemporaryDirectory(prefix="evaldash-demo-") as tmp:
        store = Store(tmp)
        for env in runs_a:
            store.ingest(env)
        assert len(store.manifest()) == 18, len(store.manifest())
        md5_store_1 = store.store_md5()
        for env in runs_a:  # re-ingest: must not change a single byte
            store.ingest(env)
        assert store.store_md5() == md5_store_1, "ingest is not idempotent"
        print(f"ingest: 18/18 runs, re-ingest byte-identical (store md5={md5_store_1[:12]}...)")

        # 3. fleet health --------------------------------------------------------
        fleet = fleet_health(store)
        assert fleet["n_tools"] == 6 and fleet["n_runs"] == 18
        assert fleet["status"] == "critical", fleet["status"]
        assert check_exit_code(fleet) == 2
        print(f"fleet: {fleet['status']} (check exit 2)")

        # 4. trends --------------------------------------------------------------
        trends = {p["tool"]: p["trend"] for p in fleet["projects"]}
        expected = {
            "ai-red-teaming-harness": "improving",
            "tool-call-trace-replay": "steady",
            "trace-anomaly-detector": "steady",
            "structured-output-validator": "declining",
            "prompt-injection-firewall": "steady",
            "adversarial-prompt-synthesizer": "declining",
        }
        assert trends == expected, trends
        statuses = {p["tool"]: p["status"] for p in fleet["projects"]}
        assert statuses["structured-output-validator"] == "critical"
        assert statuses["ai-red-teaming-harness"] == "green"
        assert statuses["prompt-injection-firewall"] == "green"
        print("trends: " + ", ".join(f"{t.split('-')[0]}={tr}" for t, tr in trends.items()))

        # 5. evidence quotes on every finding ------------------------------------
        latest = store.get("structured-output-validator-r2")
        assert len(latest["findings"]) == 3
        assert all(f["evidence"].strip() for f in latest["findings"])
        html = render_fleet(fleet, simulated=True)
        assert "SIMULATED DATA" in html
        assert "fleet: critical" in html
        assert html.count("&ldquo;") >= len(latest["findings"])
        print(f"evidence: validator-r2 has {len(latest['findings'])} findings, all with quotes")

        # 6. live server smoke test ----------------------------------------------
        if smoke_serve:
            handler = make_handler(tmp, simulated=True)
            httpd = HTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{port}"
                code, page = _get(base + "/")
                assert code == 200 and "fleet: critical" in page, code
                code, body = _get(base + "/api/status")
                assert code == 200
                status = json.loads(body)
                assert status["status"] == "critical" and status["n_tools"] == 6
                code, body = _get(base + "/api/run/ai-red-teaming-harness-r2")
                assert code == 200 and json.loads(body)["headline"] == 1.0
                code, _ = _get(base + "/api/runs")
                assert code == 200
                code, body = _get(base + "/api/run/nope")
                assert code == 404, code
                print(f"serve: live server OK on :{port} (/, /api/status, /api/run/<id>, 404 path)")
            finally:
                httpd.shutdown()
                thread.join()

    print("\ndemo OK: deterministic artifacts -> idempotent ingest -> fleet "
          "health -> live dashboard")


if __name__ == "__main__":
    main()
