# Glossary

- **Evidence** — a concrete configuration value with a citable ID equal to its dotted path (`audit.logging`).
- **Claim** — an assertion by the application team. Examined against evidence; never counted as evidence.
- **Gap / missing evidence** — a required evidence path that is absent or undocumented (`null`, `"not_documented"`).
- **Policy gate** — the deterministic step that has the final say over the model's recommendation.
- **Architect review** — the LangGraph `interrupt()` where a human approves, rejects, or supplies evidence.
- **Iteration** — one pass through the evaluation; supplying evidence starts a new iteration on the same thread.
- **Thread / evaluation_id** — the LangGraph checkpoint thread that holds an evaluation's state across requests.
