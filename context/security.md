# Security

- Synthetic data only. No real company configurations, policies, or patient data in this repo.
- Fail closed: any model exception, timeout, malformed or partial output becomes NEEDS_REVIEW, never READY (tests: `test_model_failure_never_approves`).
- Model citations are verified against the evidence index; invented references are rejected and listed in the report.
- Architect-supplied evidence is tagged `architect-supplied:<reviewer>` in the report; claims cannot be patched as evidence.
- CORS is open for local development. Lock it to the CloudFront origin in Progression 2.
- No authentication in Progression 1. The reviewer name is self-asserted. Progression 2 should put the API behind IAM/Cognito before anything is shared.
