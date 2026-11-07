#!/usr/bin/env bash
# Passes when an intent file states an Outcome and how success will be evidenced.
# Usage: hooks/pre-implement.sh [intent-file]   (default: intent/current-feature.md)
set -euo pipefail

file="${1:-intent/current-feature.md}"

if [ ! -f "$file" ]; then
  echo "pre-implement: $file not found" >&2
  exit 1
fi

missing=$(awk '
  BEGIN {
    outcome["outcome"]; outcome["business outcome"]
    evidence["success / evidence"]; evidence["evidence"]
    evidence["success criteria"]; evidence["acceptance criteria"]
    other["inputs"]; other["outputs"]; other["requirements"]
    other["constraints"]; other["constraints / boundaries"]
  }
  {
    gsub(/<!--.*-->/, "")
    name = tolower($0)
    sub(/^#+[ \t]*/, "", name)
    sub(/[ \t:]+$/, "", name)
    if (name in outcome)  { section = "outcome";  next }
    if (name in evidence) { section = "evidence"; next }
    if ($0 ~ /^#/ || name in other) { section = ""; next }
    if (section != "" && $0 ~ /[^ \t]/) found[section] = 1
  }
  END {
    if (!found["outcome"])  print "Outcome"
    if (!found["evidence"]) print "Success / Evidence"
  }
' "$file")

if [ -n "$missing" ]; then
  echo "pre-implement: $file is not sufficient to start. Missing:" >&2
  echo "$missing" | sed 's/^/  - /' >&2
  exit 1
fi

echo "pre-implement: $file is sufficient to start."
