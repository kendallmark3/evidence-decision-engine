"""Evidence extraction.

The configuration is split into two kinds of content:

* Evidence — concrete, checkable configuration values. Each one gets a stable
  reference ID equal to its dotted path (e.g. ``audit.logging``). These are the
  only things the evaluator is allowed to cite.
* Claims — free-text assertions (``claims`` and ``application.description``).
  Claims are never evidence. They are examined *against* the evidence.
"""

from __future__ import annotations

from typing import Any

# Keys that carry assertions, not evidence.
CLAIM_PATHS = {"claims", "application.description"}
# Keys that are UI/sample metadata and never part of an evaluation.
IGNORED_ROOTS = {"_sample"}
# Values that mean "we have no evidence for this".
UNDOCUMENTED = {None, "", "not_documented", "unknown", "tbd"}


def flatten(config: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested config into ``{dotted.path: value}`` leaves."""
    out: dict[str, Any] = {}
    for key, value in config.items():
        path = f"{prefix}.{key}" if prefix else key
        if not prefix and key in IGNORED_ROOTS:
            continue
        if path in CLAIM_PATHS:
            continue
        if isinstance(value, dict):
            out.update(flatten(value, path))
        else:
            out[path] = value
    return out


def extract_claims(config: dict[str, Any]) -> list[str]:
    claims: list[str] = []
    desc = (config.get("application") or {}).get("description")
    if isinstance(desc, str) and desc.strip():
        claims.append(desc.strip())
    for c in config.get("claims") or []:
        c = c.strip() if isinstance(c, str) else ""
        if c and not any(c in existing for existing in claims):
            claims.append(c)
    return claims


def is_documented(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in UNDOCUMENTED
    return value is not None


def apply_patch(config: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply ``{dotted.path: value}`` updates to a deep copy of the config."""
    import copy

    updated = copy.deepcopy(config)
    for path, value in patch.items():
        if path.split(".")[0] in IGNORED_ROOTS or path in CLAIM_PATHS:
            raise ValueError(f"'{path}' is not an evidence path")
        node = updated
        parts = path.split(".")
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
    return updated
