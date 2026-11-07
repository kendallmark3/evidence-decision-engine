"""Framework-independent evaluation steps.

The evaluation contract lives here, not in the graph. ``graph.py`` (LangGraph)
and ``baseline.py`` (plain Python) both call these same functions, which keeps
the "does LangGraph earn its place?" experiment honest and lets the contract
survive a move to another orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .evidence import extract_claims, flatten
from .policy import NOT_READY, READY, check_policies, gate
from .reasoner import safe_assess


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def understand_request(config: dict[str, Any]) -> dict[str, Any]:
    app = config.get("application") or {}
    return {
        "application": app.get("name", "Unnamed application"),
        "use_case": app.get("use_case"),
        "owner": app.get("owner"),
        "question": "Is this AI application ready to deploy into the enterprise environment?",
    }


def examine_evidence(config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    return flatten(config), extract_claims(config)


def identify_gaps(evidence: dict[str, Any], policies: dict[str, Any]) -> dict[str, list]:
    return check_policies(evidence, policies)


def evaluate_readiness(reasoner, evidence, claims, policies, findings) -> dict[str, Any]:
    payload = {
        "evidence": evidence,
        "claims": claims,
        "policies": policies["policies"],
        "gaps": [m["evidence_ref"] for m in findings["missing"]],
    }
    return safe_assess(reasoner, payload)


def policy_check(findings, assessment, evidence) -> dict[str, Any]:
    return gate(findings, assessment, evidence)


def final_decision(gate_decision: str, approval: dict[str, Any] | None) -> str:
    """A human can block a READY, but can never turn a blocked decision into READY."""
    if gate_decision == READY:
        return READY if (approval or {}).get("status") == "approved" else NOT_READY
    return gate_decision


def build_report(state: dict[str, Any], policies: dict[str, Any]) -> dict[str, Any]:
    evidence = state["evidence"]
    findings = state["findings"]
    gate_result = state["gate"]
    assessment = state.get("assessment") or {}
    approval = state.get("approval") or {"status": "pending"}

    referenced = set(gate_result["verified_citations"])
    for group in ("passed", "violations", "missing"):
        referenced.update(f["evidence_ref"] for f in findings[group])
    for c in assessment.get("contradictions") or []:
        referenced.add(c["evidence_ref"])

    evidence_refs = [
        {
            "id": ref,
            "value": evidence.get(ref),
            "present": ref in evidence,
            "source": state.get("provenance", {}).get(ref, "submitted-config"),
        }
        for ref in sorted(referenced)
    ]
    # Report integrity: every evidence reference the report presents as present must exist.
    assert all(e["present"] == (e["id"] in evidence) for e in evidence_refs)

    contradictions = [c for c in assessment.get("contradictions") or [] if c.get("evidence_ref") in evidence]
    remediation = list(dict.fromkeys(
        [f["remediation"] for f in findings["violations"] + findings["missing"]] + list(assessment.get("remediation") or [])
    ))

    return {
        "report_version": "1.0",
        "evaluation_id": state["evaluation_id"],
        "generated_at": now(),
        "request": state["request"],
        "decision": final_decision(gate_result["decision"], approval),
        "policy_gate_decision": gate_result["decision"],
        "model": {
            "provider": state.get("model_provider"),
            "recommendation": gate_result["model_recommendation"],
            "rationale": assessment.get("rationale"),
            "error": assessment.get("error"),
            "overridden_by_policy": gate_result["overrode_model"],
            "invented_citations_rejected": gate_result["invented_citations"],
        },
        "decision_reasons": gate_result["reasons"],
        "evidence_references": evidence_refs,
        "missing_evidence": findings["missing"],
        "policy_violations": findings["violations"],
        "policies_passed": findings["passed"],
        "contradictions": contradictions,
        "claims_examined": state.get("claims", []),
        "recommended_remediation": remediation,
        "human_approval": approval,
        "iterations": state.get("iteration", 1),
        "policy_set_version": policies.get("version"),
    }
