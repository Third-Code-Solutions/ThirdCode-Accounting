import ast
import json
import re

from lxml import html
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestTrialBalanceSources(AccountTestInvoicingCommon):
    def _entry(self, date, amount, journal=None, partner=None, posted=True):
        move = self.env["account.move"].create({
            "date": date, "journal_id": (journal or self.company_data["default_journal_misc"]).id,
            "line_ids": [
                Command.create({"account_id": self.company_data["default_account_receivable"].id,
                    "partner_id": (partner or self.partner_a).id, "debit": amount}),
                Command.create({"account_id": self.company_data["default_account_revenue"].id,
                    "partner_id": (partner or self.partner_a).id, "credit": amount}),
            ],
        })
        if posted:
            move.action_post()
        return move

    def test_rendered_amount_links_reconcile_to_filtered_sources(self):
        before = self._entry("2024-12-15", 10)
        opening = self._entry("2025-01-20", 20)
        activity = self._entry("2025-06-15", 30)
        excluded = self._entry("2025-06-15", 40, journal=self.company_data["default_journal_sale"])
        excluded |= self._entry("2025-06-15", 50, partner=self.partner_b)
        excluded |= self._entry("2025-07-01", 60)
        excluded |= self._entry("2025-06-15", 70, posted=False)
        wizard = self.env["trial.balance.report.wizard"].create({
            "company_id": self.env.company.id, "date_from": "2025-06-01", "date_to": "2025-06-30",
            "journal_ids": [Command.set(self.company_data["default_journal_misc"].ids)],
            "partner_ids": [Command.set(self.partner_a.ids)], "target_move": "posted",
        })
        for accounts in ([], self.company_data["default_account_revenue"].ids):
            wizard.account_ids = [Command.set(accounts)]
            # Round-trip matches dates/options supplied by the web report client.
            data = json.loads(json.dumps(wizard._prepare_report_data(), default=str))
            values = self.env["report.account_financial_report.trial_balance"]._get_report_values([], data)
            revenue_id = self.company_data["default_account_revenue"].id
            self.assertEqual(values["total_amount"][revenue_id]["initial_balance"], -20)
            self.assertEqual(values["total_amount"][revenue_id]["ending_balance"], -50)
            document, _format = self.env["ir.actions.report"]._render_qweb_html(
                "account_financial_report.trial_balance", wizard.ids, data=data)
            links = html.fromstring(document).xpath("//span[@res-model='account.move.line'][@domain]")
            self.assertGreaterEqual(len(links), 5)
            sources = self.env["account.move"]
            for link in links:
                domain = ast.literal_eval(link.attrib["domain"])
                lines = self.env["account.move.line"].search(domain)
                sources |= lines.move_id
                self.assertFalse(lines.move_id & excluded, str(domain))
                displayed = float(re.sub(r"[^0-9.\-]", "", "".join(link.itertext())))
                metric = "debit" if any(term[0] == "debit" for term in domain if isinstance(term, tuple)) else "credit" if any(term[0] == "credit" for term in domain if isinstance(term, tuple)) else "balance"
                self.assertAlmostEqual(sum(lines.mapped(metric)), displayed, places=2)
            self.assertIn(opening, sources)
            self.assertIn(activity, sources)
            if not accounts:
                self.assertIn(before, sources)
            else:
                self.assertNotIn(before, sources)

    def test_html_export_rechecks_active_company(self):
        wizard = self.env["trial.balance.report.wizard"].create({"company_id": self.env.company.id})
        other = self.env["res.company"].create({"name": "Inactive report company"})
        wizard.company_id = other
        self.assertNotIn(other.id, wizard.with_context(allowed_company_ids=[self.env.company.id]).env.companies.ids)
        with self.assertRaises(AccessError):
            wizard.with_context(allowed_company_ids=[self.env.company.id]).button_export_html()
