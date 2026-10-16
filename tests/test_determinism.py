"""Determinism tests: same inputs -> byte-identical outputs, every time."""

import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from dashboard import render_fleet  # noqa: E402
from health import fleet_health  # noqa: E402
from store import Store, canonical  # noqa: E402


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class TestDeterminism(unittest.TestCase):
    def test_fixture_generation_byte_identical(self):
        a = _md5(canonical(fixtures.make_all()))
        b = _md5(canonical(fixtures.make_all()))
        self.assertEqual(a, b)

    def test_store_state_byte_identical(self):
        def build():
            tmp = tempfile.mkdtemp(prefix="evaldash-test-")
            store = Store(tmp)
            for env in fixtures.make_all():
                store.ingest(env)
            return store.store_md5()

        self.assertEqual(build(), build())

    def test_fleet_render_byte_identical(self):
        def build():
            tmp = tempfile.mkdtemp(prefix="evaldash-test-")
            store = Store(tmp)
            for env in fixtures.make_all():
                store.ingest(env)
            return render_fleet(fleet_health(store), simulated=True)

        self.assertEqual(build(), build())

    def test_bad_run_id_rejected_deterministically(self):
        with self.assertRaises(ValueError):
            fixtures.make_run("prompt-injection-firewall", 9)
        with self.assertRaises(KeyError):
            fixtures.make_run("nope", 0)


if __name__ == "__main__":
    unittest.main()
