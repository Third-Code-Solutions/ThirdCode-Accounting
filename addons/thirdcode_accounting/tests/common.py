"""Fixture provisioning uses the installer; business assertions keep real users."""
from odoo.addons.account.tests.common import AccountTestInvoicingCommon as NativeAccountCommon
from odoo.addons.hr_expense.tests.common import TestExpenseCommon as NativeExpenseCommon


class CompanyFixtureProvisioning:
    @classmethod
    def _create_company(cls, **values):
        original_env = cls.env
        try:
            # Native common creates a company before adding it to the fixture
            # user's scope. This is trusted setup, like platform provisioning.
            cls.env = cls.env(su=True)
            company = super()._create_company(**values)
        finally:
            cls.env = original_env
        return company.with_env(original_env)


class AccountTestInvoicingCommon(CompanyFixtureProvisioning, NativeAccountCommon):
    pass


class TestExpenseCommon(CompanyFixtureProvisioning, NativeExpenseCommon):
    pass
