from copy import deepcopy

from lxml import etree
from odoo import api, models


def tcsi_settings_arch(arch):
    """Curate the completed native view, without changing configuration values.

    Run after view inheritance so other addons can still find their native
    anchors. Work on a copy; never modify another caller's cached architecture.
    Accounting application settings and access modifiers remain untouched.
    """
    arch = deepcopy(arch)
    for app in arch.xpath("//app[@name='general_settings']"):
        app.set("string", "TCSI Settings")
        app.set("data-string", "TCSI Settings")
        app.set("logo", "/thirdcode_accounting/static/src/img/apps/settings.svg")
        for node in app.xpath(
            ".//block[@id='product_general_settings'] | "
            ".//div[@id='contacts_settings'] | "
            ".//setting[@id='digest'] | "
            ".//widget[@name='res_config_dev_tool'] | "
            ".//setting[@id='mail_pluggin_setting' or @id='product_get_pic_setting' "
            "or @id='unsplash' or @id='base_geolocalize'] | "
            ".//block[@id='discuss']/setting[not(@id='activities_setting')]"
        ):
            node.getparent().remove(node)
        for block in app.xpath(".//block[@id='discuss']"):
            block.set("title", "Activities")
        for block in app.xpath(".//block[@name='integration']"):
            block.set("title", "Sign-in & protection")
        for setting in app.xpath(".//setting[@id='email_servers_setting']"):
            setting.set("title", "Configure email delivery and receiving for TCSI Accounting.")
        # Upstream help widgets construct vendor URLs at render time. Keep
        # provider-specific documentation (e.g. Microsoft/Google) when useful.
        for node in app.xpath(".//widget[@name='documentation_link']"):
            node.getparent().remove(node)
        for node in app.xpath(".//*[@documentation]"):
            documentation = node.get("documentation", "")
            if documentation.startswith("/") or "odoo.com" in documentation.lower():
                del node.attrib["documentation"]
        for about in app.xpath(".//div[@id='about']"):
            about.clear()
            about.set("id", "about")
            block = etree.SubElement(about, "block", title="About TCSI", name="about_setting_container")
            setting = etree.SubElement(block, "setting", id="tcsi_about", string="TCSI Accounting")
            etree.SubElement(setting, "p", attrib={"class": "text-muted"}).text = "Accounting workspace by Third Code Solutions Inc."
            etree.SubElement(setting, "a", href="https://www.thirdcodesolutions.com", target="_blank", rel="noopener noreferrer").text = "Third Code Solutions Inc."
    return arch


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            arch = tcsi_settings_arch(arch)
        return arch, view
