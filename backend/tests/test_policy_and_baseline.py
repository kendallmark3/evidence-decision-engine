from app.baseline import evaluate_plain
from app.evidence import apply_patch, extract_claims, flatten
from app.policy import check_policies, load_policies
from tests.conftest import load_sample

POLICIES = load_policies()


def test_claims_are_never_evidence():
    cfg = load_sample("vendor-contract-analyzer-misleading")
    ev = flatten(cfg)
    assert "claims" not in ev and "application.description" not in ev
    assert not any(k.startswith("_sample") for k in ev)
    assert any("fully compliant" in c for c in extract_claims(cfg))


def test_undocumented_value_is_missing_not_passed():
    ev = flatten(load_sample("clinical-document-summarizer"))
    f = check_policies(ev, POLICIES)
    assert "POL-004" in [m["policy_id"] for m in f["missing"]]


def test_conditional_policy_only_applies_when_triggered():
    ev = flatten(load_sample("internal-knowledge-assistant"))
    f = check_policies(ev, POLICIES)
    assert "POL-008" in [n["policy_id"] for n in f["not_applicable"]]


def test_patch_builds_nested_paths():
    out = apply_patch({"application": {"name": "x"}}, {"audit.logging": "enabled"})
    assert out["audit"]["logging"] == "enabled"


def test_baseline_matches_graph_decision_without_pause():
    expected = {
        "internal-knowledge-assistant": "READY",
        "clinical-document-summarizer": "NOT_READY",
        "autonomous-data-export-agent": "NOT_READY",
        "vendor-contract-analyzer-misleading": "NOT_READY",
    }
    for name, decision in expected.items():
        r = evaluate_plain(load_sample(name), approval={"status": "approved"})
        assert r["policy_gate_decision"] == decision
