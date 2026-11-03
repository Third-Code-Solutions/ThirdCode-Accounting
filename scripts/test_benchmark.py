"""Safety and acceptance regressions for the isolated transaction benchmark."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark


class FakeOdoo:
    """RPC boundary fixture with non-US accounts and two accessible companies."""

    def __init__(self, *args):
        self.uid = 11
        self.company_id = None
        self.closed = False
        self.calls = []
        self.fail_post = False
        self.fail_close = False
        self.missing_income = False

    def bind_company(self, company_id):
        if company_id not in (1, 14):
            raise RuntimeError("Company is outside the authenticated user's scope")
        self.company_id = company_id

    def call(self, model, method, args, kwargs=None):
        self.calls.append((model, method, args, kwargs or {}))
        if model == "account.account" and method == "search_read":
            domain = args[0]
            if ("company_ids", "in", [self.company_id]) not in domain:
                raise AssertionError("Account lookup escaped company scope")
            if any(term[0] == "code" for term in domain):
                raise AssertionError("Account codes differ between client charts")
            kind = next(term[2] for term in domain if term[0] == "account_type")
            if kind == "income" and self.missing_income:
                return []
            return [{"id": {"asset_receivable": 501, "liability_payable": 502, "income": 503}[kind]}]
        if model == "account.journal" and method == "search_read":
            if ("company_id", "=", self.company_id) not in args[0]:
                raise AssertionError("Journal lookup escaped company scope")
            return [{"id": 601}]
        if model == "res.partner" and method == "create":
            if args[0]["company_id"] != self.company_id:
                raise AssertionError("Partner escaped company scope")
            return 701
        if model == "account.move" and method == "create":
            return 801
        if model == "account.move" and method == "action_post":
            if self.fail_post:
                raise RuntimeError("Posting denied by accounting control")
            return True
        if model == "account.move" and method == "read":
            return [{"state": "draft"}]
        if model == "account.move" and method == "unlink":
            return True
        raise AssertionError(f"Unexpected RPC: {model}.{method}")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("Session teardown failed")


def arguments(*extra):
    with patch.dict("os.environ", {"ODOO_LOGIN": "benchmark.accountant", "ODOO_PASSWORD": "private-test-value"}):
        return benchmark.parse_args([
            "--database", "tcsi_alignment_test", "--confirm-isolated-database", "tcsi_alignment_test",
            "--company-id", "14", "--iterations", "20", *extra,
        ])


class BenchmarkSafetyTests(unittest.TestCase):
    def test_production_name_or_mismatched_confirmation_blocks_before_authentication(self):
        for database, confirmation in [("tcsi_pilot", "tcsi_pilot"), ("tcsi_alignment_test", "tcsi_alignment_other")]:
            with self.subTest(database=database), patch.object(benchmark, "OdooHttp") as client:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    benchmark.main(["--database", database, "--confirm-isolated-database", confirmation, "--company-id", "1"])
                client.assert_not_called()

    def test_password_must_come_from_environment_and_cannot_be_passed_in_argv(self):
        with patch.dict("os.environ", {}, clear=True), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                benchmark.parse_args(["--database", "tcsi_alignment_test", "--confirm-isolated-database", "tcsi_alignment_test", "--company-id", "1", "--login", "operator"])
        error_output = io.StringIO()
        with contextlib.redirect_stderr(error_output), self.assertRaises(SystemExit):
            arguments("--password", "should-not-appear-in-process-list")
        self.assertNotIn("should-not-appear-in-process-list", error_output.getvalue())

    def test_fixture_uses_company_specific_accounts_and_new_partner_per_run(self):
        client = FakeOdoo()
        client.bind_company(14)
        first = benchmark.prepare_fixture(client, 14, "first-run")
        second = benchmark.prepare_fixture(client, 14, "second-run")
        self.assertEqual(first["income_id"], 503)
        self.assertEqual(second["journal_id"], 601)
        partners = [args[0] for model, method, args, _ in client.calls if model == "res.partner" and method == "create"]
        self.assertEqual([partner["company_id"] for partner in partners], [14, 14])
        self.assertNotEqual(partners[0]["ref"], partners[1]["ref"])
        self.assertFalse(any(model == "res.partner" and method == "search_read" for model, method, _, _ in client.calls))

    def test_incomplete_chart_fails_before_creating_fixture(self):
        client = FakeOdoo()
        client.bind_company(14)
        client.missing_income = True
        with self.assertRaisesRegex(RuntimeError, "income"):
            benchmark.prepare_fixture(client, 14, "missing-chart")
        self.assertFalse(any(method == "create" for _, method, _, _ in client.calls))

    def test_company_outside_membership_blocks_writes_and_closes_session(self):
        client = FakeOdoo()
        result = benchmark.run_benchmark(arguments("--company-id", "99"), client_factory=lambda *args: client)
        self.assertEqual(result["exit_code"], 1)
        self.assertFalse(any(method == "create" for _, method, _, _ in client.calls))
        self.assertTrue(client.closed)

    def test_failed_post_retains_save_sample_cleans_draft_and_ends_session(self):
        client = FakeOdoo()
        client.fail_post = True
        probe = benchmark.run_probe(arguments("--post"), {"partner_id": 701, "income_id": 503, "journal_id": 601}, 0, "failed-post", lambda *args: client)
        self.assertIsNotNone(probe["create_ms"])
        self.assertIsNone(probe["post_ms"])
        self.assertIn("Posting denied", probe["error"])
        self.assertTrue(client.closed)
        self.assertTrue(any(method == "unlink" for _, method, _, _ in client.calls))
        self.assertEqual([x["phase"] for x in probe["rpc_intervals"]], ["create", "post"])
        self.assertEqual([x["succeeded"] for x in probe["rpc_intervals"]], [True, False])
        self.assertIsNone(probe["post_ms"])

    def test_rpc_overlap_counts_simultaneous_calls_without_calling_it_server_queue(self):
        intervals = [
            {"rpc_intervals": [{"start_s": 1, "end_s": 3}, {"start_s": 3, "end_s": 4}]},
            {"rpc_intervals": [{"start_s": 2, "end_s": 3}, {"start_s": 5, "end_s": 5}]},
        ]
        self.assertEqual(benchmark.peak_rpc_overlap(intervals), 2)
        self.assertEqual(benchmark.peak_rpc_overlap([intervals[0]]), 1)
        probe = {"create_ms": 10, "post_ms": None, "error": None, "cleanup_errors": [],
                 "client_executor_wait_ms": 900, **intervals[0]}
        report = benchmark.build_report(arguments(), [probe], [])
        self.assertEqual(report["save"]["p95_ms"], 10)
        self.assertEqual(report["client_executor_wait"]["p95_ms"], 900)
        self.assertIsNone(report["server_queue_measurement"])
        self.assertEqual(report["samples"], [probe])

    def test_session_cleanup_failure_remains_visible(self):
        client = FakeOdoo()
        client.fail_close = True
        probe = benchmark.run_probe(arguments("--post"), {"partner_id": 701, "income_id": 503, "journal_id": 601}, 0, "close-failure", lambda *args: client)
        self.assertIn("Session teardown failed", probe["cleanup_errors"][0])

    def test_nearest_rank_p95_and_empty_samples_do_not_report_false_zero(self):
        self.assertEqual(benchmark.percentile(list(range(1, 101)), .95), 95)
        self.assertEqual(benchmark.percentile(list(range(1, 13)), .95), 12)
        self.assertIsNone(benchmark.summary([])["p95_ms"])

    def test_native_rpc_company_context_cannot_be_overridden_by_call_arguments(self):
        replies = [{"result": {"uid": 11}}, {"result": [{"company_ids": [1, 14]}]}, {"result": []}, {"result": None}]
        with patch.object(benchmark.OdooHttp, "_request", side_effect=replies) as request:
            client = benchmark.OdooHttp("http://localhost:8069", "tcsi_alignment_test", "operator", "secret")
            client.bind_company(14)
            client.call("account.move", "search_read", [[]], {"context": {"allowed_company_ids": [1], "lang": "en_US"}})
            sent = request.call_args.args[1]
            self.assertEqual(sent["kwargs"]["context"], {"allowed_company_ids": [14], "lang": "en_US"})
            client.close()
            self.assertEqual(request.call_args.args, ("/web/session/destroy", {}))

    def test_native_rpc_rejects_company_outside_actual_user_membership(self):
        replies = [{"result": {"uid": 11}}, {"result": [{"company_ids": [1]}]}, {"result": None}]
        with patch.object(benchmark.OdooHttp, "_request", side_effect=replies) as request:
            client = benchmark.OdooHttp("http://localhost:8069", "tcsi_alignment_test", "operator", "secret")
            with self.assertRaisesRegex(RuntimeError, "outside"):
                client.bind_company(14)
            self.assertIsNone(client.company_id)
            self.assertEqual(request.call_count, 2)
            client.close()

    def test_main_keeps_failed_threshold_evidence_and_returns_failure(self):
        result = {"status": "TARGET_MISSED", "exit_code": 2, "save": {"p95_ms": 2300}}
        with tempfile.TemporaryDirectory() as folder, patch.object(benchmark, "run_benchmark", return_value=result):
            args = arguments()
            args.output = str(Path(folder) / "failed-run.json")
            with patch.object(benchmark, "parse_args", return_value=args), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(benchmark.main([]), 2)
            self.assertEqual(json.loads(Path(args.output).read_text()), result)

    def test_all_concurrent_probes_and_setup_sessions_close_on_success(self):
        clients = []

        def factory(*args):
            client = FakeOdoo()
            clients.append(client)
            return client

        result = benchmark.run_benchmark(arguments("--post"), client_factory=factory)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["attempted_iterations"], 20)
        self.assertEqual(result["actor_uid"], 11)
        self.assertEqual(len(clients), 21)
        self.assertTrue(all(client.closed for client in clients))
        self.assertEqual(len(result["samples"]), 20)
        self.assertTrue(all(item["client_executor_wait_ms"] >= 0 for item in result["samples"]))
        self.assertTrue(all(len(item["rpc_intervals"]) == 2 for item in result["samples"]))

    def test_threshold_equality_fails_and_insufficient_sample_is_distinct(self):
        args = arguments("--iterations", "20")
        probes = [{"create_ms": 2000, "post_ms": None, "error": None, "cleanup_errors": []} for _ in range(20)]
        failed = benchmark.build_report(args, probes, [])
        self.assertEqual(failed["exit_code"], 2)
        self.assertFalse(failed["target_observed"]["save_p95_within_target"])
        insufficient = benchmark.build_report(args, [{**probes[0], "create_ms": 10}], [])
        self.assertEqual(insufficient["exit_code"], 3)
        self.assertFalse(insufficient["accepted"])

    def test_failed_requests_never_disappear_from_successful_latency_summary(self):
        args = arguments("--post")
        probes = [{"create_ms": 100, "post_ms": 50, "error": None, "cleanup_errors": []} for _ in range(19)]
        probes.append({"create_ms": 120, "post_ms": None, "error": "posting failed", "cleanup_errors": []})
        result = benchmark.build_report(args, probes, [])
        self.assertEqual(result["save"]["count"], 20)
        self.assertEqual(result["post"]["count"], 19)
        self.assertEqual(result["failed_iterations"], 1)
        self.assertEqual(result["failure_rate"], .05)
        self.assertEqual(result["exit_code"], 1)
        self.assertFalse(result["accepted"])


if __name__ == "__main__":
    unittest.main()
