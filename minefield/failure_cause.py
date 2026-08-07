"""Canonical failure-cause codes for Evidence Packets.

See docs/failure-cause-taxonomy.md. This is not evidence_status.
"""

from __future__ import annotations

# Infrastructure / harness causes that must never be silently treated as a
# target-model negative finding.
INFRASTRUCTURE_OR_HARNESS_CAUSES = frozenset({
    "TRANSPORT_ERROR",
    "CLIENT_TIMEOUT",
    "HARNESS_ERROR",
    "TOOL_EXECUTION_ERROR",
    "AUTH_REQUIRED",
    "AUTH_FAILED",
    "WRONG_MODEL_IDENTITY",
    "WRONG_TARGET_REVISION",
    "ENVIRONMENT_CONTAMINATION",
    "SERVER_ERROR",
})

TARGET_ATTRIBUTABLE_CAUSES = frozenset({
    "MODEL_REFUSAL",
    "MODEL_INVALID_OUTPUT",
    "PARSER_REJECTED",
})

CANONICAL_FAILURE_CAUSES = frozenset({
    "NONE",
    "MODEL_REFUSAL",
    "MODEL_INVALID_OUTPUT",
    "PARSER_REJECTED",
    "SERVER_ERROR",
    "TRANSPORT_ERROR",
    "CLIENT_TIMEOUT",
    "HARNESS_ERROR",
    "TOOL_EXECUTION_ERROR",
    "AUTH_REQUIRED",
    "AUTH_FAILED",
    "WRONG_MODEL_IDENTITY",
    "WRONG_TARGET_REVISION",
    "ENVIRONMENT_CONTAMINATION",
    "UNKNOWN_UNADJUDICATED",
})

# Moving refs that are never an "exact" pin for promotion-grade claims.
MOVING_REVISION_TOKENS = frozenset({
    "main",
    "master",
    "HEAD",
    "latest",
    "trunk",
    "develop",
    "dev",
})


def is_canonical_cause(code: str | None) -> bool:
    return isinstance(code, str) and code in CANONICAL_FAILURE_CAUSES


def is_infrastructure_or_harness(code: str | None) -> bool:
    return isinstance(code, str) and code in INFRASTRUCTURE_OR_HARNESS_CAUSES
