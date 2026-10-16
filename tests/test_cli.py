"""CLI tests: ingest / list / summary / check against a temp store."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from cli import main  # noqa: E402


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="evaldash-test-")
        self.addCleanup(self.tmp.cleanup)
        self.store = os.path.join(self.tmp.name, "store")
        self.art = os.path.join(self.tmp.name, "art.json")
        with open(self.art, "w", encoding="utf-8") as fh:
            json.dump(fixtures.make_run("prompt-injection-firewall", 0), fh)

    def _run(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--store", self.store, *argv])
        return code, buf.getvalue()

    def test_ingest_then_list(self):
        code, out = self._run("ingest", self.art)
        self.assertEqual(code, 0)
        self.assertIn("prompt-injection-firewall-r0", out)
        code, out = self._run("list")
        self.assertEqual(code, 0)
        self.assertIn("prompt-injection-firewall-r0", out)

    def test_summary(self):
        self._run("ingest", self.art)
        code, out = self._run("summary")
        self.assertEqual(code, 0)
        self.assertIn("fleet: all-green", out)

    def test_check_all_green(self):
        self._run("ingest", self.art)
        code, _ = self._run("check")
        self.assertEqual(code, 0)

    def test_check_critical(self):
        bad = os.path.join(self.tmp.name, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump(fixtures.make_run("structured-output-validator", 2), fh)
        self._run("ingest", bad)
        code, out = self._run("check")
        self.assertEqual(code, 2)
        self.assertIn("fleet: critical", out)

    def test_check_project_scoped(self):
        self._run("ingest", self.art)
        code, _ = self._run("check", "--project", "prompt-injection-firewall")
        self.assertEqual(code, 0)

    def test_check_unknown_project(self):
        code, _ = self._run("check", "--project", "nope")
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
