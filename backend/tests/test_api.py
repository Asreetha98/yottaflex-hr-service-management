"""API tests: authentication, RBAC, ticket lifecycle, sensitive-case access control, policy validity."""

import pytest

from conftest import PASSWORD

API = "/api/v1"


def test_health_and_docs(client):
    assert client.get("/openapi.json").status_code == 200


def test_login_success_and_me(client, tokens):
    r = client.get(API + "/auth/me", headers=tokens["employee"])
    assert r.status_code == 200
    assert r.json()["username"] == "employee"


def test_login_wrong_password(client):
    r = client.post(API + "/auth/login", json={"username": "employee", "password": "wrong-password"})
    assert r.status_code in (401, 403)


def test_unauthenticated_request_rejected(client):
    assert client.get(API + "/tickets").status_code in (401, 403)


def test_employee_cannot_use_admin_endpoints(client, tokens):
    assert client.get(API + "/admin/users", headers=tokens["employee"]).status_code == 403
    assert client.get(API + "/admin/users", headers=tokens["admin"]).status_code == 200


def _create(client, headers, subject, body):
    r = client.post(API + "/tickets", json={"subject": subject, "description": body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_ticket_classifies_and_routes(client, tokens):
    t = _create(client, tokens["employee"], "Payslip missing", "My salary payslip for this month is missing")
    assert t["status"] in ("ASSIGNED", "CLASSIFIED", "AWAITING_CLARIFICATION")
    assert t["is_sensitive"] is False


def test_sensitive_ticket_is_restricted(client, tokens):
    t = _create(client, tokens["employee"], "Confidential harassment report",
                "I want to report harassment by my manager, please keep this confidential")
    assert t["is_sensitive"] is True
    tid = t["ticket_id"]
    # a general HR partner without sensitive clearance cannot read it, the privileged one can
    assert client.get("%s/tickets/%s" % (API, tid), headers=tokens["hr_partner"]).status_code in (403, 404)
    assert client.get("%s/tickets/%s" % (API, tid), headers=tokens["hr_sensitive"]).status_code == 200
    # another ordinary employee cannot read it either
    assert client.get("%s/tickets/%s" % (API, tid), headers=tokens["employee2"]).status_code in (403, 404)
    # and the owner can
    assert client.get("%s/tickets/%s" % (API, tid), headers=tokens["employee"]).status_code == 200


def test_sensitive_ticket_hidden_from_general_listing(client, tokens):
    t = _create(client, tokens["employee"], "Discrimination grievance", "I need to file a grievance about discrimination")
    items = client.get(API + "/tickets?limit=200", headers=tokens["hr_partner"]).json()["items"]
    assert t["ticket_id"] not in {i["ticket_id"] for i in items}


def test_denied_access_is_audited(client, tokens):
    t = _create(client, tokens["employee"], "Harassment complaint", "harassment by a colleague, confidential")
    client.get("%s/tickets/%s" % (API, t["ticket_id"]), headers=tokens["employee2"])
    logs = client.get(API + "/admin/audit-logs?limit=200", headers=tokens["admin"]).json()["items"]
    assert any(l["action"] == "ACCESS_DENIED" for l in logs)


def test_lifecycle_cannot_skip_states(client, tokens):
    t = _create(client, tokens["employee"], "Annual leave balance", "How many annual leave days do I have left this year")
    # resolving a ticket that was never started is an invalid transition
    r = client.post("%s/tickets/%s/resolve" % (API, t["ticket_id"]),
                    json={"resolution_type": "ACTION_COMPLETED", "summary": "done", "resolution_text": "done"},
                    headers=tokens["hr_partner"])
    assert r.status_code in (400, 409, 422)


def test_full_lifecycle_and_closed_is_terminal(client, tokens):
    t = _create(client, tokens["employee"], "Payslip correction", "My salary payslip shows the wrong tax deduction amount")
    tid = t["ticket_id"]
    h = tokens["hr_partner"]
    assert t["status"] == "ASSIGNED", t["status"]
    assert client.post("%s/tickets/%s/start" % (API, tid), headers=h).status_code == 200
    r = client.post("%s/tickets/%s/resolve" % (API, tid), headers=h, json={
        "resolution_type": "ACTION_COMPLETED", "summary": "Corrected", "resolution_text": "Corrected the deduction"})
    assert r.status_code == 200, r.text
    assert client.post("%s/tickets/%s/close" % (API, tid), headers=h).status_code == 200
    again = client.post("%s/tickets/%s/start" % (API, tid), headers=h)
    assert again.status_code in (400, 409, 422)


def test_policy_answer_requires_source(client, tokens):
    t = _create(client, tokens["employee"], "Payslip tax deduction",
                "My salary payslip for October shows a wrong tax deduction amount")
    tid = t["ticket_id"]
    h = tokens["hr_partner"]
    assert t["status"] == "ASSIGNED", t["status"]
    client.post("%s/tickets/%s/start" % (API, tid), headers=h)
    r = client.post("%s/tickets/%s/resolve" % (API, tid), headers=h, json={
        "resolution_type": "POLICY_ANSWER", "summary": "Policy answer", "resolution_text": "It is 20 days."})
    assert r.status_code in (400, 409, 422)


def test_policy_effective_endpoint(client, tokens):
    policies = client.get(API + "/policies?limit=5", headers=tokens["admin"])
    assert policies.status_code == 200
    items = policies.json()["items"]
    if items:
        r = client.get("%s/policies/%s/effective" % (API, items[0]["policy_id"]), headers=tokens["admin"])
        assert r.status_code == 200


def test_sla_metrics_available_to_staff(client, tokens):
    assert client.get(API + "/sla/metrics", headers=tokens["hr_partner"]).status_code == 200


def test_analytics_overview(client, tokens):
    assert client.get(API + "/analytics/overview", headers=tokens["admin"]).status_code == 200
