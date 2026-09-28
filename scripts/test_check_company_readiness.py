"""Regression checks for the live company structural preflight."""

import unittest

from check_company_readiness import check_company


class CompanyReadinessTests(unittest.TestCase):
    def setUp(self):
        self.company = {
            "id": 1,
            "name": "Example company",
            "country_id": [174, "Philippines"],
            "currency_id": [35, "PHP"],
            "vat": "approved-identifier",
            "company_registry": False,
            "thirdcode_bir_ack_approved": True,
            "thirdcode_bir_ack_control_number": "approved-control",
            "thirdcode_eis_status": "not_in_scope",
            "thirdcode_report_samples_approved": True,
            "thirdcode_backup_owner": "Assigned owner",
            "thirdcode_restore_owner": "Assigned owner",
        }

    @staticmethod
    def call(model, method, args, kwargs):
        if method == "search_count":
            return 1
        if model == "res.country" and method == "read":
            return [{"code": "PH"}]
        if model == "res.currency" and method == "read":
            return [{"name": "PHP"}]
        raise AssertionError(f"Unexpected preflight call: {model}.{method}")

    def test_configured_identity_and_approved_codes_pass(self):
        result = check_company(self.call, self.company, "2026-09-28", "PH", "PHP")
        self.assertTrue(result["structurally_ready"])
        self.assertEqual(result["identity"]["currency_code"], "PHP")

    def test_missing_identity_or_wrong_currency_blocks_readiness(self):
        company = {**self.company, "country_id": False, "vat": False}
        result = check_company(self.call, company, "2026-09-28", "PH", "USD")
        self.assertFalse(result["structurally_ready"])
        self.assertFalse(result["checks"]["country_recorded"])
        self.assertFalse(result["checks"]["legal_identifier_recorded"])
        self.assertFalse(result["checks"]["expected_country"])
        self.assertFalse(result["checks"]["expected_currency"])


if __name__ == "__main__":
    unittest.main()
