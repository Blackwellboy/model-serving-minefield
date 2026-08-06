"""Rank registry entries without converting textual similarity into proof."""

from __future__ import annotations

import re
from typing import Any

from .diagnosis_contract import contract_for_match, miss_contract

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
    conditions: dict[str, Any] | None = None,
    direct_probe_trap_ids: list[str] | None = None,
    direct_probe_results: dict[str, str] | None = None,
    mechanism_probe_trap_ids: list[str] | None = None,
    evidence_status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    conditions = dict(conditions or {})
    if stack:
        conditions.setdefault("serving_stack", stack)
    if model:
        conditions.setdefault("exact_checkpoint", model)
    if version:
        conditions.setdefault("stack_version", version)
    known_ids = {entry["id"] for entry in registry["entries"]}
    direct_ids = {
        str(item).zfill(2) for item in (direct_probe_trap_ids or [])
        if str(item).zfill(2) in known_ids
    }
    probe_results = {
        str(trap_id).zfill(2): str(outcome).lower()
        for trap_id, outcome in (direct_probe_results or {}).items()
        if (
            str(trap_id).zfill(2) in known_ids
            and str(outcome).lower() in {"confirmed", "refuted", "inconclusive"}
        )
    }
    explicit_ids = direct_ids | set(probe_results)
    mechanism_ids = {str(item).zfill(2) for item in (mechanism_probe_trap_ids or [])}
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
        is_explicit = entry["id"] in explicit_ids
        if not direct and not context and not is_explicit:
            continue
        score = direct * 4 + context
        if symptom.strip().lower() in symptom_text.lower():
            score += 30
        if stack:
            target = stack.lower()
            if any(target in item.lower() or item.lower() in target for item in entry["affected_stacks"]):
                score += 5
        if model:
            target = model.lower()
            if any(target in item.lower() or item.lower() in target
                   for item in entry["affected_models"]):
                score += 5
        if version:
            if version.lower() in entry["affected_versions_builds"].lower():
                score += 3
        probe_result = probe_results.get(
            entry["id"],
            "candidate_requested" if entry["id"] in direct_ids else "not_supplied",
        )
        contract = contract_for_match(
            entry,
            observed_symptom=symptom,
            symptom_score=score,
            observed_conditions=conditions,
            direct_probe_support=probe_result == "confirmed",
            direct_probe_result=probe_result,
            mechanism_directly_supported=entry["id"] in mechanism_ids,
        )
        results.append({
            "trap_ids": [entry["id"]],
            "title": entry["title"],
            "match_confidence": contract["diagnosis_level"],
            "score": score,
            "source_path": entry["source_path"],
            **contract,
        })
    results.sort(key=lambda item: (
        item["trap_id"] not in explicit_ids,
        -item["score"],
        int(item["trap_ids"][0]),
    ))
    explicit_results = [item for item in results if item["trap_id"] in explicit_ids]
    ordinary_results = [item for item in results if item["trap_id"] not in explicit_ids]
    ordinary_slots = min(max(1, limit), max(0, 50 - len(explicit_results)))
    return explicit_results[:50] + ordinary_results[:ordinary_slots]


def diagnose(
    registry: dict[str, Any],
    symptom: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return an explicit envelope so a miss can never be mistaken for CLEAN."""
    matches = search(registry, symptom, **kwargs)
    if not matches:
        return miss_contract(symptom, kwargs.get("conditions"))
    return {
        "diagnosis_level": matches[0]["diagnosis_level"],
        "observed_symptom": symptom,
        "matches": matches,
        "warning": (
            "Candidates are ranked, not proven. Apply mitigations only after the "
            "confirmation check succeeds under the user's exact conditions."
        ),
    }
