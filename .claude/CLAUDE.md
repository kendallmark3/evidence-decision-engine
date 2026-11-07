# Repository Rules
Read intent/current-feature.md first, including any deltas appended to it.
Read intent/project-intent.md and context/ for what the code cannot show.
Run hooks/pre-implement.sh before implementing.
Build the smallest useful delta, then let the human observe it and decide: continue or stop.
Always write tests. `make test` must pass.
Respect architecture:
- Evaluation logic stays framework-independent in backend/app/engine.py, policy.py, evidence.py. Only graph.py knows LangGraph.
- Only policy.gate() may produce READY. A model failure must never approve.
- Synthetic data only.
