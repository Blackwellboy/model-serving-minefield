#!/usr/bin/env python3
"""Search the non-canonical Minefield lead catalogue.

This router is advisory. Lexical resemblance never confirms a mechanism.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOUND_RE = re.compile(r"[a-z0-9_+.-]{2,}", re.I)
COMPONENT_RE = re.compile(r"[a-z0-9_+]{2,}", re.I)


def tokens(text: str) -> set[str]:
    """Index both compound identifiers and punctuation-separated components."""
    result: set[str] = set()
    for match in COMPOUND_RE.finditer(text):
        raw = match.group(0).lower().strip(".-")
        if len(raw) >= 2:
            result.add(raw)
        result.update(token.lower() for token in COMPONENT_RE.findall(raw))
    return result


def searchable(lead: dict) -> str:
    values = [
        lead.get("title", ""),
        lead.get("symptom", ""),
        lead.get("possible_mechanism", ""),
        lead.get("scope", ""),
        lead.get("notes", ""),
        " ".join(lead.get("affected_stacks", [])),
        " ".join(lead.get("related_traps", [])),
    ]
    return " ".join(str(v) for v in values)


def score(query: str, lead: dict) -> tuple[int, int]:
    q = tokens(query)
    hay = searchable(lead).lower()
    ht = tokens(hay)
    overlap = len(q & ht)
    phrase = 1 if query.strip().lower() in hay and query.strip() else 0
    return phrase, overlap


def search(query: str, limit: int = 10) -> list[dict]:
    payload = json.loads((ROOT / "LEADS.json").read_text(encoding="utf-8"))
    ranked = []
    for lead in payload["leads"]:
        rank = score(query, lead)
        if rank != (0, 0):
            ranked.append((rank, lead["id"], lead))
    ranked.sort(key=lambda item: (-item[0][0], -item[0][1], item[1]))
    return [item[2] for item in ranked[:limit]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    matches = search(args.query, max(args.limit, 0))
    if args.json:
        print(json.dumps({"query": args.query, "matches": matches}, indent=2))
        return 0

    if not matches:
        print("No possible/unverified lead matched this lexical search.")
        return 1

    print("No canonical conclusion is implied by these lead matches.\n")
    for lead in matches:
        print(f"{lead['id']}  {lead['title']}")
        print(f"  status: {lead['status']}  confidence: {lead['confidence']}")
        print(f"  symptom: {lead['symptom']}")
        print(f"  check: {lead['confirmation_check']}")
        print(f"  refute: {lead['refutation_check']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
