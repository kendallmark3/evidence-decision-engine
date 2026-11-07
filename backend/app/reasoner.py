"""The single reasoning capability.

Every provider is exposed as a LangChain ``Runnable`` with the same contract:

    input:  {"evidence": {...}, "claims": [...], "policies": [...], "gaps": [...]}
    output: Assessment dict (decision, rationale, cited_evidence, contradictions, remediation)
            or {"error": "..."} when the model fails.

Providers (``EDE_MODEL_PROVIDER``):
  * ``offline`` (default) — deterministic evidence reasoner. No model, no cost,
    reproducible. Lets the whole graph run and be tested for $0.
  * ``bedrock`` — Claude (or any Bedrock model) via ``langchain-aws``.
  * ``ollama``  — a local open-weight model via ``langchain-ollama``.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field

from .policy import check_policies


class Contradiction(BaseModel):
    claim: str = Field(description="The claim text, quoted exactly")
    evidence_ref: str = Field(description="Evidence ID that contradicts the claim")
    explanation: str


class Assessment(BaseModel):
    decision: Literal["READY", "NOT_READY", "NEEDS_REVIEW"]
    rationale: str = Field(description="Short explanation grounded only in the cited evidence")
    cited_evidence: list[str] = Field(description="Evidence IDs exactly as provided. Never invent IDs.")
    contradictions: list[Contradiction] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are an enterprise AI deployment-readiness evaluator.
You decide only from EVIDENCE. Claims are assertions made by the application team and are NOT evidence.
If a claim conflicts with evidence, report it as a contradiction and trust the evidence.
Cite evidence only by the exact IDs given in the EVIDENCE object. Never invent an ID.
Recommend READY only if every applicable policy is satisfied by documented evidence.
Return the structured assessment only."""

HUMAN_PROMPT = """EVIDENCE (id -> value):
{evidence}

CLAIMS (not evidence):
{claims}

POLICIES:
{policies}

GAPS ALREADY IDENTIFIED (evidence IDs with no documented value):
{gaps}"""

_COMPLIANCE_WORDS = re.compile(r"\b(compliant|compliance|secure|approved|review(ed)? completed|meets all)\b", re.I)


def _offline_assess(payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic stand-in for a model: inspects the evidence, cross-examines claims."""
    evidence = payload["evidence"]
    findings = check_policies(evidence, {"policies": payload["policies"]})
    problems = findings["violations"] + findings["missing"]
    cited = sorted({f["evidence_ref"] for f in findings["passed"] + problems if f["evidence_ref"] in evidence})

    contradictions = []
    for claim in payload["claims"]:
        if _COMPLIANCE_WORDS.search(claim):
            for v in findings["violations"]:
                contradictions.append(
                    {
                        "claim": claim,
                        "evidence_ref": v["evidence_ref"],
                        "explanation": f"Claim asserts compliance, but {v['evidence_ref']}={v['observed']!r} violates {v['policy_id']} ({v['title']}).",
                    }
                )

    if problems:
        decision = "NOT_READY"
        rationale = "Evidence does not support deployment: " + "; ".join(
            f"{f['policy_id']} {f['title'].lower()}" for f in problems
        ) + "."
        if contradictions:
            rationale += " Team claims of compliance are contradicted by the configuration and were not accepted."
    else:
        decision = "READY"
        rationale = f"All {len(findings['passed'])} applicable policies are satisfied by documented evidence."

    return Assessment(
        decision=decision,
        rationale=rationale,
        cited_evidence=cited,
        contradictions=contradictions,
        remediation=[f["remediation"] for f in problems],
    ).model_dump()


def _chat_model(provider: str):
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse  # optional dependency

        return ChatBedrockConverse(
            model=os.getenv("EDE_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
        )
    if provider == "ollama":
        from langchain_ollama import ChatOllama  # optional dependency

        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3.1"), temperature=0)
    raise ValueError(f"Unknown EDE_MODEL_PROVIDER '{provider}'")


def _llm_runnable(provider: str) -> Runnable:
    prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])
    chain = prompt | _chat_model(provider).with_structured_output(Assessment)

    def to_prompt_vars(p: dict[str, Any]) -> dict[str, str]:
        return {
            "evidence": json.dumps(p["evidence"], indent=2, default=str),
            "claims": json.dumps(p["claims"], indent=2),
            "policies": json.dumps(p["policies"], indent=2),
            "gaps": json.dumps(p["gaps"]),
        }

    return RunnableLambda(to_prompt_vars) | chain | RunnableLambda(lambda a: a.model_dump())


def build_reasoner(provider: str | None = None) -> Runnable:
    provider = (provider or os.getenv("EDE_MODEL_PROVIDER", "offline")).lower()
    if provider == "offline":
        return RunnableLambda(_offline_assess)
    return _llm_runnable(provider)


def safe_assess(reasoner: Runnable, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke the reasoner; any exception or malformed output becomes ``{"error": ...}``."""
    try:
        result = reasoner.invoke(payload)
        if not isinstance(result, dict):
            return {"error": f"Model returned {type(result).__name__}, expected an assessment"}
        return Assessment.model_validate(result).model_dump()
    except Exception as exc:  # noqa: BLE001 — every failure must fail closed
        return {"error": f"{type(exc).__name__}: {exc}"}
