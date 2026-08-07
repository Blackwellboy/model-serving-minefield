"""Promotion Receipt v1 - provenance for future promotions.

Not retroactively required for every existing trap.
"""

from __future__ import annotations

import re
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_FIELDS = (
    "schema_version",
    "receipt_id",
    "source_candidate",
    "evidence_packet_sha256",
    "reproducer",
    "falsifier",
    "adjudicator",
    "selected_evidence_status",
    "selected_owner",
    "validators_run",
    "waivers",
    "unresolved_limitations",
    "raw_artifact_refs",
)


def validate_receipt(doc: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not isinstance(doc, dict) or not doc:
        return {
            "status": "UNKNOWN",
            "observed_count": 0,
            "findings": [{"level": "UNKNOWN", "code": "EMPTY", "message": "no receipt"}],
        }

    observed = 1
    for field in REQUIRED_FIELDS:
        if field not in doc:
            findings.append({
                "level": "FAIL",
                "code": "MISSING_FIELD",
                "message": f"missing {field}",
            })

    if doc.get("schema_version") != "1.0":
        findings.append({
            "level": "FAIL",
            "code": "SCHEMA_VERSION",
            "message": f"schema_version must be 1.0, got {doc.get('schema_version')!r}",
        })

    for hash_field in ("evidence_packet_sha256", "blind_review_packet_sha256"):
        val = doc.get(hash_field)
        if val is None and hash_field == "blind_review_packet_sha256":
            continue  # optional
        if val is not None and not (isinstance(val, str) and SHA256_RE.match(val)):
            findings.append({
                "level": "FAIL",
                "code": "MALFORMED_HASH",
                "message": f"{hash_field} must be 64 lowercase hex",
            })

    if not doc.get("adjudicator"):
        findings.append({
            "level": "FAIL",
            "code": "MISSING_ADJUDICATION",
            "message": "adjudicator required",
        })

    if not doc.get("selected_evidence_status"):
        findings.append({
            "level": "FAIL",
            "code": "MISSING_EVIDENCE_STATUS",
            "message": "selected_evidence_status required",
        })

    if isinstance(doc.get("validators_run"), list):
        observed += len(doc["validators_run"])
    else:
        findings.append({
            "level": "FAIL",
            "code": "VALIDATORS_SHAPE",
            "message": "validators_run must be a list",
        })

    levels = {f["level"] for f in findings}
    if "FAIL" in levels:
        status = "FAIL"
    elif findings:
        status = "HOLD"
    else:
        status = "PASS"
    if status == "PASS" and observed == 0:
        status = "UNKNOWN"

    return {
        "status": status,
        "observed_count": observed,
        "findings": findings,
    }
