---
description: Turn the human's observation of a running result into the next minimum intent delta. Use when the human gives feedback on something that was just built, such as "keep this", "change that", or "this is too busy".
---

# Progressive Intent Skill
Turn the human's observation of a running result into the next minimum intent delta.

- Take feedback as given ("keep this", "too complicated", "don't change the backend"). Do not ask for a rewritten specification.
- Append a delta to `intent/current-feature.md` using `templates/delta-template.md`. Use only the sections needed.
- Record what stays as carefully as what changes. An explicit "don't touch" is a New Boundary.
- Do not rewrite the original intent, and do not plan the implementation here; that is the feature planner's job.
- If the observation asks for nothing further, the answer is Stop.
