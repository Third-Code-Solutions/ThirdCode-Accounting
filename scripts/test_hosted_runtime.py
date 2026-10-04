"""Exercise runtime shutdown using real disposable processes, without Odoo or credentials."""
import importlib.util
import pathlib
import signal
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("hosted_runtime", pathlib.Path(__file__).resolve().parents[1] / "docker/odoo/hosted_runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class HostedRuntimeTests(unittest.TestCase):
    def test_public_port_cannot_overlap_internal_services(self):
        for port in (0, 80, 8068, 8072, 65536, "8069; stop"):
            with self.assertRaises(ValueError):
                runtime.proxy_config("/tmp/runtime", port)

    def test_process_failure_stops_peer_and_retains_exit_status(self):
        previous = signal.getsignal(signal.SIGTERM)
        with tempfile.TemporaryDirectory() as directory:
            stopped = pathlib.Path(directory) / "stopped"
            peer = "import signal,time,sys; signal.signal(signal.SIGTERM, lambda *args: (open(sys.argv[1], 'w').write('stopped'), sys.exit(0))); time.sleep(30)"
            status = runtime.serve([
                [sys.executable, "-c", peer, str(stopped)],
                [sys.executable, "-c", "import time; time.sleep(0.5); raise SystemExit(7)"],
            ])
            self.assertEqual(status, 7)
            self.assertEqual(stopped.read_text(), "stopped")
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)

    def test_failed_spawn_stops_already_started_peer(self):
        with self.assertRaises(FileNotFoundError):
            runtime.serve([[sys.executable, "-c", "import time; time.sleep(30)"], ["/no-such-tcsi-process"]])


if __name__ == "__main__":
    unittest.main()
