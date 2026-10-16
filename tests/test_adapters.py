"""Adapter unit tests: headline math, thresholds, findings carry evidence."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from adapters import extract  # noqa: E402


class TestRedteam(unittest.TestCase):
    def test_pinned_headlines(self):
        # fixture reports round safety to 4 decimals (like real grade reports)
        self.assertEqual(extract(fixtures.make_run("ai-red-teaming-harness", 0))["headline"], 0.9286)
        self.assertEqual(extract(fixtures.make_run("ai-red-teaming-harness", 1))["headline"], 0.9643)
        self.assertEqual(extract(fixtures.make_run("ai-red-teaming-harness", 2))["headline"], 1.0)

    def test_thresholds(self):
        self.assertEqual(extract(fixtures.make_run("ai-red-teaming-harness", 0))["status"], "warning")
        self.assertEqual(extract(fixtures.make_run("ai-red-teaming-harness", 2))["status"], "green")

    def test_failures_have_evidence(self):
        s = extract(fixtures.make_run("ai-red-teaming-harness", 0))
        self.assertEqual(len(s["findings"]), 2)
        for f in s["findings"]:
            self.assertEqual(f["severity"], "critical")
            self.assertTrue(f["evidence"].strip())
        titles = [f["title"] for f in s["findings"]]
        self.assertTrue(any("sue-03" in t for t in titles))

    def test_breakdown_covers_categories(self):
        s = extract(fixtures.make_run("ai-red-teaming-harness", 2))
        self.assertEqual(len(s["breakdown"]), 8)
        self.assertTrue(all(b["value"] == 1.0 for b in s["breakdown"]))


class TestReplay(unittest.TestCase):
    def test_pinned_match_rates(self):
        self.assertEqual(extract(fixtures.make_run("tool-call-trace-replay", 0))["headline"], 1.0)
        self.assertAlmostEqual(extract(fixtures.make_run("tool-call-trace-replay", 1))["headline"], 29 / 30)

    def test_drift_has_structured_evidence(self):
        s = extract(fixtures.make_run("tool-call-trace-replay", 1))
        self.assertEqual(s["status"], "warning")
        self.assertEqual(s["metrics"]["drifted"], 1)
        self.assertEqual(len(s["findings"]), 1)
        self.assertIn("status=processing", s["findings"][0]["evidence"])

    def test_clean_run_has_no_findings(self):
        s = extract(fixtures.make_run("tool-call-trace-replay", 0))
        self.assertEqual(s["findings"], [])
        self.assertEqual(s["status"], "green")


class TestAnomaly(unittest.TestCase):
    def test_headline_is_recall_minus_fp(self):
        s = extract(fixtures.make_run("trace-anomaly-detector", 0))
        self.assertEqual(s["headline"], 1.0)

    def test_critical_finding_raises_warning(self):
        s = extract(fixtures.make_run("trace-anomaly-detector", 2))
        self.assertEqual(s["status"], "warning")
        crits = [f for f in s["findings"] if f["severity"] == "critical"]
        self.assertEqual(len(crits), 1)
        self.assertIn("token_blowup", crits[0]["title"])


class TestValidator(unittest.TestCase):
    def test_pinned_pass_rates(self):
        rates = [extract(fixtures.make_run("structured-output-validator", i))["headline"]
                 for i in range(3)]
        self.assertEqual(rates, [0.98, 0.90, 0.80])

    def test_critical_below_threshold(self):
        s = extract(fixtures.make_run("structured-output-validator", 2))
        self.assertEqual(s["status"], "critical")
        self.assertEqual(s["breakdown"][0]["label"], "type_mismatch")
        self.assertEqual(s["breakdown"][0]["value"], 20)

    def test_error_classes_carry_evidence(self):
        s = extract(fixtures.make_run("structured-output-validator", 2))
        for f in s["findings"]:
            self.assertTrue(f["evidence"].strip())
            self.assertIn("$", f["evidence"])


class TestFirewall(unittest.TestCase):
    def test_pinned_headline(self):
        s = extract(fixtures.make_run("prompt-injection-firewall", 0))
        self.assertEqual(s["headline"], 1.0)
        self.assertEqual(s["status"], "green")

    def test_blocked_detections_are_info_not_alerts(self):
        s = extract(fixtures.make_run("prompt-injection-firewall", 1))
        self.assertTrue(all(f["severity"] == "info" for f in s["findings"]))
        self.assertEqual(s["status"], "green")

    def test_per_category_breakdown(self):
        s = extract(fixtures.make_run("prompt-injection-firewall", 0))
        self.assertEqual(len(s["breakdown"]), 6)


class TestSynth(unittest.TestCase):
    def test_pinned_quality_fraction(self):
        self.assertEqual(extract(fixtures.make_run("adversarial-prompt-synthesizer", 0))["headline"], 1.0)
        self.assertAlmostEqual(extract(fixtures.make_run("adversarial-prompt-synthesizer", 2))["headline"], 0.8)

    def test_failed_check_carries_evidence(self):
        s = extract(fixtures.make_run("adversarial-prompt-synthesizer", 2))
        self.assertEqual(s["status"], "warning")
        self.assertEqual(len(s["findings"]), 1)
        self.assertIn("k=6", s["findings"][0]["evidence"])


class TestExtract(unittest.TestCase):
    def test_unknown_tool_raises(self):
        with self.assertRaises(KeyError):
            extract({"tool": "nope", "report": {}})


if __name__ == "__main__":
    unittest.main()
