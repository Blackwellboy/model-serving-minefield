"""Rank registry entries without converting textual similarity into proof."""

from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9_.+-]{2,}", re.I)
STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "only",
    "your", "you", "use", "using", "not", "are", "was", "were", "has",
    "have", "under", "over", "after", "before",
}


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value)
            if token.lower() not in STOPWORDS}


def search(
    registry: dict[str, Any],
    symptom: str,
    *,
    stack: str | None = None,
    model: str | None = None,
    version: str | None = None,
    evidence_status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    query = _tokens(" ".join(filter(None, (symptom, stack, model, version))))
    results: list[dict[str, Any]] = []
    for entry in registry["entries"]:
        if evidence_status and evidence_status not in entry["evidence_strength"]:
            continue
        symptom_text = entry["symptom"] + " " + entry["title"] + " " + entry["check"]
        symptom_tokens = _tokens(symptom_text)
        context_tokens = _tokens(
            " ".join(entry["affected_stacks"])
            + " " + entry["affected_versions_builds"]
            + " " + entry["mechanism"]
        )
        direct = len(query & symptom_tokens)
        context = len(query & context_tokens)
        if not direct and not context:
            continue
        score = direct * 4 + context
        if symptom.strip().lower() in symptom_text.lower():
            score += 30
        condition_match = []
        condition_mismatch = []
        if stack:
            target = stack.lower()
            if any(target in item.lower() or item.lower() in target for item in entry["affected_stacks"]):
                score += 5
                condition_match.append(f"stack: {stack}")
            elif entry["affected_stacks"]:
                condition_mismatch.append(f"stack {stack} is not named in published conditions")
        confidence = "possible"
        if direct >= 3 and not condition_mismatch:
            confidence = "strong possible"
        results.append({
            "trap_ids": [entry["id"]],
            "title": entry["title"],
            "match_confidence": confidence,
            "score": score,
            "evidence_status": entry["status"],
            "condition_match": condition_match,
            "condition_mismatch": condition_mismatch,
            "confirmation_check": entry["check"],
            "refutation_check": (
                "Run the published check under the named conditions; a result "
                "that contradicts its failure signature refutes this match only."
            ),
            "safest_mitigation": entry["mitigation"],
            "mutation_authority_warning": (
                "Do not change configuration or restart services until the match "
                "is supported and the user explicitly authorises mutation."
            ),
            "what_remains_unknown": entry["known_limitations"]
                or "Text similarity is not a reproduced diagnosis.",
            "source_path": entry["source_path"],
        })
    results.sort(key=lambda item: (-item["score"], int(item["trap_ids"][0])))
    return results[: max(1, min(limit, 50))]
