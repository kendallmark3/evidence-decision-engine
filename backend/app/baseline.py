"""Plain-Python baseline — the control group for the LangGraph experiment.

Same evaluation contract, no graph. It produces the same gate decision, but it
cannot pause for a human, persist mid-evaluation state, or resume after new
evidence arrives without hand-written state management. That difference is the
measurable value LangGraph has to justify. See docs/langgraph-vs-plain-python.md.
"""

from __future__ import annotations

from typing import Any

from . import engine
from .policy import load_policies
from .reasoner import build_reasoner


def evaluate_plain(config: dict[str, Any], reasoner=None, policies=None, approval=None) -> dict[str, Any]:
    policies = policies or load_policies()
    reasoner = reasoner or build_reasoner()
    request = engine.understand_request(config)
    evidence, claims = engine.examine_evidence(config)
    findings = engine.identify_gaps(evidence, policies)
    assessment = engine.evaluate_readiness(reasoner, evidence, claims, policies, findings)
    gate = engine.policy_check(findings, assessment, evidence)
    state = {
        "evaluation_id": "baseline",
        "request": request,
        "evidence": evidence,
        "claims": claims,
        "findings": findings,
        "assessment": assessment,
        "gate": gate,
        "approval": approval,  # must be known up front — there is no pause
    }
    return engine.build_report(state, policies)
