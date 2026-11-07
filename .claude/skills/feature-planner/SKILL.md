---
description: Determine the smallest useful implementation delta from repository state and the current intent. Use before building a feature or an intent delta.
---

# Feature Planner Skill
Understand repository state and the current intent, including its deltas, and determine the smallest useful implementation delta.

- Read current state from the code and tests; use `context/` for what the code cannot show.
- Plan internally. The intent file does not need to contain the implementation plan.
- Leave untouched whatever the intent or a delta says to keep.
