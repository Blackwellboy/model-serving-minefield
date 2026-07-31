#!/usr/bin/env python3
"""Validate community/impact.json against evidence-control rules."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPES = {"ADOPTION","RESOLVED_INCIDENT","CONTRIBUTOR_DISCOVERY","INDEPENDENT_CONFIRMATION"}
EV = {"PUBLIC_PRIMARY","PUBLIC_CORROBORATED","OWNER_REPORTED","CONTRIBUTOR_REPORTED","INCONCLUSIVE"}
SUCCESS_BAN = ("saved hours", "users saved", "millions of", "guaranteed", "#1 adoption")

def main() -> int:
    path = ROOT / "community" / "impact.json"
    data = json.loads(path.read_text())
    fails = []
    ids = set()
    for rec in data:
        iid = rec.get("impact_id")
        if not iid: fails.append("missing impact_id")
        elif iid in ids: fails.append(f"duplicate impact_id {iid}")
        else: ids.add(iid)
        if rec.get("type") not in TYPES: fails.append(f"{iid}: bad type")
        if rec.get("evidence_status") not in EV: fails.append(f"{iid}: bad evidence_status")
        if not rec.get("public_source"): fails.append(f"{iid}: missing public_source")
        if not rec.get("person_or_project"): fails.append(f"{iid}: missing person_or_project")
        if not rec.get("permission_to_publish"): fails.append(f"{iid}: missing permission_to_publish")
        if not rec.get("permission_to_quote"): fails.append(f"{iid}: missing permission_to_quote")
        if rec.get("evidence_status") in ("PUBLIC_PRIMARY","PUBLIC_CORROBORATED") and not str(rec.get("public_source","")).startswith("http"):
            fails.append(f"{iid}: public evidence_status needs http public_source")
        summary = (rec.get("summary") or "").lower()
        for ban in SUCCESS_BAN:
            if ban in summary: fails.append(f"{iid}: unsupported success language: {ban}")
        if rec.get("type") == "CONTRIBUTOR_DISCOVERY" and not rec.get("wording_guardrail"):
            fails.append(f"{iid}: contributor discovery needs wording_guardrail")
        # attribution: contributor work must not credit only maintainer
        pop = (rec.get("person_or_project") or "").lower()
        bb = (rec.get("blackwellboy_role") or "").lower()
        if rec.get("type") == "CONTRIBUTOR_DISCOVERY" and "scottleimroth" not in pop and "contributor" not in pop:
            if "blackwellboy" in pop and "scottleimroth" not in pop:
                fails.append(f"{iid}: contributor work credited only to maintainer")
    if fails:
        print("FAIL community impact integrity:")
        for f in fails: print(" -", f)
        return 1
    print("PASS", len(data), "records")
    return 0

if __name__ == "__main__":
    sys.exit(main())
