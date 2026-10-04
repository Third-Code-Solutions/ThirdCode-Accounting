"""Regression checks for persisted demo data validation."""

import unittest
from datetime import date

from check_client_demo import confirm_fixture_date


class FixtureDateTests(unittest.TestCase):
    def test_saved_demo_date_does_not_have_to_be_today(self):
        seeded = confirm_fixture_date(None, "2026-09-23", "first invoice")
        self.assertEqual(seeded, date(2026, 9, 23))
        self.assertEqual(confirm_fixture_date(seeded, "2026-09-23", "bill"), seeded)

    def test_mismatched_or_missing_date_fails(self):
        with self.assertRaisesRegex(RuntimeError, "dated differently"):
            confirm_fixture_date(date(2026, 9, 23), "2026-09-24", "bill")
        with self.assertRaisesRegex(RuntimeError, "no invoice date"):
            confirm_fixture_date(None, False, "invoice")
        with self.assertRaisesRegex(RuntimeError, "invalid invoice date"):
            confirm_fixture_date(None, "not-a-date", "invoice")


if __name__ == "__main__":
    unittest.main()
