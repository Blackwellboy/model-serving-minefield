"""Context-only lookup for the MCP stack and model tools.

Symptom search deliberately requires at least two independent symptom concepts.
That safety rule is correct for diagnosis, but it made single-token context
queries such as ``vllm`` or ``Qwen`` return no entries.  These helpers search
only the registry's declared applicability fields and label every result as a
context match rather than a diagnosis.
"""

from __future__ import annotations

import re
from typing import Any

TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return set(TOKEN.findall(value.casefold()))


def _values(entry: dict[str, Any], field: str) -> list[str]:
    value = entry.get(field, [])
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    return []


def lookup_context(
    registry: dict[str, Any],
    query: str,
    *,
    field: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return entries whose declared stack/model context matches ``query``.

    A result means only that the canonical entry names a related context.  It
    is not evidence that the user's deployment has the trap.
    """
    if field not in {"affected_stacks", "affected_models"}:
        raise ValueError(f"unsupported context field: {field}")
    phrase = " ".join(query.casefold().split())
    query_tokens = _tokens(query)
    if not phrase or not query_tokens:
        return []

    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for entry in registry.get("entries", []):
        values = _values(entry, field)
        if not values:
            continue
        best_score = 0
        best_value = ""
        for value in values:
            normal = " ".join(value.casefold().split())
            value_tokens = _tokens(value)
            overlap = len(query_tokens & value_tokens)
            if normal == phrase:
                score = 100 + overlap
            elif phrase in normal or normal in phrase:
                score = 70 + overlap
            elif query_tokens <= value_tokens:
                score = 50 + overlap
            elif overlap:
                score = 10 + overlap
            else:
                score = 0
            if score > best_score:
                best_score = score
                best_value = value
        if best_score:
            ranked.append((best_score, -int(entry["id"]), {
                "trap_id": entry["id"],
                "title": entry["title"],
                "source_path": entry["source_path"],
                "check": entry["check"],
                "evidence_strength": entry.get("evidence_strength", []),
                "matched_context": best_value,
                "match_type": "declared-context-only",
                "warning": "A context match is not a diagnosis; run the entry's check.",
            }))
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    return [item[2] for item in ranked[:max(0, min(limit, 50))]]
