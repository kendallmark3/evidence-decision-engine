# Architecture

## Progression 1 (built, runs locally)

```
React + TypeScript (Vite)  ──/api──▶  FastAPI (backend/app/api.py)
                                          │
                                          ▼
                                 LangGraph (backend/app/graph.py)
                                    │                │
                       engine.py (contract)   SqliteSaver checkpointer
                         │            │          (data/checkpoints.db)
                 policy.py (gate)   reasoner.py (one model, LangChain Runnable)
                 policies.json       offline | bedrock | ollama
```

| Module | Responsibility | Framework-dependent? |
|---|---|---|
| `evidence.py` | Split config into evidence (citable IDs) vs claims (never evidence) | No |
| `policy.py` | Deterministic policy rules and the readiness gate | No |
| `reasoner.py` | The single reasoning capability; fails closed to `{"error": ...}` | LangChain Runnable only |
| `engine.py` | The evaluation contract — every step as a plain function | No |
| `graph.py` | State, branching, checkpointing, interrupt/resume, re-evaluation loop | **LangGraph** |
| `baseline.py` | Same contract in plain Python — the experiment's control group | No |
| `api.py` | HTTP surface; synchronous evaluate, separate review request resumes graph | FastAPI |

## Progression 2 (target, see intent/next-progression-aws.md)

S3 + CloudFront (static UI) → API Gateway → Lambda (FastAPI via Mangum) → LangGraph → Bedrock.
DynamoDB-backed checkpointer replaces SQLite; S3 stores evidence reports.
S3 never runs LangGraph — the Python runtime lives in Lambda.

## Invariants
- Only `policy.gate()` can produce READY, and only when no violations, no missing evidence, a valid model assessment, no invented citations, and model concurrence.
- A human can block READY but cannot turn NOT_READY / NEEDS_REVIEW into READY. New evidence → re-evaluation is the only path.
- Every evidence reference in a report exists in the (possibly architect-patched) config, with provenance.
