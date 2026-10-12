"""Exercise runtime shutdown using real disposable processes, without Odoo or credentials."""
import importlib.util
from contextlib import ExitStack
import pathlib
import signal
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("hosted_runtime", pathlib.Path(__file__).resolve().parents[1] / "docker/odoo/hosted_runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)

START_SPEC = importlib.util.spec_from_file_location("cloud_start", pathlib.Path(__file__).resolve().parents[1] / "docker/odoo/cloud_start.py")
launcher = importlib.util.module_from_spec(START_SPEC)
with mock.patch.dict(sys.modules, {"hosted_runtime": runtime, "psycopg2": mock.MagicMock()}):
    START_SPEC.loader.exec_module(launcher)


class HostedStartupVersionTests(unittest.TestCase):
    def setUp(self):
        patches = self.enterContext(ExitStack())
        patches.enter_context(mock.patch.dict(launcher.os.environ, {
            "PGDATABASE": "tcsi_test", "PGHOST": "test-db", "PGUSER": "test-user",
            "PGPASSWORD": "test-only", "TCSI_ADMIN_LOGIN": "test@example.invalid",
            "TCSI_ADMIN_PASSWORD": "test-only-admin-password-1234",
            "TCSI_MASTER_PASSWORD": "test-only-master-password-1234",
        }, clear=True))
        patches.enter_context(mock.patch.object(launcher.os, "getuid", return_value=1000))
        patches.enter_context(mock.patch.object(launcher.os, "chmod"))
        patches.enter_context(mock.patch.object(launcher.pathlib.Path, "mkdir"))
        patches.enter_context(mock.patch.object(launcher.pathlib.Path, "write_text"))
        patches.enter_context(mock.patch.object(launcher.pathlib.Path, "read_text", return_value="{'version': '18.0.2.15.5'}"))
        config = patches.enter_context(mock.patch.object(launcher.tempfile, "NamedTemporaryFile"))
        config.return_value.__enter__.return_value.name = "/private/test-runtime.conf"
        directory = patches.enter_context(mock.patch.object(launcher.tempfile, "TemporaryDirectory"))
        directory.return_value.__enter__.return_value = "/private/test-proxy"
        connection = patches.enter_context(mock.patch.object(launcher.psycopg2, "connect"))
        self.cursor = connection.return_value.cursor.return_value.__enter__.return_value
        self.run = patches.enter_context(mock.patch.object(launcher.subprocess, "run"))
        self.serve = patches.enter_context(mock.patch.object(launcher, "serve", return_value=0))

    def start(self, version):
        self.cursor.fetchone.side_effect = [(None,)] if version is None else [
            ("ir_module_module",), ("installed", version),
        ]
        launcher.main()

    def test_newer_database_refuses_before_bootstrap_or_runtime_start(self):
        with self.assertRaisesRegex(RuntimeError, "refusing unsafe downgrade"):
            self.start("18.0.2.15.6")
        self.run.assert_not_called()
        self.serve.assert_not_called()

    def test_fresh_equal_and_older_databases_keep_expected_startup(self):
        for version, operation in ((None, "-i"), ("18.0.2.15.5", None), ("18.0.2.15.4", "-u")):
            with self.subTest(version=version):
                self.run.reset_mock()
                self.serve.reset_mock()
                with self.assertRaises(SystemExit) as result:
                    self.start(version)
                self.assertEqual(result.exception.code, 0)
                module_commands = [call.args[0] for call in self.run.call_args_list
                                   if "-i" in call.args[0] or "-u" in call.args[0]]
                self.assertEqual(len(module_commands), int(operation is not None))
                if operation:
                    self.assertIn(operation, module_commands[0])
                    self.assertIn("--stop-after-init", module_commands[0])
                self.assertTrue(any("shell" in call.args[0] for call in self.run.call_args_list))
                self.serve.assert_called_once()


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
