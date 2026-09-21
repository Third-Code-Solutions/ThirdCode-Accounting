import base64

from odoo.tools import file_open


def post_init_hook(env):
    company = env.ref("base.main_company", raise_if_not_found=False)
    if not company:
        return

    with file_open("thirdcode_accounting/static/src/img/tcsi-logo.svg", "rb") as logo_file:
        logo = base64.b64encode(logo_file.read())
    company.write(
        {
            "name": "Third Code Solutions Inc.",
            "logo": logo,
        }
    )
