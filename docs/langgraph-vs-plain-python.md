# Experiment: does LangGraph earn its place?

> Does LangGraph provide measurable value over a simple Python implementation for this use case?

The evaluation contract lives in `backend/app/engine.py`. Two orchestrators call it:

- `backend/app/graph.py` — LangGraph
- `backend/app/baseline.py` — plain Python, ~30 lines

`test_baseline_matches_graph_decision_without_pause` confirms both produce the same gate decision for every scenario. So for a **single, uninterrupted evaluation, LangGraph adds nothing.** A function call is enough.

## Where the difference appears

| Capability | Plain Python | LangGraph (this repo) |
|---|---|---|
| Linear evaluation | ✅ trivial | ✅ |
| Pause for a human mid-workflow | ❌ approval must be known up front | ✅ `interrupt()` |
| Resume across HTTP requests | ❌ hand-rolled state serialization | ✅ checkpointer + `thread_id` |
| Survive a process restart while paused | ❌ hand-rolled persistence | ✅ `test_paused_state_survives_restart` |
| Add evidence → loop back and re-evaluate | ❌ hand-rolled state machine | ✅ conditional edge back to `examine_evidence` |
| Execution trace per step | ❌ manual logging | ✅ state reducer (`trace`) |
| Swap checkpoint store (SQLite → DynamoDB) | ❌ rewrite persistence | ✅ swap the checkpointer |

## Honest read after Progression 1

LangGraph's value is concentrated in **human-in-the-loop + durable state + loops**. If the product never needed an architect pause or re-evaluation, the plain baseline would be the better choice. Because the governance story *requires* a resumable human decision, the graph earns its place, but only for that reason.

Measure in Progression 2: lines of code and defects for the equivalent hand-rolled pause/resume on Lambda + DynamoDB versus the checkpointer approach.
