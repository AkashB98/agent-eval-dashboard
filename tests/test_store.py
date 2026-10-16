"""Store unit tests: idempotency, determinism, manifest ordering."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from store import Store, artifact_sha, canonical  # noqa: E402


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="evaldash-test-")
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)

    def test_ingest_all_and_manifest_order(self):
        for env in fixtures.make_all():
            self.store.ingest(env)
        manifest = self.store.manifest()
        self.assertEqual(len(manifest), 18)
        keys = [(r["tool"], r["ts"], r["run_id"]) for r in manifest]
        self.assertEqual(keys, sorted(keys))

    def test_idempotent_reingest(self):
        for env in fixtures.make_all():
            self.store.ingest(env)
        md5_before = self.store.store_md5()
        for env in fixtures.make_all():
            self.store.ingest(env)
        self.assertEqual(self.store.store_md5(), md5_before)
        self.assertEqual(len(self.store.manifest()), 18)

    def test_run_id_derived_when_missing(self):
        env = fixtures.make_run("prompt-injection-firewall", 0)
        del env["run_id"]
        expected = artifact_sha(env)
        s = self.store.ingest(env)
        self.assertEqual(s["run_id"], expected)
        # derived id is stable across ingest calls
        s2 = self.store.ingest(env)
        self.assertEqual(s2["run_id"], expected)
        self.assertEqual(len(self.store.manifest()), 1)

    def test_canonical_is_sorted_and_stable(self):
        a = canonical({"b": 1, "a": {"z": 2, "y": 1}})
        b = canonical({"a": {"y": 1, "z": 2}, "b": 1})
        self.assertEqual(a, b)
        self.assertTrue(a.index('"a"') < a.index('"b"'))

    def test_run_files_are_canonical_json(self):
        env = fixtures.make_run("ai-red-teaming-harness", 2)
        s = self.store.ingest(env)
        path = os.path.join(self.tmp.name, "runs", f"{s['run_id']}.json")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertEqual(raw, canonical(json.loads(raw)) + "\n")

    def test_get_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.store.get("nope")

    def test_runs_for_oldest_first(self):
        for i in (2, 0, 1):  # out of order ingest
            self.store.ingest(fixtures.make_run("structured-output-validator", i))
        runs = self.store.runs_for("structured-output-validator")
        self.assertEqual([r["run_id"] for r in runs],
                         [f"structured-output-validator-r{i}" for i in (0, 1, 2)])

    def test_empty_manifest(self):
        self.assertEqual(self.store.manifest(), [])


if __name__ == "__main__":
    unittest.main()
