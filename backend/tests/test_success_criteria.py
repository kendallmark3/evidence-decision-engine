"""One test group per success criterion in intent/current-feature.md."""

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from tests.conftest import load_sample

SCENARIOS = [
    ("internal-knowledge-assistant", "READY", None),
    ("clinical-document-summarizer", "NOT_READY", "POL-002"),
    ("autonomous-data-export-agent", "NOT_READY", "POL-005"),
    ("vendor-contract-analyzer-misleading", "NOT_READY", "POL-001"),
]


def submit(client, name):
    r = client.post("/api/evaluations", json={"config": load_sample(name)})
    assert r.status_code == 200, r.text
    return r.json()


# 1. A user submits an application configuration through the API the UI uses.
def test_submit_config_pauses_for_review(client):
    body = submit(client, "internal-knowledge-assistant")
    assert body["status"] == "awaiting_review"
    assert body["review_request"]["type"] == "architect_review"


def test_rejects_config_without_application(client):
    assert client.post("/api/evaluations", json={"config": {"model": {}}}).status_code == 422


# 2. LangGraph evaluates every node in order, using the configured model.
@pytest.mark.parametrize("name,expected,policy", SCENARIOS)
def test_scenarios(client, name, expected, policy):
    body = submit(client, name)
    assert body["gate"]["decision"] == expected
    nodes = [t["node"] for t in body["trace"]]
    assert nodes[:5] == ["understand_request", "examine_evidence", "identify_gaps", "evaluate_readiness", "policy_check"]
    assert nodes[5] == ("route_ready" if expected == "READY" else "route_not_ready")
    if policy:
        ids = [v["policy_id"] for v in body["findings"]["violations"] + body["findings"]["missing"]]
        assert policy in ids


def test_misleading_claim_is_contradicted_not_accepted(client):
    body = submit(client, "vendor-contract-analyzer-misleading")
    contradictions = body["assessment"]["contradictions"]
    assert any("fully compliant" in c["claim"] and c["evidence_ref"] == "audit.logging" for c in contradictions)
    assert body["gate"]["decision"] == "NOT_READY"


# 3. The deterministic validator prevents an unsupported READY.
def test_model_saying_ready_cannot_override_violation(client_with):
    def overconfident(_):
        return {"decision": "READY", "rationale": "Looks great", "cited_evidence": ["audit.logging"]}

    body = client_with(overconfident).post(
        "/api/evaluations", json={"config": load_sample("vendor-contract-analyzer-misleading")}
    ).json()
    assert body["assessment"]["decision"] == "READY"
    assert body["gate"]["decision"] == "NOT_READY"
    assert body["gate"]["overrode_model"] is True


def test_model_saying_not_ready_on_clean_config_needs_review(client_with):
    def cautious(_):
        return {"decision": "NOT_READY", "rationale": "Unsure", "cited_evidence": []}

    body = client_with(cautious).post("/api/evaluations", json={"config": load_sample("internal-knowledge-assistant")}).json()
    assert body["gate"]["decision"] == "NEEDS_REVIEW"


# 4. An architect can approve or reject a paused evaluation and the graph resumes.
def test_approve_resumes_to_final_report(client):
    eid = submit(client, "internal-knowledge-assistant")["evaluation_id"]
    body = client.post(f"/api/evaluations/{eid}/review", json={"action": "approve", "reviewer": "mark"}).json()
    assert body["status"] == "complete"
    assert body["report"]["decision"] == "READY"
    assert body["report"]["human_approval"]["status"] == "approved"
    assert body["trace"][-1]["node"] == "final_report"


def test_reject_blocks_a_ready_recommendation(client):
    eid = submit(client, "internal-knowledge-assistant")["evaluation_id"]
    body = client.post(f"/api/evaluations/{eid}/review", json={"action": "reject", "comment": "Not this quarter"}).json()
    assert body["report"]["decision"] == "NOT_READY"
    assert body["report"]["human_approval"]["status"] == "rejected"


def test_approval_cannot_turn_not_ready_into_ready(client):
    eid = submit(client, "clinical-document-summarizer")["evaluation_id"]
    body = client.post(f"/api/evaluations/{eid}/review", json={"action": "approve"}).json()
    assert body["report"]["decision"] == "NOT_READY"


def test_add_evidence_resumes_and_reevaluates(client):
    eid = submit(client, "hr-policy-assistant-missing-audit")["evaluation_id"]
    body = client.post(
        f"/api/evaluations/{eid}/review",
        json={"action": "add_evidence", "reviewer": "mark", "evidence": {"audit.logging": "enabled", "audit.retention_days": 365}},
    ).json()
    assert body["status"] == "awaiting_review"
    assert body["iteration"] == 2
    assert body["gate"]["decision"] == "READY"
    body = client.post(f"/api/evaluations/{eid}/review", json={"action": "approve", "reviewer": "mark"}).json()
    report = body["report"]
    assert report["decision"] == "READY"
    audit = next(e for e in report["evidence_references"] if e["id"] == "audit.logging")
    assert audit["source"] == "architect-supplied:mark"


def test_paused_state_survives_restart(tmp_path):
    first = TestClient(create_app(data_dir=tmp_path))
    eid = first.post("/api/evaluations", json={"config": load_sample("internal-knowledge-assistant")}).json()["evaluation_id"]
    second = TestClient(create_app(data_dir=tmp_path))  # new process, same checkpoint store
    body = second.post(f"/api/evaluations/{eid}/review", json={"action": "approve"}).json()
    assert body["report"]["decision"] == "READY"


def test_review_after_completion_is_rejected(client):
    eid = submit(client, "internal-knowledge-assistant")["evaluation_id"]
    client.post(f"/api/evaluations/{eid}/review", json={"action": "approve"})
    assert client.post(f"/api/evaluations/{eid}/review", json={"action": "approve"}).status_code == 409


def test_add_evidence_cannot_rewrite_claims(client):
    eid = submit(client, "vendor-contract-analyzer-misleading")["evaluation_id"]
    r = client.post(f"/api/evaluations/{eid}/review", json={"action": "add_evidence", "evidence": {"claims": ["ok"]}})
    assert r.status_code == 422
    assert client.get(f"/api/evaluations/{eid}").json()["status"] == "awaiting_review"


# 5. Complete evidence report with no invented evidence references.
@pytest.mark.parametrize("name,expected,_", SCENARIOS)
def test_report_is_complete_and_references_only_real_evidence(client, name, expected, _):
    config = load_sample(name)
    eid = submit(client, name)["evaluation_id"]
    client.post(f"/api/evaluations/{eid}/review", json={"action": "approve"})
    r = client.get(f"/api/evaluations/{eid}/report")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    report = r.json()
    for key in [
        "decision", "evidence_references", "missing_evidence", "policy_violations",
        "recommended_remediation", "human_approval", "decision_reasons",
    ]:
        assert key in report
    assert report["decision"] == expected
    from app.evidence import flatten

    real = flatten(config)
    for ref in report["evidence_references"]:
        assert ref["present"] == (ref["id"] in real)
        if ref["present"]:
            assert ref["value"] == real[ref["id"]]
    for c in report["contradictions"]:
        assert c["evidence_ref"] in real


def test_invented_citation_is_rejected(client_with):
    def hallucinating(_):
        return {"decision": "READY", "rationale": "SOC2 attested", "cited_evidence": ["security.soc2_attestation", "audit.logging"]}

    c = client_with(hallucinating)
    body = c.post("/api/evaluations", json={"config": load_sample("internal-knowledge-assistant")}).json()
    assert body["gate"]["decision"] == "NEEDS_REVIEW"
    assert body["gate"]["invented_citations"] == ["security.soc2_attestation"]
    eid = body["evaluation_id"]
    report = c.post(f"/api/evaluations/{eid}/review", json={"action": "approve"}).json()["report"]
    assert report["decision"] == "NEEDS_REVIEW"
    assert "security.soc2_attestation" not in [e["id"] for e in report["evidence_references"]]


# 6. A model failure cannot accidentally result in approval.
FAILURES = {
    "raises": lambda _: (_ for _ in ()).throw(TimeoutError("Bedrock timed out")),
    "returns_none": lambda _: None,
    "returns_text": lambda _: "READY",
    "bad_decision": lambda _: {"decision": "APPROVED", "rationale": "", "cited_evidence": []},
    "missing_fields": lambda _: {"decision": "READY"},
}


@pytest.mark.parametrize("mode", FAILURES)
def test_model_failure_never_approves(client_with, mode):
    c = client_with(FAILURES[mode])
    body = c.post("/api/evaluations", json={"config": load_sample("internal-knowledge-assistant")}).json()
    assert body["gate"]["decision"] == "NEEDS_REVIEW"
    assert "error" in body["assessment"]
    report = c.post(f"/api/evaluations/{body['evaluation_id']}/review", json={"action": "approve"}).json()["report"]
    assert report["decision"] != "READY"
