"""Regression tests for the production audit hardening.

Covers the findings that can be asserted without an HTTP client (CI installs
with ``--no-http``):

* H1 - an unknown login is reported as unknown, and the dummy hash really is a
  password hash (the cost is what closes the timing oracle).
* H2 - ``reset_password`` never raises, whatever the login.
* H3 - the throttle counters are committed, so they survive the rollback of the
  request that recorded them and are shared by every worker.
* M3 / L4 - the header and cookie hardening helpers keep their contract.

Note on reading committed counters: Odoo opens every connection at
``REPEATABLE READ`` (``odoo/sql_db.py``), so a test transaction that has already
read the throttle table keeps its snapshot and cannot observe the counter the
isolated cursor commits. Assertions about committed counters therefore go
through a cursor of their own - which is what the next request does in
production.
"""

import time

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessDenied
from odoo.tests import TransactionCase, tagged

THROTTLE_TABLE = "thirdcode_auth_throttle"
IP_SCOPE = "login-ip"


@tagged("post_install", "-at_install")
class TestAuthThrottle(TransactionCase):
    """H3 - a shared, database-backed login cooldown."""

    def setUp(self):
        super().setUp()
        self.limiter = self.env["thirdcode.auth.throttle"].sudo()
        self._clear_counters()

    def tearDown(self):
        self._clear_counters()
        super().tearDown()

    def _clear_counters(self):
        # The counters are committed on a cursor of their own, so the rollback
        # that ends a test would leave them behind.
        with self.env.registry.cursor() as cr:
            cr.execute("DELETE FROM %s" % THROTTLE_TABLE)
            cr.commit()

    def _counter_row(self, key, scope):
        """Read the counter over a connection that sees committed data only."""
        query = "SELECT failures, blocked_until FROM %s WHERE key = %%s AND scope = %%s" % (
            THROTTLE_TABLE,
        )
        with self.env.registry.cursor() as cr:
            cr.execute(query, (key, scope))
            return cr.fetchone()

    def _committed_blocked_seconds(self, key, scope):
        """The cooldown as the next request would compute it."""
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            return env["thirdcode.auth.throttle"]._tcsi_blocked_seconds(key, scope)

    def test_failure_counter_is_committed(self):
        self.limiter._tcsi_register_failure("203.0.113.7", IP_SCOPE, 3, 3600, 900)
        row = self._counter_row("203.0.113.7", IP_SCOPE)
        self.assertIsNotNone(row, "the counter must survive the recording transaction")
        self.assertEqual(row[0], 1)

    def test_counter_blocks_once_the_limit_is_reached(self):
        for _ in range(2):
            self.limiter._tcsi_register_failure("203.0.113.8", IP_SCOPE, 3, 3600, 900)
        self.assertEqual(self._committed_blocked_seconds("203.0.113.8", IP_SCOPE), 0)

        self.limiter._tcsi_register_failure("203.0.113.8", IP_SCOPE, 3, 3600, 900)
        self.assertGreater(self._committed_blocked_seconds("203.0.113.8", IP_SCOPE), 0)
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            with self.assertRaises(AccessDenied):
                env["thirdcode.auth.throttle"]._tcsi_assert_allowed([("203.0.113.8", IP_SCOPE)])

    def test_success_clears_the_counter(self):
        self.limiter._tcsi_register_failure("203.0.113.9", IP_SCOPE, 3, 3600, 900)
        self.limiter._tcsi_register_success("203.0.113.9", IP_SCOPE)
        self.assertIsNone(self._counter_row("203.0.113.9", IP_SCOPE))
        self.assertEqual(self._committed_blocked_seconds("203.0.113.9", IP_SCOPE), 0)

    def test_observation_window_restarts_the_count(self):
        # Seed a counter whose window has already elapsed, on a committed
        # connection so the isolated counter update can see it.
        with self.env.registry.cursor() as cr:
            cr.execute(
                "INSERT INTO %s (key, scope, failures, first_failure, last_failure)"
                " VALUES (%%s, %%s, 9, now() - interval '2 hours', now())"
                % THROTTLE_TABLE,
                ("203.0.113.11", IP_SCOPE),
            )
            cr.commit()
        failures = self.limiter._tcsi_register_failure("203.0.113.11", IP_SCOPE, 3, 60, 900)
        self.assertEqual(failures, 1)

    def test_disabled_limit_records_nothing(self):
        self.assertEqual(self.limiter._tcsi_register_failure("203.0.113.12", IP_SCOPE, 0, 60, 900), 0)
        self.assertIsNone(self._counter_row("203.0.113.12", IP_SCOPE))


@tagged("post_install", "-at_install")
class TestLoginTimingOracle(TransactionCase):
    """H1 - an unknown account must not be cheaper to probe than a known one."""

    def setUp(self):
        super().setUp()
        self.users = self.env["res.users"]

    def test_unknown_login_is_reported_as_absent(self):
        self.assertFalse(self.users._tcsi_login_exists(self.env.cr.dbname, "nobody-here@example.com"))

    def test_known_login_is_reported_as_present(self):
        # The helper resolves accounts over a cursor of its own, like
        # res.users._login, so the probe has to use a committed account: a user
        # created inside this transaction is invisible to another connection.
        with self.env.registry.cursor() as cr:
            cr.execute(
                "SELECT u.login, p.email FROM res_users u"
                " JOIN res_partner p ON p.id = u.partner_id"
                " WHERE u.active ORDER BY u.id LIMIT 1"
            )
            row = cr.fetchone()
        self.assertIsNotNone(row, "the test database must hold a committed active user")
        self.assertTrue(self.users._tcsi_login_exists(self.env.cr.dbname, row[0]))
        if row[1]:
            self.assertTrue(self.users._tcsi_login_exists(self.env.cr.dbname, row[1]))

    def test_dummy_hash_costs_a_real_hash(self):
        started = time.monotonic()
        self.users._tcsi_burn_password_hash("not-the-password")
        self.assertGreater(
            time.monotonic() - started,
            0.001,
            "the dummy credential check must do real work, otherwise the oracle stays open",
        )


@tagged("post_install", "-at_install")
class TestPasswordResetDisclosure(TransactionCase):
    """H2 - the reset endpoint answers the same way for every login."""

    def test_unknown_login_does_not_raise(self):
        self.assertFalse(self.env["res.users"].reset_password("nobody-here@example.com"))

    def test_user_without_email_does_not_raise(self):
        user = self.env["res.users"].create(
            {"name": "Reset Probe", "login": "tcsi-reset-probe", "email": False}
        )
        self.env["res.users"].reset_password(user.login)


@tagged("post_install", "-at_install")
class TestHttpHardeningHelpers(TransactionCase):
    """M3 - the header and cookie hardening keep their contract."""

    def test_session_cookie_is_forced_secure(self):
        hardened = self.env["ir.http"]._tcsi_harden_cookie_value("session_id=abc; HttpOnly")
        self.assertIn("Secure", hardened)
        self.assertIn("SameSite=Lax", hardened)
        self.assertEqual(hardened.count("HttpOnly"), 1)

    def test_other_cookies_are_left_alone(self):
        self.assertEqual(
            self.env["ir.http"]._tcsi_harden_cookie_value("cids=1-2-3; Path=/"), "cids=1-2-3; Path=/"
        )

    def test_security_headers_are_declared(self):
        from odoo.addons.thirdcode_accounting.models import ir_http

        names = {name for name, _value in ir_http.SECURITY_HEADERS}
        self.assertIn("Referrer-Policy", names)
        self.assertIn("X-Content-Type-Options", names)
        self.assertIn("Permissions-Policy", names)

    def test_database_manager_is_denied_by_default(self):
        self.assertFalse(self.env["ir.http"]._tcsi_db_manager_allowed())
