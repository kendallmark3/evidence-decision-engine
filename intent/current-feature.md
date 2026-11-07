# Current Feature — Progression 1: AI Evidence Decision Engine (V1)
<!-- After the first build, append deltas below (templates/delta-template.md). Do not rewrite this intent. -->

## Outcome
Build a functional AI application that evaluates enterprise AI deployment readiness using LangGraph, LangChain, and evidence-based reasoning. The user submits an application configuration, the graph investigates the evidence, identifies gaps, makes a recommendation, and pauses for a human architect before the final report.

## Inputs
- A JSON application configuration containing architecture, model, data security, identity, audit, and governance information.
- A small set of machine-readable policy rules.

## Outputs
A structured evaluation containing:
- Readiness decision: READY, NOT_READY, or NEEDS_REVIEW.
- Supporting evidence references.
- Missing evidence.
- Policy violations.
- Recommended remediation.
- Human approval status.
- A downloadable JSON report.

## Success / Evidence
1. A user submits an application configuration through the web interface.
2. LangGraph evaluates the application using the configured model and evidence.
3. A deterministic policy validator prevents an unsupported READY decision.
4. An architect can approve or reject a paused evaluation, and the graph resumes correctly.
5. The application produces a complete evidence report, with no invented evidence references.
6. A model failure cannot accidentally result in approval.

Scenarios that must behave as expected:

| Application | Expected | Reason |
|---|---|---|
| Internal Knowledge Assistant | READY | All mandatory evidence present |
| Clinical Document Summarizer | NOT_READY | Model version not pinned |
| Autonomous Data Export Agent | NOT_READY | Unauthorized external egress |
| Misleading "fully compliant" claim | NOT_READY | Claim contradicted by config (audit logging disabled) |

## Constraints / Boundaries
- Python, LangGraph, LangChain. Fictional configs and synthetic evidence only.
- One reasoning capability inside a governed workflow — no multi-agent org, no vector DB, no custom orchestration.
- Progression 1 runs locally end-to-end. AWS deployment is the next progression, not this one.
