#!/usr/bin/env python3
"""Validate community/impact.json against schema rules and evidence controls.

Does not call the live GitHub API. Source-state checks use committed fields
(source_state, source_state_reason, last_verified, follow_up_state).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "community" / "impact.json"
SCHEMA_PATH = ROOT / "community" / "impact.schema.json"

TYPES = {
    "ADOPTION",
    "RESOLVED_INCIDENT",
    "CONTRIBUTOR_DISCOVERY",
    "INDEPENDENT_CONFIRMATION",
    "DOWNSTREAM_REFERENCE",
}
EV = {
    "PUBLIC_PRIMARY",
    "PUBLIC_CORROBORATED",
    "OWNER_REPORTED",
    "CONTRIBUTOR_REPORTED",
    "INCONCLUSIVE",
}
SOURCE_STATES = {
    "OPEN",
    "CLOSED_COMPLETED",
    "CLOSED_NOT_PLANNED",
    "MERGED",
    "DRAFT",
    "EXTERNAL_STATIC",
    "UNKNOWN",
}
SUCCESS_BAN = (
    "saved hours",
    "users saved",
    "millions of",
    "guaranteed",
    "#1 adoption",
)
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ID_RE = re.compile(r"^impact-[0-9]{8}-[a-z0-9-]+$")
HTTP_RE = re.compile(r"^https://.+")


def _schema_check(data) -> list[str]:
    fails: list[str] = []
    if not isinstance(data, list):
        return ["impact.json top-level must be array"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if schema.get("type") != "array":
        fails.append("impact.schema.json top-level type must be array")
    items = schema.get("items") or {}
    enums = (items.get("properties") or {}).get("type", {}).get("enum") or []
    if "DOWNSTREAM_REFERENCE" not in enums:
        fails.append("schema missing DOWNSTREAM_REFERENCE type")
    if set(enums) != TYPES:
        fails.append(f"schema type enum mismatch: {enums}")
    return fails


def validate_records(data: list) -> list[str]:
    fails: list[str] = []
    fails.extend(_schema_check(data))
    ids: set[str] = set()
    for rec in data:
        if not isinstance(rec, dict):
            fails.append("non-object record")
            continue
        iid = rec.get("impact_id") or "<missing>"
        if not rec.get("impact_id"):
            fails.append("missing impact_id")
        elif not ID_RE.match(rec["impact_id"]):
            fails.append(f"{iid}: impact_id pattern invalid")
        elif rec["impact_id"] in ids:
            fails.append(f"duplicate impact_id {iid}")
        else:
            ids.add(rec["impact_id"])

        if rec.get("type") not in TYPES:
            fails.append(f"{iid}: bad type {rec.get('type')!r}")
        if rec.get("evidence_status") not in EV:
            fails.append(f"{iid}: bad evidence_status")
        if rec.get("source_state") not in SOURCE_STATES:
            fails.append(f"{iid}: bad source_state")
        if not rec.get("source_state_reason"):
            fails.append(f"{iid}: missing source_state_reason")
        if not DATE_RE.match(str(rec.get("date") or "")):
            fails.append(f"{iid}: bad date")
        if not DATE_RE.match(str(rec.get("last_verified") or "")):
            fails.append(f"{iid}: bad last_verified")
        if not HTTP_RE.match(str(rec.get("public_source") or "")):
            fails.append(f"{iid}: public_source must be https URL")
        if not rec.get("person_or_project"):
            fails.append(f"{iid}: missing person_or_project")
        if not rec.get("permission_to_publish"):
            fails.append(f"{iid}: missing permission_to_publish")
        if not rec.get("permission_to_quote"):
            fails.append(f"{iid}: missing permission_to_quote")
        if not rec.get("follow_up_state"):
            fails.append(f"{iid}: missing follow_up_state")
        if not rec.get("minefield_role"):
            fails.append(f"{iid}: missing minefield_role")
        if not rec.get("summary"):
            fails.append(f"{iid}: missing summary")

        maintainers = rec.get("maintainers") or []
        if not isinstance(maintainers, list) or not maintainers:
            fails.append(f"{iid}: maintainers must be non-empty array")

        contributors = rec.get("contributors") or []
        if rec.get("type") == "CONTRIBUTOR_DISCOVERY":
            if not contributors:
                fails.append(
                    f"{iid}: CONTRIBUTOR_DISCOVERY requires contributors[]"
                )
            if not rec.get("wording_guardrail"):
                fails.append(
                    f"{iid}: CONTRIBUTOR_DISCOVERY needs wording_guardrail"
                )
            # Maintainer-only credit is forbidden: contributors must be present
            # and credit_statement (if any) must mention a contributor token.
            credit = (rec.get("credit_statement") or "").lower()
            if credit and contributors:
                if not any(
                    c.lstrip("@").lower() in credit
                    or c.lower() in credit
                    for c in contributors
                ):
                    if "contributor" not in credit:
                        fails.append(
                            f"{iid}: credit_statement must credit a contributor"
                        )
            # person_or_project must not be only a maintainer when contributors exist
            pop = (rec.get("person_or_project") or "").lower()
            maint_tokens = {
                m.lstrip("@").lower() for m in maintainers if isinstance(m, str)
            }
            contrib_tokens = {
                c.lstrip("@").lower() for c in contributors if isinstance(c, str)
            }
            if contrib_tokens and pop:
                pop_norm = pop.replace("@", "")
                only_maint = any(m in pop_norm for m in maint_tokens) and not any(
                    c in pop_norm for c in contrib_tokens
                )
                if only_maint:
                    fails.append(
                        f"{iid}: person_or_project credits maintainer only; "
                        "contributor discovery requires contributor attribution"
                    )

        if rec.get("evidence_status") in (
            "PUBLIC_PRIMARY",
            "PUBLIC_CORROBORATED",
        ) and not str(rec.get("public_source", "")).startswith("http"):
            fails.append(f"{iid}: public evidence_status needs http public_source")

        summary = (rec.get("summary") or "").lower()
        for ban in SUCCESS_BAN:
            if ban in summary:
                fails.append(f"{iid}: unsupported success language: {ban}")

        # Committed source-state contradictions (no live network).
        ss = rec.get("source_state")
        fu = (rec.get("follow_up_state") or "").lower()
        if ss == "OPEN" and fu in ("closed_completed", "closed", "merged"):
            fails.append(
                f"{iid}: follow_up_state claims closed while source_state is OPEN"
            )
        if ss in ("CLOSED_COMPLETED", "CLOSED_NOT_PLANNED", "MERGED") and fu in (
            "open",
            "awaiting_reporter",
            "awaiting_control",
        ):
            # only if follow_up explicitly claims still open waiting
            if "pending" not in fu:
                fails.append(
                    f"{iid}: follow_up_state open-ish while source_state is {ss}"
                )
        # Known issue identity checks from related_issue URL when present
        rel = rec.get("related_issue") or ""
        if "/issues/19" in rel and ss != "OPEN":
            fails.append(
                f"{iid}: issue #19 must be recorded source_state=OPEN until closed"
            )
        if "/issues/18" in rel and ss == "OPEN":
            fails.append(
                f"{iid}: issue #18 must not be recorded OPEN (closed adoption)"
            )
        if ss == "OPEN" and "closed" in (rec.get("source_state_reason") or "").lower():
            if "not closed" not in (rec.get("source_state_reason") or "").lower():
                # allow "not closed"; reject "closed as..."
                if re.search(r"\bclosed\b", (rec.get("source_state_reason") or ""), re.I):
                    if "remains open" not in (rec.get("source_state_reason") or "").lower():
                        fails.append(
                            f"{iid}: source_state OPEN contradicts reason claiming closed"
                        )

    return fails


def main() -> int:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    fails = validate_records(data if isinstance(data, list) else data)
    if fails:
        print("FAIL community impact integrity:")
        for f in fails:
            print(" -", f)
        return 1
    n = len(data) if isinstance(data, list) else 0
    print("PASS", n, "records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
