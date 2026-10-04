"""Populate new attachment digest metadata without changing retained contents."""
import hashlib
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for attachment in env["ir.attachment"].search([]):
        digest = hashlib.sha256(attachment.raw or b"").hexdigest()
        cr.execute("UPDATE ir_attachment SET thirdcode_content_sha256 = %s WHERE id = %s", [digest, attachment.id])
    env["ir.attachment"].invalidate_model(["thirdcode_content_sha256"])
