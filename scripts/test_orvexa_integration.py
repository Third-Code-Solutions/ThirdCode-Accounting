"""Run only ORVEXA integration tests after module installation in a disposable DB."""
import sys

import odoo
from odoo.tests.loader import make_suite, run_suite

odoo.tools.config.parse_config(sys.argv[1:])
database = odoo.tools.config["db_name"]
if not database or not database.startswith("tcsi_orvexa_"):
    raise SystemExit("Refusing to run synthetic writes outside a disposable tcsi_orvexa_ database")
odoo.tools.config["test_tags"] = "/thirdcode_accounting:TestOrvexa"
odoo.modules.registry.Registry(database)
suite = make_suite(["thirdcode_accounting"], "post_install")
if suite.countTestCases() < 7:
    raise SystemExit("ORVEXA tests were not discovered")
result = run_suite(suite)
print(f"ORVEXA: {result.testsRun} tests, {result.failures_count} failures, {result.errors_count} errors")
raise SystemExit(0 if result.wasSuccessful() else 1)
