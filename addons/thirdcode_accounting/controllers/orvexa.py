"""ORVEXA's same-session, CSRF-protected task boundary."""
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError


class OrvexaController(http.Controller):
    @http.route("/thirdcode_accounting/orvexa", type="json", auth="user", methods=["POST"])
    def task(self, csrf_token=None, company_id=None, message=None, proposal_id=None, cancel=False, memory=False):
        if not csrf_token or not request.validate_csrf(csrf_token):
            return {"status": "error", "message": "Session verification failed. Reload the workspace."}
        try:
            with request.env.cr.savepoint():
                agent = request.env["thirdcode.orvexa"]
                if memory is True:
                    return agent.memory(company_id)
                if proposal_id is not None:
                    return agent.confirm_task(proposal_id, company_id, cancel)
                return agent.request_task(message, company_id)
        except AccessError:
            return {"status": "error", "message": "Your role does not permit this task in the selected company."}
        except (UserError, ValidationError) as error:
            return {"status": "error", "message": str(error)}
