"""Verify branding transformations without requiring the accounting runtime."""
import ast
import pathlib
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons/thirdcode_accounting"
tree = ast.parse((ADDON / "models/branding.py").read_text())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
namespace = {"re": re}
exec(compile(ast.Module(body=[function], type_ignores=[]), "branding.py", "exec"), namespace)


class BrandingTests(unittest.TestCase):
    def test_workspace_redirects_preserve_deep_link_and_parameters(self):
        controller = ast.parse((ADDON / "controllers/webclient.py").read_text())
        helper = next(node for node in controller.body if isinstance(node, ast.FunctionDef))
        scope = {"re": re}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "webclient.py", "exec"), scope)
        brand = scope["branded_workspace_url"]
        for suffix in ("", "?debug=1", "#menu_id=4", "/action-408?lang=en_US#tab"):
            self.assertEqual(brand("/odoo" + suffix), "/workspace" + suffix)
        for path in ("/odoo-other", "/web/login", "https://other.example/odoo"):
            self.assertEqual(brand(path), path)

    def test_invitation_preserves_dynamic_fields_and_is_idempotent(self):
        body = ('Welcome to Odoo <t t-out="object.name"/> '
                '<a t-att-href="object.partner_id._get_signup_url()">Accept</a> '
                '<a href="https://www.odoo.com/page/tour?utm_source=db">Odoo Tour</a> '
                'Never heard of Odoo? Millions of users increase your productivity.')
        result = namespace["brand_invitation"](body)
        self.assertNotIn("Odoo", result)
        self.assertNotIn("Millions", result)
        self.assertIn('<t t-out="object.name"/>', result)
        self.assertIn('t-att-href="object.partner_id._get_signup_url()"', result)
        self.assertEqual(result, namespace["brand_invitation"](result))

    def test_form_views_declare_models_and_use_stable_selectors(self):
        root = ET.parse(ADDON / "views/branding_communications.xml").getroot()
        for record in root.findall("record"):
            self.assertIsNotNone(record.find("field[@name='model']"))
        for selector in root.iter("xpath"):
            self.assertNotIn("@string", selector.get("expr"))


if __name__ == "__main__":
    unittest.main()
