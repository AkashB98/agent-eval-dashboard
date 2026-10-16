"""No-network enforcement: core flows work with sockets stubbed out.

Nothing in fixtures/adapters/store/health/dashboard/cli/demo may touch the
network. We stub socket.socket and socket.create_connection to raise, then
run the full pipeline in-process. (The `serve` command is the only network
surface; it is smoke-tested by demo.py's live-server check, not in the suite.)
"""

import io
import os
import socket
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fixtures  # noqa: E402
from health import fleet_health  # noqa: E402
from store import Store  # noqa: E402


def _raising_socket(*args, **kwargs):
    raise AssertionError("network socket used during hermetic test")


class TestNoNetwork(unittest.TestCase):
    def test_full_pipeline_with_sockets_stubbed(self):
        with mock.patch.object(socket, "socket", _raising_socket), \
             mock.patch.object(socket, "create_connection", _raising_socket):
            import tempfile

            store = Store(tempfile.mkdtemp(prefix="evaldash-test-"))
            for env in fixtures.make_all():
                store.ingest(env)
            fleet = fleet_health(store)
            self.assertEqual(fleet["status"], "critical")
            self.assertEqual(fleet["n_runs"], 18)

    def test_demo_with_sockets_stubbed(self):
        with mock.patch.object(socket, "socket", _raising_socket), \
             mock.patch.object(socket, "create_connection", _raising_socket):
            import demo

            buf = io.StringIO()
            with redirect_stdout(buf):
                demo.main(smoke_serve=False)
            self.assertIn("demo OK", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
