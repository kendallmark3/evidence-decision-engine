"""Deterministic policy evaluation and the readiness gate.

Nothing in this module calls a model. These rules are the non-negotiable
controls: the model may *recommend*, but only this module can permit READY.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence import is_documented

POLICY_FILE = Path(__file__).resolve().parent.parent / "policies" / "policies.json"

READY = "READY"
NOT_READY = "NOT_READY"
NEEDS_REVIEW = "NEEDS_REVIEW"
DECISIONS = {READY, NOT_READY, NEEDS_REVIEW}


def load_policies(path: Path = POLICY_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def _matches(value: Any, rule: dict[str, Any]) -> bool:
    if "equals" in rule:
        expected = rule["equals"]
        if isinstance(expected, str) and isinstance(value, str):
            return value.strip().lower() == expected.lower()
        return value == expected
    if "in" in rule:
        allowed = rule["in"]
        if isinstance(value, str):
            return value.strip().lower() in {a.lower() for a in allowed}
        return value in allowed
    if "gte" in rule:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= rule["gte"]
    raise ValueError(f"Unknown rule: {rule}")


def _applies(policy: dict[str, Any], evidence: dict[str, Any]) -> bool:
    for path, rule in (policy.get("when") or {}).items():
        if path not in evidence or not _matches(evidence[path], rule):
            return False
    return True


def check_policies(evidence: dict[str, Any], policies: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return passed / violations / missing / not_applicable findings."""
    findings: dict[str, list[dict[str, Any]]] = {
        "passed": [],
        "violations": [],
        "missing": [],
        "not_applicable": [],
    }
    for p in policies["policies"]:
        base = {"policy_id": p["id"], "title": p["title"], "evidence_ref": p["evidence"]}
        if not _applies(p, evidence):
            findings["not_applicable"].append(base)
            continue
        value = evidence.get(p["evidence"])
        if p["evidence"] not in evidence or not is_documented(value):
            findings["missing"].append({**base, "remediation": f"Provide evidence for '{p['evidence']}'. " + p["remediation"]})
        elif _matches(value, p["rule"]):
            findings["passed"].append({**base, "observed": value})
        else:
            findings["violations"].append(
                {**base, "observed": value, "expected": p["rule"], "remediation": p["remediation"]}
            )
    return findings


def gate(findings: dict[str, list], assessment: dict[str, Any] | None, evidence: dict[str, Any]) -> dict[str, Any]:
    """The readiness gate. Combines deterministic findings with the model's assessment.

    Rules, in order:
      1. Any policy violation or missing mandatory evidence  -> NOT_READY.
      2. Model failed, returned nothing usable, or an unknown decision -> NEEDS_REVIEW.
      3. Model cited evidence that does not exist (invented)   -> NEEDS_REVIEW.
      4. Model disagrees with a clean policy result            -> NEEDS_REVIEW.
      5. Model recommends READY and policy is clean            -> READY.

    READY is only reachable through rule 5. A model failure can never approve.
    """
    reasons: list[str] = []
    cited = list((assessment or {}).get("cited_evidence") or [])
    verified = [ref for ref in cited if ref in evidence]
    invented = [ref for ref in cited if ref not in evidence]

    if findings["violations"] or findings["missing"]:
        for v in findings["violations"]:
            reasons.append(f"{v['policy_id']} violated: {v['title']} (observed {v['evidence_ref']}={v['observed']!r})")
        for m in findings["missing"]:
            reasons.append(f"{m['policy_id']} blocked: no evidence for {m['evidence_ref']}")
        decision = NOT_READY
    elif assessment is None or assessment.get("error"):
        decision = NEEDS_REVIEW
        reasons.append("Model assessment unavailable: " + str((assessment or {}).get("error", "no output")))
    elif assessment.get("decision") not in DECISIONS:
        decision = NEEDS_REVIEW
        reasons.append(f"Model returned an unrecognized decision: {assessment.get('decision')!r}")
    elif invented:
        decision = NEEDS_REVIEW
        reasons.append("Model cited evidence that does not exist: " + ", ".join(invented))
    elif assessment["decision"] != READY:
        decision = NEEDS_REVIEW
        reasons.append(f"Model recommended {assessment['decision']} although all policies passed; human review required")
    else:
        decision = READY
        reasons.append("All applicable policies passed with documented evidence, and the model concurs")

    return {
        "decision": decision,
        "model_recommendation": (assessment or {}).get("decision"),
        "reasons": reasons,
        "verified_citations": verified,
        "invented_citations": invented,
        "overrode_model": (assessment or {}).get("decision") not in (None, decision),
    }
