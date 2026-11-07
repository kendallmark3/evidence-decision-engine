# Business Rules

Machine-readable rules live in `backend/policies/policies.json` (synthetic, fictional policy set).

| ID | Rule | Applies when |
|---|---|---|
| POL-001 | `audit.logging` = enabled | always |
| POL-002 | `model.version_pinned` = true | always |
| POL-003 | `identity.type` ∈ IAM, SSO, OIDC | always |
| POL-004 | `governance.egress.documented` = true | always |
| POL-005 | `governance.egress.external_egress` = false | always |
| POL-006 | `governance.human_approval` = required | data is restricted or confidential |
| POL-007 | `data.encryption_in_transit` = true | always |
| POL-008 | `audit.retention_days` ≥ 365 | data is restricted |
| POL-009 | `model.gateway` = enterprise-model-gateway | always |

Gate outcomes:
- **NOT_READY** — any violation or missing (undocumented) evidence.
- **NEEDS_REVIEW** — model error, malformed output, invented citation, or model disagrees with a clean policy result.
- **READY** — clean policy result and the model concurs. Final READY additionally requires architect approval.

Claims (`claims[]`, `application.description`) are assertions, never evidence.
