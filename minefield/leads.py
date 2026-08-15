"""Non-canonical symptom-first troubleshooting leads.

The canonical registry remains the authority for Minefield trap IDs.  This
module deliberately exposes weaker L-series leads without converting textual
similarity into proof.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "UNVERIFIED_LEADS.json"
COMPOUND_RE = re.compile(r"[a-z0-9_.+-]{2,}", re.I)
COMPONENT_RE = re.compile(r"[a-z0-9_+]{2,}", re.I)
STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "only",
    "your", "you", "use", "using", "not", "are", "was", "were", "has",
    "have", "under", "over", "after", "before", "can", "may", "might",
}


def _tokens(value: str) -> set[str]:
    """Keep exact compound identifiers and their punctuation-separated parts."""
    result: set[str] = set()
    for match in COMPOUND_RE.finditer(value):
        raw = match.group(0).lower().strip(".-")
        candidates = ({raw} if len(raw) >= 2 else set()) | {
            token.lower() for token in COMPONENT_RE.findall(raw)
        }
        result.update(token for token in candidates if token not in STOPWORDS)
    return result


def load_leads(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DATA_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("canonical_trap_count_impact") != 0:
        raise ValueError("unverified lead catalogue must not change canonical trap count")
    if not payload.get("policy", {}).get("lead_match_never_confirms_root_cause"):
        raise ValueError("unverified lead catalogue must preserve the non-confirmation policy")
    return payload


def _searchable(lead: dict[str, Any]) -> tuple[str, str]:
    direct = " ".join((
        str(lead.get("title", "")),
        str(lead.get("symptom", "")),
        str(lead.get("confirmation_check", "")),
    ))
    context = " ".join((
        str(lead.get("possible_mechanism", "")),
        str(lead.get("scope", "")),
        str(lead.get("notes", "")),
        " ".join(str(item) for item in lead.get("affected_stacks", [])),
        " ".join(str(item) for item in lead.get("related_traps", [])),
    ))
    return direct, context


def _contract(lead: dict[str, Any], *, score: int, observed_symptom: str) -> dict[str, Any]:
    return {
        "lead_id": lead["id"],
        "canonical": False,
        "lead_match_level": "POSSIBLE_UNVERIFIED_LEAD",
        "evidence_status": lead["status"],
        "source_class": lead["source_class"],
        "confidence": lead["confidence"],
        "scope": lead["scope"],
        "title": lead["title"],
        "score": score,
        "observed_symptom": observed_symptom,
        "documented_symptom": lead["symptom"],
        "pattern_resemblance": (
            f"The supplied symptom resembles non-canonical lead {lead['id']}; "
            "resemblance is not confirmation."
        ),
        "possible_mechanism": lead["possible_mechanism"],
        "confirmation_check": lead["confirmation_check"],
        "refutation_check": lead["refutation_check"],
        "conditional_mitigation": lead["conditional_mitigation"],
        "related_traps": lead["related_traps"],
        "affected_stacks": lead["affected_stacks"],
        "source_refs": lead["source_refs"],
        "warning": (
            "This is a possible/unverified troubleshooting lead, not a canonical "
            "Minefield trap and not a confirmed root cause."
        ),
    }


def search_leads(
    symptom: str,
    *,
    stack: str | None = None,
    model: str | None = None,
    version: str | None = None,
    limit: int = 5,
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank public-safe L-series leads while keeping them non-canonical."""
    payload = load_leads() if payload is None else payload
    query_text = " ".join(filter(None, (symptom, stack, model, version)))
    query = _tokens(query_text)
    if not query:
        return []

    results: list[dict[str, Any]] = []
    for lead in payload.get("leads", []):
        direct_text, context_text = _searchable(lead)
        direct = len(query & _tokens(direct_text))
        context = len(query & _tokens(context_text))
        if not direct and not context:
            continue
        score = direct * 4 + context
        if symptom.strip() and symptom.strip().lower() in direct_text.lower():
            score += 30
        if stack:
            target = stack.lower()
            if any(
                target in str(item).lower() or str(item).lower() in target
                for item in lead.get("affected_stacks", [])
            ):
                score += 5
        if model and model.lower() in (direct_text + " " + context_text).lower():
            score += 3
        if version and version.lower() in (direct_text + " " + context_text).lower():
            score += 2
        results.append(_contract(lead, score=score, observed_symptom=symptom))

    results.sort(key=lambda item: (-item["score"], item["lead_id"]))
    return results[:max(0, min(limit, 20))]
