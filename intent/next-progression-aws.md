# Next Progression (draft) — Progression 2: Deploy to AWS
<!-- Not active. When Progression 1 has been observed and the human says "continue", append this as a delta to current-feature.md. -->

## Observation
Progression 1 runs locally end-to-end: five scenarios, interrupt/resume, re-evaluation, fail-closed gate, downloadable report.

## Keep
- The evaluation contract (`engine.py`, `policy.py`, `evidence.py`) and the graph shape, unchanged.
- The offline reasoner as the default for tests and CI.
- All existing tests passing.

## Change
- Static UI on S3 behind CloudFront (HTTPS).
- API Gateway → Lambda (Python, FastAPI via Mangum) running the same graph.
- Model: Bedrock, low-cost model, pinned version.
- Checkpoint state in DynamoDB (select or implement a compatible LangGraph checkpointer).
- Evidence reports written to S3.
- Infrastructure as code (SAM or CDK), one-command deploy.

## New Boundary
- Still synchronous for short evaluations; architect review stays a separate request that resumes saved state.
- API not public without auth (IAM or Cognito); CORS locked to the CloudFront origin.
- Synthetic data only.

## Evidence
- The five scenarios produce the same decisions on AWS as locally.
- A paused evaluation survives a Lambda cold start and resumes from DynamoDB.
- A forced Bedrock failure yields NEEDS_REVIEW, never READY.
- Monthly cost at demo volume is shown and stays within free tier / a few dollars.
