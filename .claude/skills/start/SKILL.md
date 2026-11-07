---
description: Start Progressive Intent work in the current project. Use at the beginning of a feature, or the first time this plugin is used in a repository.
argument-hint: "[the outcome you want]"
---

# Start
Get from a stated outcome to something the human can observe.

The outcome, if given: $ARGUMENTS

1. If `intent/current-feature.md` does not exist in the project, create it from `templates/feature-template.md`.
2. Write the human's Outcome and Success / Evidence into it in their words. Ask only for what is missing from those two. Delete the other sections unless the human gave real inputs, outputs, or boundaries.
3. Run `bash hooks/pre-implement.sh` from the project root. Code edits are blocked until it passes.
4. Read repository state, determine the smallest useful delta, build it, and run the project's tests.
5. Show the human the result and ask: continue or stop. Feedback goes to the progressive-intent skill.
