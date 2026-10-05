"""Owner and tenant HTTP flows, called only by the disposable hosted CI runner."""
import json
import uuid
from http.client import HTTPConnection


def verify_platform(port, owner_cookie, database):
    assert database.startswith("tcsi_orvexa_")

    def request(path, payload=None, cookie=None):
        connection = HTTPConnection("127.0.0.1", port, timeout=90)
        headers = {"Content-Type": "application/json", "X-Forwarded-Proto": "https"}
        if cookie:
            headers["Cookie"] = cookie.split(";", 1)[0]
        connection.request("POST" if payload is not None else "GET", path,
                           json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        session = response.getheader("Set-Cookie")
        connection.close()
        return result, session

    def rpc(method, args=None, cookie=owner_cookie, model="thirdcode.platform.console", kwargs=None, denied=False):
        data, _ = request("/web/dataset/call_kw", {"jsonrpc": "2.0", "params": {
            "model": model, "method": method, "args": args or [], "kwargs": kwargs or {}}}, cookie)
        if denied:
            assert "error" in data, (model, method, "unexpectedly allowed")
            return data["error"]
        assert "error" not in data, (model, method, data.get("error"))
        return data["result"]

    # Exercise actual chart/journal/admin creation, not a mocked baseline.
    payload = {"request_id": str(uuid.uuid4()), "name": "Hosted platform client", "country": "PH",
               "currency": "PHP", "admin_name": "Hosted client admin", "admin_login": "platform-ci@example.invalid",
               "admin_password": "Disposable-CI-Account-Only-48"}
    company = rpc("create_organization", [payload])
    assert rpc("create_organization", [payload])["id"] == company["id"]
    rows = rpc("get_organizations", [payload["name"]])["rows"]
    assert len(rows) == 1 and rows[0]["baseline_ready"] and rows[0]["open_periods"]
    session, tenant_cookie = request("/web/session/authenticate", {"jsonrpc": "2.0", "params": {
        "db": database, "login": payload["admin_login"], "password": payload["admin_password"]}})
    assert session.get("result", {}).get("uid") and tenant_cookie
    for method in ["get_console_data", "get_people", "get_audit", "get_monitoring", "get_publications"]:
        error = rpc(method, cookie=tenant_cookie, denied=True)
        assert error["data"]["name"] == "odoo.exceptions.AccessError", error
    rpc("dispatch", ["status"], cookie=tenant_cookie, model="thirdcode.setup.service",
        kwargs={"context": {"tcsi_setup_token_ok": True}}, denied=True)
    rpc("_provision_user", cookie=tenant_cookie, model="thirdcode.setup.service", denied=True)

    public_path = "/thirdcode_accounting/public/website"
    assert request(public_path)[0] == {"seo": None, "releases": []}
    values = {"kind": "seo", "title": "Hosted SEO title", "description": "Public snapshot test",
              "version": "", "category": "improvement"}
    draft = rpc("save_publication", [values])
    assert request(public_path)[0]["seo"] is None
    rpc("publish_content", [draft["id"], draft["revision"]])
    snapshot = request(public_path)[0]["seo"]
    assert snapshot["title"] == values["title"] and "revision" not in snapshot
    assert "published_json" not in snapshot
    record = rpc("get_publications")["rows"][0]
    rpc("save_publication", [dict(values, title="Still private draft"), record["id"], record["revision"]])
    assert request(public_path)[0]["seo"]["title"] == values["title"]

    # A server failure must survive the failed request's transaction rollback.
    rpc("manage_person", ["synthetic-invalid-id", "disable"], denied=True)
    incidents = rpc("get_monitoring")["incidents"]
    assert any(i["kind"] == "ValueError" and i["route"] == "/web" for i in incidents)
    assert all("synthetic-invalid-id" not in json.dumps(i) for i in incidents)
    analytics = rpc("get_analytics", [30], kwargs={"context": {"tz": "Asia/Manila"}})
    assert sum(p["count"] for p in analytics["points"]) == analytics["total"]
    assert rpc("get_audit")["total"] >= 3
    print("Platform HTTP: real organization baseline/admin, tenant denials, private RPC, publishing snapshots, rollback-surviving incident capture passed")
