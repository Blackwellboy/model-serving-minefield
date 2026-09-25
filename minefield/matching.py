"""Rank registry entries without converting textual similarity into proof."""

from __future__ import annotations

import re
from typing import Any

from .diagnosis_contract import contract_for_match, miss_contract
from .leads import search_leads

TOKEN_RE = re.compile(r"[a-z0-9_.+-]{2,}", re.I)
STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "only",
    "your", "you", "use", "using", "not", "are", "was", "were", "has",
    "have", "under", "over", "after", "before",
}

# User phrasing may vary, but one concept still counts as one concept:
# aliases broaden vocabulary without manufacturing extra overlap.
TOKEN_ALIASES: dict[str, set[str]] = {
    "response": {"content", "reply"},
    "reply": {"content", "response"},
    "blank": {"empty"},
    "garbage": {"gibberish", "garbled"},
    "garbled": {"gibberish", "garbage"},
    "thinking": {"reasoning"},
    "reasoning": {"thinking"},
    "leak": {"spill", "spills", "spilled", "leaked", "leaking"},
    "leaked": {"spill", "spills", "spilled", "leak", "leaking"},
    "leaking": {"spill", "spills", "spilled", "leak", "leaked"},
    "ignored": {"inert"},
    "ignore": {"inert"},
}


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(value)
        if token.lower() not in STOPWORDS
    }


def _concepts(value: str) -> list[set[str]]:
    """Return one alias-set per original meaningful token.

    Counting concepts rather than expanded tokens is deliberate: the word
    thinking may expand to reasoning, but that still contributes only one
    overlap. This prevents a synonym table from recreating the old
    one-shared-word false-positive bug.
    """
    out: list[set[str]] = []
    for token in TOKEN_RE.findall(value):
        token = token.lower()
        if token in STOPWORDS:
            continue
        out.append({token, *TOKEN_ALIASES.get(token, set())})
    return out


def _concept_overlap(concepts: list[set[str]], searchable: set[str]) -> int:
    return sum(1 for concept in concepts if concept & searchable)


def search(
    registry: dict[str, Any],
    symptom: str,
    *,
    stack: str | None = None,
    model: str | None = None,
    version: str | None = None,
    log_excerpt: str | None = None,
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

    # Candidate admission is symptom-first. Stack/model/version may improve
    # ranking and applicability, but cannot turn one ordinary shared word into
    # a candidate by themselves.
    symptom_text_for_match = " ".join(
        part for part in (symptom, log_excerpt or "") if part
    )
    symptom_concepts = _concepts(symptom_text_for_match)
    context_concepts = _concepts(" ".join(filter(None, (stack, model, version))))

    results: list[dict[str, Any]] = []
    for entry in registry["entries"]:
        if evidence_status and evidence_status not in entry["evidence_strength"]:
            continue
        searchable_symptom = (
            entry["symptom"] + " " + entry["title"] + " " + entry["check"]
        )
        searchable_symptom_tokens = _tokens(searchable_symptom)
        searchable_context_tokens = _tokens(
            " ".join(entry["affected_stacks"])
            + " " + entry["affected_versions_builds"]
            + " " + entry["mechanism"]
        )
        direct = _concept_overlap(symptom_concepts, searchable_symptom_tokens)
        context = _concept_overlap(context_concepts, searchable_context_tokens)
        is_explicit = entry["id"] in explicit_ids

        # Two independently supplied meaningful symptom/log concepts are the
        # minimum for ordinary textual admission. Direct-probe IDs bypass this
        # because the caller explicitly named the trap under test.
        if direct < 2 and not is_explicit:
            continue

        score = direct * 4 + context
        normalized_symptom = symptom.strip().lower()
        if (
            normalized_symptom
            and len(_concepts(symptom)) >= 2
            and normalized_symptom in searchable_symptom.lower()
        ):
            score += 30
        if stack:
            target = stack.lower()
            if any(
                target in item.lower() or item.lower() in target
                for item in entry["affected_stacks"]
            ):
                score += 5
        if model:
            target = model.lower()
            if any(
                target in item.lower() or item.lower() in target
                for item in entry["affected_models"]
            ):
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
    """Return canonical candidates plus a clearly separate weaker lead layer.

    Canonical traps are always searched first. L-series leads remain
    non-canonical and never turn resemblance into confirmation.
    """
    matches = search(registry, symptom, **kwargs)
    lead_text = " ".join(
        part for part in (symptom, kwargs.get("log_excerpt") or "") if part
    )
    lead_matches = search_leads(
        lead_text,
        stack=kwargs.get("stack"),
        model=kwargs.get("model"),
        version=kwargs.get("version"),
        limit=5,
    )
    if not matches:
        result = miss_contract(symptom, kwargs.get("conditions"))
        result["possible_unverified_leads"] = lead_matches
        if lead_matches:
            result["warning"] = (
                "No canonical Minefield trap matched. The L-series items below are "
                "possible unverified troubleshooting leads only. Run their confirm/refute "
                "checks before treating any mechanism as applicable."
            )
        else:
            result["warning"] = (
                "No canonical trap or public-safe unverified lead matched. A registry miss "
                "means not documented, never safe."
            )
        return result
    return {
        "diagnosis_level": matches[0]["diagnosis_level"],
        "observed_symptom": symptom,
        "matches": matches,
        "possible_unverified_leads": lead_matches,
        "warning": (
            "Canonical candidates are ranked, not proven. L-series suggestions are a "
            "strictly weaker non-canonical tier. Apply mitigations only after the relevant "
            "confirmation check succeeds under the user's exact conditions."
        ),
    }
