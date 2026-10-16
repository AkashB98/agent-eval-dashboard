"""Health model tests: trends, fleet roll-up, CI exit codes, alerts."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from adapters import extract  # noqa: E402
from health import check_exit_code, fleet_health, project_health  # noqa: E402
from store import Store  # noqa: E402


def _summaries(vals, tool="x", status="green"):
    return [
        {"tool": tool, "run_id": f"r{i}", "ts": f"2026-10-{i+1:02d}T00:00:00Z",
         "headline": v, "status": status, "findings": []}
        for i, v in enumerate(vals)
    ]


class TestTrends(unittest.TestCase):
    def test_new_with_one_run(self):
        p = project_health(_summaries([0.9]))
        self.assertEqual(p["trend"], "new")
        self.assertIsNone(p["delta"])

    def test_improving(self):
        p = project_health(_summaries([0.9, 0.95]))
        self.assertEqual(p["trend"], "improving")
        self.assertAlmostEqual(p["delta"], 0.05)

    def test_declining(self):
        p = project_health(_summaries([0.9, 0.85]))
        self.assertEqual(p["trend"], "declining")

    def test_steady_within_eps(self):
        p = project_health(_summaries([0.9, 0.91]))
        self.assertEqual(p["trend"], "steady")

    def test_eps_boundary_is_steady(self):
        p = project_health(_summaries([0.9, 0.92]))
        self.assertEqual(p["trend"], "steady")  # exactly 0.02 -> not improving


class TestFleet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="evaldash-test-")
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        for env in fixtures.make_all():
            self.store.ingest(env)
        self.fleet = fleet_health(self.store)

    def test_fixture_fleet_is_critical(self):
        self.assertEqual(self.fleet["status"], "critical")
        self.assertEqual(check_exit_code(self.fleet), 2)
        self.assertEqual(self.fleet["n_tools"], 6)
        self.assertEqual(self.fleet["n_runs"], 18)

    def test_pinned_trends(self):
        trends = {p["tool"]: p["trend"] for p in self.fleet["projects"]}
        self.assertEqual(trends, {
            "ai-red-teaming-harness": "improving",
            "tool-call-trace-replay": "steady",
            "trace-anomaly-detector": "steady",
            "structured-output-validator": "declining",
            "prompt-injection-firewall": "steady",
            "adversarial-prompt-synthesizer": "declining",
        })

    def test_pinned_alerts(self):
        # validator 3 high + anomaly 1 critical + replay 1 high
        self.assertEqual(len(self.fleet["alerts"]), 5)
        tools = sorted(a["tool"] for a in self.fleet["alerts"])
        self.assertEqual(tools, ["structured-output-validator"] * 3 +
                         ["tool-call-trace-replay", "trace-anomaly-detector"])
        for a in self.fleet["alerts"]:
            self.assertTrue(a["evidence"].strip())

    def test_declining_trend_forces_warning(self):
        # a declining-but-green project still trips fleet warning
        store = Store(tempfile.mkdtemp(prefix="evaldash-test-"))
        for i, v in enumerate([1.0, 0.96]):  # 0.96 stays green, delta -0.04 declines
            env = fixtures.make_run("prompt-injection-firewall", 0)
            env["run_id"] = f"fw-{i}"
            env["ts"] = f"2026-10-{i+1:02d}T00:00:00Z"
            env["report"] = dict(env["report"])
            env["report"]["detection_rate"] = v
            store.ingest(env)
        proj = project_health(store.runs_for("prompt-injection-firewall"))
        self.assertEqual(proj["status"], "green")
        self.assertEqual(proj["trend"], "declining")
        fleet = fleet_health(store)
        self.assertEqual(fleet["status"], "warning")
        self.assertEqual(check_exit_code(fleet), 1)

    def test_all_green_fleet(self):
        store = Store(tempfile.mkdtemp(prefix="evaldash-test-"))
        store.ingest(fixtures.make_run("prompt-injection-firewall", 0))
        fleet = fleet_health(store)
        self.assertEqual(fleet["status"], "all-green")
        self.assertEqual(check_exit_code(fleet), 0)

    def test_empty_store(self):
        fleet = fleet_health(Store(tempfile.mkdtemp(prefix="evaldash-test-")))
        self.assertEqual(fleet["status"], "all-green")
        self.assertEqual(fleet["projects"], [])


if __name__ == "__main__":
    unittest.main()
