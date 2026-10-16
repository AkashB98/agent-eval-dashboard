"""Dashboard tests: content, HTML escaping, deterministic render."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from dashboard import render_fleet, render_run  # noqa: E402
from health import fleet_health  # noqa: E402
from store import Store  # noqa: E402


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="evaldash-test-")
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        for env in fixtures.make_all():
            self.store.ingest(env)
        self.fleet = fleet_health(self.store)

    def test_render_contains_fleet_state(self):
        page = render_fleet(self.fleet, simulated=True)
        self.assertIn("fleet: critical", page)
        self.assertIn("SIMULATED DATA", page)
        self.assertIn("agent-eval-dashboard", page)
        for tool in fixtures.TOOLS:
            self.assertIn(tool, page)

    def test_render_is_deterministic(self):
        a = render_fleet(self.fleet, simulated=True)
        b = render_fleet(self.fleet, simulated=True)
        self.assertEqual(a, b)

    def test_evidence_quotes_rendered(self):
        page = render_fleet(self.fleet, simulated=True)
        self.assertIn("&ldquo;", page)
        self.assertIn("status=processing", page)

    def test_sparkline_present(self):
        page = render_fleet(self.fleet, simulated=True)
        self.assertIn("<svg", page)
        self.assertIn("<polyline", page)

    def test_no_banner_when_not_simulated(self):
        page = render_fleet(self.fleet, simulated=False)
        self.assertNotIn("SIMULATED DATA", page)

    def test_html_escaping(self):
        summary = {
            "tool": "x", "run_id": "r1", "ts": "t",
            "headline": 1.0, "headline_label": "s",
            "metrics": {}, "status": "green",
            "findings": [{"severity": "high", "title": "<script>alert(1)</script>",
                          "evidence": "a & b"}],
        }
        page = render_run(summary)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("a &amp; b", page)

    def test_render_run_page(self):
        s = self.store.get("structured-output-validator-r2")
        page = render_run(s)
        self.assertIn("structured-output-validator-r2", page)
        self.assertIn("type_mismatch", page)


if __name__ == "__main__":
    unittest.main()
