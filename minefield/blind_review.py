"""Derive a blind-review packet from a full Evidence Packet.

Reduces one obvious source of reviewer contamination (proposer confidence,
verdict, recommended numbering, final disposition, persuasive narrative).
Does not mathematically guarantee independence.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

# Fields stripped or quarantined from the blind packet.
STRIP_REVIEW_KEYS = (
    "proposer_confidence",
    "proposer_verdict",
)
STRIP_CLAIM_KEYS = (
    "disposition",
)
# Entire optional narrative bags if present
STRIP_TOP_LEVEL = (
    "proposer_narrative",
    "recommended_trap_number",
    "adjudicator_conclusion",
    "persuasive_summary",
    "final_disposition",
)


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(_canonical_json(obj)).hexdigest()


def derive_blind_packet(full: dict[str, Any]) -> dict[str, Any]:
    """Return blind packet + hashes metadata wrapper.

    Blind body retains hypothesis, identities, artifacts, execution facts,
    controls, expected disproof, unresolved questions.
    """
    if not isinstance(full, dict):
        raise TypeError("full packet must be a dict")

    full_hash = sha256_obj(full)
    blind = copy.deepcopy(full)

    for key in STRIP_TOP_LEVEL:
        blind.pop(key, None)

    review = blind.get("review")
    if isinstance(review, dict):
        for key in STRIP_REVIEW_KEYS:
            review.pop(key, None)
        # Keep role names and independence status; strip confidence/verdict.
        # Do not include adjudicator conclusion fields if present.
        review.pop("adjudicator_conclusion", None)
        review.pop("final_verdict", None)

    claim = blind.get("claim")
    if isinstance(claim, dict):
        for key in STRIP_CLAIM_KEYS:
            claim.pop(key, None)
        # Keep claim_boundary, evidence_status, unresolved_conditions
        claim.pop("recommended_trap_number", None)
        claim.pop("persuasive_summary", None)

    # Quarantine any nested narrative fields
    for path_key in ("notes", "narrative", "summary"):
        blind.pop(path_key, None)

    blind_hash = sha256_obj(blind)
    return {
        "schema_version": "1.0",
        "kind": "blind_review_packet",
        "full_packet_sha256": full_hash,
        "blind_packet_sha256": blind_hash,
        "independence_note": (
            "This packet strips proposer confidence/verdict and final "
            "disposition to reduce anchoring. It does not guarantee "
            "independent review."
        ),
        "packet": blind,
    }


def assert_no_leak(blind_wrapper: dict[str, Any]) -> list[str]:
    """Return list of leak descriptions (empty if clean)."""
    leaks: list[str] = []
    raw = json.dumps(blind_wrapper, sort_keys=True)
    forbidden_substrings = (
        '"proposer_confidence"',
        '"proposer_verdict"',
        '"recommended_trap_number"',
        '"adjudicator_conclusion"',
        '"persuasive_summary"',
        '"final_disposition"',
    )
    # disposition may still appear in independence_note text? We strip claim.disposition
    # Check structural keys in packet body
    packet = blind_wrapper.get("packet") or {}
    review = packet.get("review") or {}
    claim = packet.get("claim") or {}
    for key in STRIP_REVIEW_KEYS:
        if key in review:
            leaks.append(f"review.{key} leaked")
    if "disposition" in claim:
        leaks.append("claim.disposition leaked")
    for key in STRIP_TOP_LEVEL:
        if key in packet:
            leaks.append(f"top-level {key} leaked")
    for s in forbidden_substrings:
        if s in raw and s.strip('"') in (review.keys() if False else []):
            pass
    # Direct JSON key scan
    if '"proposer_confidence"' in raw:
        leaks.append("proposer_confidence string present in blind wrapper")
    if '"proposer_verdict"' in raw:
        leaks.append("proposer_verdict string present in blind wrapper")
    if '"recommended_trap_number"' in raw:
        leaks.append("recommended_trap_number present in blind wrapper")
    return leaks
