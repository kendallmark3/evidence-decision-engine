r"""The LangGraph workflow.

    understand_request -> examine_evidence -> identify_gaps -> evaluate_readiness
        -> policy_check --(READY)--> route_ready ----\
                        \-(NOT_READY / NEEDS_REVIEW)-> route_not_ready
                                                       -> human_approval (interrupt)
                                    (add_evidence) <-/        |
                         examine_evidence <------------------/ (approve / reject)
                                                              -> final_report -> END

What LangGraph contributes here, and nowhere else in the codebase:
  * explicit typed state shared across steps,
  * conditional branching after the policy gate,
  * a checkpointer so a paused evaluation survives across HTTP requests / restarts,
  * ``interrupt()`` + ``Command(resume=...)`` for human-in-the-loop,
  * a loop back to re-evaluate when the architect supplies new evidence.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import engine
from .evidence import apply_patch
from .policy import READY, load_policies
from .reasoner import build_reasoner

MAX_ITERATIONS = 5


class EvalState(TypedDict, total=False):
    evaluation_id: str
    model_provider: str
    config: dict[str, Any]
    provenance: dict[str, str]
    request: dict[str, Any]
    evidence: dict[str, Any]
    claims: list[str]
    findings: dict[str, list]
    assessment: dict[str, Any]
    gate: dict[str, Any]
    branch: str
    approval: dict[str, Any]
    resume_action: str
    iteration: int
    report: dict[str, Any]
    trace: Annotated[list[dict[str, Any]], operator.add]


def _t(node: str, summary: str) -> list[dict[str, Any]]:
    return [{"node": node, "at": engine.now(), "summary": summary}]


def build_graph(checkpointer, reasoner=None, policies: dict[str, Any] | None = None, provider: str | None = None):
    policies = policies or load_policies()
    reasoner = reasoner or build_reasoner(provider)

    def understand_request(state: EvalState):
        req = engine.understand_request(state["config"])
        return {"request": req, "iteration": 1, "trace": _t("understand_request", f"Evaluating '{req['application']}'")}

    def examine_evidence(state: EvalState):
        evidence, claims = engine.examine_evidence(state["config"])
        return {
            "evidence": evidence,
            "claims": claims,
            "trace": _t("examine_evidence", f"{len(evidence)} evidence items, {len(claims)} claims (claims are not evidence)"),
        }

    def identify_gaps(state: EvalState):
        f = engine.identify_gaps(state["evidence"], policies)
        return {
            "findings": f,
            "trace": _t("identify_gaps", f"{len(f['passed'])} passed, {len(f['violations'])} violations, {len(f['missing'])} missing"),
        }

    def evaluate_readiness(state: EvalState):
        a = engine.evaluate_readiness(reasoner, state["evidence"], state["claims"], policies, state["findings"])
        summary = f"Model error: {a['error']}" if a.get("error") else f"Model recommends {a['decision']}"
        return {"assessment": a, "trace": _t("evaluate_readiness", summary)}

    def policy_check(state: EvalState):
        g = engine.policy_check(state["findings"], state["assessment"], state["evidence"])
        note = " (overrode model)" if g["overrode_model"] else ""
        return {"gate": g, "trace": _t("policy_check", f"Gate decision {g['decision']}{note}")}

    def route_after_gate(state: EvalState) -> str:
        return "route_ready" if state["gate"]["decision"] == READY else "route_not_ready"

    def route_ready(state: EvalState):
        return {"branch": "READY", "trace": _t("route_ready", "Eligible for deployment pending architect approval")}

    def route_not_ready(state: EvalState):
        return {"branch": "NOT_READY", "trace": _t("route_not_ready", f"Deployment approval blocked ({state['gate']['decision']})")}

    def human_approval(state: EvalState):
        g = state["gate"]
        decision = interrupt(
            {
                "type": "architect_review",
                "gate_decision": g["decision"],
                "reasons": g["reasons"],
                "allowed_actions": ["approve", "reject", "add_evidence"],
                "note": "Approval cannot override a blocked decision. Supply evidence to re-evaluate.",
            }
        )
        action = decision.get("action")
        if action not in {"approve", "reject", "add_evidence"}:
            raise ValueError(f"Invalid review action: {action!r}")
        reviewer = decision.get("reviewer") or "architect"
        comment = decision.get("comment") or ""

        if action == "add_evidence":
            if state.get("iteration", 1) >= MAX_ITERATIONS:
                raise ValueError("Maximum re-evaluation iterations reached")
            patch = decision.get("evidence") or {}
            if not patch:
                raise ValueError("add_evidence requires an 'evidence' object of {path: value}")
            provenance = {**state.get("provenance", {}), **{k: f"architect-supplied:{reviewer}" for k in patch}}
            return {
                "config": apply_patch(state["config"], patch),
                "provenance": provenance,
                "resume_action": "add_evidence",
                "iteration": state.get("iteration", 1) + 1,
                "approval": {"status": "pending"},
                "trace": _t("human_approval", f"{reviewer} supplied {len(patch)} evidence item(s); re-evaluating"),
            }

        status = "approved" if action == "approve" else "rejected"
        return {
            "resume_action": action,
            "approval": {"status": status, "reviewer": reviewer, "comment": comment, "at": engine.now()},
            "trace": _t("human_approval", f"{reviewer} {status} the {g['decision']} recommendation"),
        }

    def route_after_review(state: EvalState) -> str:
        return "examine_evidence" if state.get("resume_action") == "add_evidence" else "final_report"

    def final_report(state: EvalState):
        report = engine.build_report(state, policies)
        return {"report": report, "trace": _t("final_report", f"Final decision {report['decision']}")}

    g = StateGraph(EvalState)
    for name, fn in [
        ("understand_request", understand_request),
        ("examine_evidence", examine_evidence),
        ("identify_gaps", identify_gaps),
        ("evaluate_readiness", evaluate_readiness),
        ("policy_check", policy_check),
        ("route_ready", route_ready),
        ("route_not_ready", route_not_ready),
        ("human_approval", human_approval),
        ("final_report", final_report),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "understand_request")
    g.add_edge("understand_request", "examine_evidence")
    g.add_edge("examine_evidence", "identify_gaps")
    g.add_edge("identify_gaps", "evaluate_readiness")
    g.add_edge("evaluate_readiness", "policy_check")
    g.add_conditional_edges("policy_check", route_after_gate, ["route_ready", "route_not_ready"])
    g.add_edge("route_ready", "human_approval")
    g.add_edge("route_not_ready", "human_approval")
    g.add_conditional_edges("human_approval", route_after_review, ["examine_evidence", "final_report"])
    g.add_edge("final_report", END)

    return g.compile(checkpointer=checkpointer)
