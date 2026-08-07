"""Evidence Packet v1 load/validate preflight (offline).

Terminal states: PASS, HOLD, FAIL, UNKNOWN.
Does not collapse UNKNOWN into PASS.
Does not invent artifact integrity when bytes are unavailable.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .failure_cause import (
    CANONICAL_FAILURE_CAUSES,
    MOVING_REVISION_TOKENS,
    is_infrastructure_or_harness,
)

SCHEMA_VERSION = "1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Minefield evidence-status vocabulary (subset accepted for packets that
# reference published trap evidence). Free-form allowed for non-trap research
# packets, but empty is not.
KNOWN_EVIDENCE_STATUS_PREFIXES = (
    "reproduced here",
    "contributor-measured",
    "reported by others",
    "measured here",
    "under test",
    "PUBLIC_PRIMARY",
    "PUBLIC_CORROBORATION",
    "not a published trap claim",
    "research-incomplete",
)

REQUIRED_TOP = (
    "schema_version",
    "packet_id",
    "experiment_id",
    "target",
    "hypothesis",
    "environment",
    "execution",
    "artifacts",
    "controls",
    "review",
    "claim",
    "sanitization",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_packet(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def preflight(
    packet: dict[str, Any],
    *,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Validate an Evidence Packet. Returns machine-readable report.

    status in {PASS, HOLD, FAIL, UNKNOWN}
    """
    findings: list[dict[str, Any]] = []
    observations = 0

    def note(level: str, code: str, message: str, **extra: Any) -> None:
        row = {"level": level, "code": code, "message": message}
        row.update(extra)
        findings.append(row)

    if not isinstance(packet, dict) or not packet:
        return {
            "status": "UNKNOWN",
            "observed_count": 0,
            "findings": [{
                "level": "UNKNOWN",
                "code": "NO_PACKET",
                "message": "packet missing or empty; nothing observed",
            }],
            "artifact_hash_results": [],
            "matched_rules": ["empty_input"],
        }

    observations += 1  # packet present

    # Schema surface
    missing = [k for k in REQUIRED_TOP if k not in packet]
    if missing:
        note("FAIL", "SCHEMA_MISSING_FIELDS", f"missing top-level fields: {missing}")
    if packet.get("schema_version") != SCHEMA_VERSION:
        note(
            "FAIL",
            "SCHEMA_VERSION",
            f"schema_version must be {SCHEMA_VERSION!r}, got {packet.get('schema_version')!r}",
        )

    target = packet.get("target") if isinstance(packet.get("target"), dict) else {}
    hypothesis = packet.get("hypothesis") if isinstance(packet.get("hypothesis"), dict) else {}
    environment = packet.get("environment") if isinstance(packet.get("environment"), dict) else {}
    execution = packet.get("execution") if isinstance(packet.get("execution"), dict) else {}
    controls = packet.get("controls") if isinstance(packet.get("controls"), dict) else {}
    review = packet.get("review") if isinstance(packet.get("review"), dict) else {}
    claim = packet.get("claim") if isinstance(packet.get("claim"), dict) else {}
    sanitization = packet.get("sanitization") if isinstance(packet.get("sanitization"), dict) else {}
    artifacts = packet.get("artifacts") if isinstance(packet.get("artifacts"), list) else None

    # Target revision pin
    rev = target.get("exact_revision")
    if not rev or not isinstance(rev, str) or not rev.strip():
        note("FAIL", "TARGET_REVISION_MISSING", "target.exact_revision is required")
    else:
        observations += 1
        token = rev.strip()
        if token in MOVING_REVISION_TOKENS or token.lower() in MOVING_REVISION_TOKENS:
            note(
                "FAIL",
                "MOVING_REVISION_ONLY",
                f"exact_revision {token!r} is a moving ref; pin a commit SHA or immutable tag",
            )
        elif re.fullmatch(r"[0-9a-f]{7,40}", token) is None and "/" not in token:
            # Allow non-git pins (image digests, versions) but flag bare branch-like tokens.
            if token.endswith("-latest") or token in {"nightly", "stable"}:
                note(
                    "HOLD",
                    "WEAK_REVISION_PIN",
                    f"exact_revision {token!r} may be moving; prefer immutable digest/SHA",
                )

    id_status = target.get("identity_verification_status")
    if not id_status:
        note("FAIL", "IDENTITY_STATUS_MISSING", "target.identity_verification_status required")

    promotion_dispositions = (
        "CORROBORATE_EXISTING", "EXTEND_EXISTING", "NEW_CHECK", "UNNUMBERED_DRAFT",
    )

    # Hypothesis
    for field in (
        "claim_under_test",
        "expected_confirming_observation",
        "expected_disproof_observation",
    ):
        if not hypothesis.get(field):
            note("FAIL", "HYPOTHESIS_INCOMPLETE", f"hypothesis.{field} required")

    # Environment / model identity when model claims
    cap = claim.get("capability_claim_kind") or "NONE"
    if cap == "MODEL_OR_RUNTIME":
        if not environment.get("model_identity") and not environment.get("engine_identity"):
            note(
                "UNKNOWN",
                "MODEL_IDENTITY_UNOBSERVABLE",
                "MODEL_OR_RUNTIME claim without model_identity or engine_identity",
            )

    if cap in ("MODEL_OR_RUNTIME",) and claim.get("disposition") not in (
        "HOLD", "INCOMPLETE", "MINING_QUESTION", "REJECT_DUPLICATE",
    ):
        # HTTP health alone cannot prove model capability
        auth = execution.get("authentication_interpretation")
        if (
            execution.get("http_status") == 200
            and execution.get("observed_count", 0) == 0
        ):
            note(
                "FAIL",
                "HEALTH_ONLY_CAPABILITY_CLAIM",
                "HTTP 200 with zero observations cannot support a model/runtime claim",
            )
        # HTTP 200 with no generation-like completion is not capability proof
        if (
            execution.get("http_status") == 200
            and execution.get("completion_stop_status") in (
                "CLIENT_TIMEOUT", "SERVER_ERROR", "ABORTED", "UNAVAILABLE", "UNKNOWN",
            )
            and execution.get("failure_cause") in (
                "CLIENT_TIMEOUT", "TRANSPORT_ERROR", "SERVER_ERROR", "AUTH_REQUIRED",
                "AUTH_FAILED", "UNKNOWN_UNADJUDICATED",
            )
        ):
            note(
                "HOLD",
                "HTTP_OK_WITHOUT_SUCCESSFUL_GENERATION",
                "HTTP 200 with non-completed generation cannot support a model/runtime claim",
            )
        if auth in ("AUTH_REQUIRED", "AUTH_FAILED") and claim.get("disposition") not in (
            "HOLD", "INCOMPLETE",
        ):
            note(
                "HOLD",
                "AUTH_BLOCKS_CAPABILITY",
                "authentication blocked or required; capability claim not established",
            )

    # Identity claimed but not verified cannot back promotion-grade dispositions
    if id_status in ("CLAIMED_UNVERIFIED", "UNAVAILABLE") and claim.get(
        "disposition"
    ) in promotion_dispositions:
        note(
            "HOLD",
            "IDENTITY_NOT_VERIFIED",
            "target identity is not VERIFIED; promotion dispositions require verification "
            "or a non-promotion disposition (HOLD/INCOMPLETE/mining/reject)",
        )

    if not environment.get("isolation_workspace_identity"):
        note("FAIL", "ISOLATION_IDENTITY_MISSING", "environment.isolation_workspace_identity required")

    # Execution
    cause = execution.get("failure_cause")
    if cause not in CANONICAL_FAILURE_CAUSES:
        note(
            "FAIL",
            "FAILURE_CAUSE_UNKNOWN_CODE",
            f"execution.failure_cause must be a canonical code, got {cause!r}",
        )
    if "observed_count" not in execution:
        note("FAIL", "OBSERVED_COUNT_MISSING", "execution.observed_count required")
    else:
        try:
            oc = int(execution["observed_count"])
        except (TypeError, ValueError):
            note("FAIL", "OBSERVED_COUNT_INVALID", "observed_count must be an integer")
            oc = -1
        else:
            observations += max(oc, 0)
            if oc == 0 and claim.get("disposition") not in (
                "HOLD", "INCOMPLETE", "MINING_QUESTION", "REJECT_DUPLICATE",
            ):
                # Zero observation cannot silently PASS substantive disposition
                if claim.get("evidence_status", "").startswith("reproduced"):
                    note(
                        "FAIL",
                        "ZERO_OBSERVATION_PASS",
                        "observed_count=0 cannot support reproduced/high-confidence disposition",
                    )
                elif packet.get("execution", {}).get("summary_only") is not True:
                    note(
                        "HOLD",
                        "ZERO_OBSERVATION",
                        "zero relevant observations; not a silent PASS",
                    )

    if execution.get("summary_only") is True and claim.get("disposition") not in (
        "HOLD", "INCOMPLETE", "MINING_QUESTION", "REJECT_DUPLICATE", "GOOD_PRACTICE_NOTE",
    ):
        note(
            "FAIL",
            "SUMMARY_ONLY_PROMOTION",
            "summary_only packet cannot promote beyond hold/incomplete/mining dispositions",
        )

    # Infrastructure misclassified as target negative
    if is_infrastructure_or_harness(cause):
        boundary = (claim.get("claim_boundary") or "").lower()
        if "target negative" in boundary or "model quality negative" in boundary:
            note(
                "FAIL",
                "INFRA_AS_TARGET_NEGATIVE",
                "infrastructure/harness failure_cause must not be claim-boundaried as target negative",
            )
        # Soft check: disposition implying target defect
        if claim.get("disposition") in ("CORROBORATE_EXISTING", "EXTEND_EXISTING") and not boundary:
            note(
                "HOLD",
                "INFRA_CLAIM_BOUNDARY_WEAK",
                "infrastructure cause with promotion disposition needs explicit claim_boundary",
            )

    if cause == "UNKNOWN_UNADJUDICATED" and claim.get("disposition") in (
        "CORROBORATE_EXISTING", "EXTEND_EXISTING",
    ):
        note(
            "HOLD",
            "UNADJUDICATED_PROMOTION",
            "UNKNOWN_UNADJUDICATED is not a genuine negative finding; do not promote as such",
        )
    boundary_l = (claim.get("claim_boundary") or "").lower()
    # Require an affirmative "is/as/was a negative" style claim, not mere
    # discussion that UNKNOWN is *not* a negative finding.
    if cause == "UNKNOWN_UNADJUDICATED":
        affirms_negative = any(
            phrase in boundary_l
            for phrase in (
                "is a negative",
                "as a negative",
                "confirmed negative",
                "target negative",
                "model quality negative",
                "genuine negative finding",
            )
        )
        denies_negative = any(
            phrase in boundary_l
            for phrase in (
                "not a negative",
                "not a genuine negative",
                "is not a negative",
                "not negative",
            )
        )
        if affirms_negative and not denies_negative:
            note(
                "FAIL",
                "UNKNOWN_AS_NEGATIVE",
                "UNKNOWN_UNADJUDICATED must remain distinct from a genuine negative finding",
            )

    # Artifacts
    artifact_hash_results: list[dict[str, Any]] = []
    if artifacts is None:
        note("FAIL", "ARTIFACTS_MISSING", "artifacts must be a list (may be empty only with HOLD)")
        artifacts = []
    if execution.get("summary_only") is not True and len(artifacts) == 0:
        note(
            "FAIL",
            "NO_RAW_ARTIFACTS",
            "non-summary packets require at least one artifact reference",
        )

    for i, art in enumerate(artifacts):
        if not isinstance(art, dict):
            note("FAIL", "ARTIFACT_SHAPE", f"artifacts[{i}] must be object")
            continue
        observations += 1
        sha = art.get("sha256")
        ref = art.get("ref")
        if not ref:
            note("FAIL", "ARTIFACT_REF_MISSING", f"artifacts[{i}].ref required")
        if not sha:
            note("FAIL", "ARTIFACT_HASH_MISSING", f"artifacts[{i}].sha256 required")
        elif sha in ("UNAVAILABLE", "NOT_COMPUTED"):
            note(
                "UNKNOWN",
                "ARTIFACT_HASH_UNVERIFIED",
                f"artifacts[{i}] hash not computed",
                ref=ref,
            )
            artifact_hash_results.append({
                "ref": ref, "result": "ARTIFACT_HASH_UNVERIFIED",
            })
        elif not SHA256_RE.match(str(sha)):
            note(
                "FAIL",
                "ARTIFACT_HASH_MALFORMED",
                f"artifacts[{i}].sha256 must be 64 lowercase hex or UNAVAILABLE/NOT_COMPUTED",
            )
            artifact_hash_results.append({"ref": ref, "result": "MALFORMED"})
        else:
            # Verify when caller claims bytes are available; otherwise format-only.
            if art.get("bytes_available_locally") and ref:
                candidate = Path(ref)
                if not candidate.is_absolute():
                    root = artifact_root or Path(".")
                    candidate = root / ref
                if candidate.is_file():
                    dig = _sha256_file(candidate)
                    if dig == sha:
                        artifact_hash_results.append({
                            "ref": ref, "result": "HASH_OK",
                        })
                        observations += 1
                    else:
                        note(
                            "FAIL",
                            "ARTIFACT_HASH_MISMATCH",
                            f"artifacts[{i}] sha256 mismatch",
                            ref=ref,
                        )
                        artifact_hash_results.append({
                            "ref": ref, "result": "HASH_MISMATCH",
                        })
                else:
                    note(
                        "UNKNOWN",
                        "ARTIFACT_HASH_UNVERIFIED",
                        f"artifacts[{i}] bytes_available_locally=true but path not readable",
                        ref=ref,
                    )
                    artifact_hash_results.append({
                        "ref": ref, "result": "ARTIFACT_HASH_UNVERIFIED",
                    })
            else:
                # Present format-valid hash, bytes not checked
                artifact_hash_results.append({
                    "ref": ref, "result": "HASH_FORMAT_OK_BYTES_NOT_CHECKED",
                })

    # Controls
    for field in ("positive_control", "negative_control", "control_independence_status"):
        if not controls.get(field):
            note("FAIL", "CONTROLS_INCOMPLETE", f"controls.{field} required")
    if "shares_same_harness" not in controls:
        note("FAIL", "CONTROL_HARNESS_FLAG_MISSING", "controls.shares_same_harness required")
    elif controls.get("shares_same_harness") is True and controls.get(
        "control_independence_status"
    ) == "INDEPENDENT":
        # Shared harness claiming independence is a control integrity defect.
        if claim.get("disposition") in promotion_dispositions:
            note(
                "FAIL",
                "CONTROL_INDEPENDENCE_CONFLICT",
                "shares_same_harness=true conflicts with INDEPENDENT; cannot promote",
            )
        else:
            note(
                "HOLD",
                "CONTROL_INDEPENDENCE_CONFLICT",
                "shares_same_harness=true conflicts with independence status INDEPENDENT",
            )
    elif (
        controls.get("shares_same_harness") is True
        and claim.get("disposition") in promotion_dispositions
        and controls.get("control_independence_status") == "SHARED_HARNESS"
    ):
        note(
            "HOLD",
            "SHARED_HARNESS_CONTROL",
            "positive and negative controls share a harness; treat independence as limited",
        )

    # Review
    for field in ("proposer", "reproducer", "falsifier", "adjudicator", "independence_status"):
        if not review.get(field):
            note("FAIL", "REVIEW_INCOMPLETE", f"review.{field} required")
    indep = review.get("independence_status")
    if indep == "INDEPENDENT_REVIEW_WAIVED_WITH_REASON" and not (
        review.get("waiver_reason") or ""
    ).strip():
        note("FAIL", "WAIVER_REASON_MISSING", "waiver_reason required when review is waived")
    roles = [
        (review.get("proposer") or "").strip(),
        (review.get("reproducer") or "").strip(),
        (review.get("falsifier") or "").strip(),
        (review.get("adjudicator") or "").strip(),
    ]
    roles_nonempty = [r for r in roles if r]
    same_actor = len(set(roles_nonempty)) == 1 and len(roles_nonempty) >= 3
    if same_actor and claim.get("disposition") in promotion_dispositions:
        if indep == "INDEPENDENT_REVIEW_PASS":
            note(
                "FAIL",
                "SELF_REVIEW_MARKED_INDEPENDENT",
                "proposer/falsifier/adjudicator are the same actor but independence_status "
                "claims INDEPENDENT_REVIEW_PASS",
            )
        elif indep not in (
            "INDEPENDENT_REVIEW_WAIVED_WITH_REASON",
            "INDEPENDENT_REVIEW_NOT_REQUIRED_FOR_THIS_DISPOSITION",
        ):
            note(
                "HOLD",
                "SELF_REVIEW_UNDISCLOSED",
                "same actor holds multiple review roles; record waiver or "
                "INDEPENDENT_REVIEW_NOT_REQUIRED_FOR_THIS_DISPOSITION",
            )
    if indep == "INDEPENDENT_REVIEW_NOT_AVAILABLE" and claim.get("disposition") in (
        "CORROBORATE_EXISTING", "EXTEND_EXISTING",
    ):
        # Solo human OK with explicit record; agent high-confidence needs waiver or pass
        proposer = (review.get("proposer") or "").lower()
        if "agent" in proposer or "model" in proposer:
            note(
                "HOLD",
                "AGENT_PROMOTION_NEEDS_REVIEW",
                "agent-generated promotion normally needs independent review or explicit waiver",
            )

    # Claim
    if not claim.get("claim_boundary"):
        note("FAIL", "CLAIM_BOUNDARY_MISSING", "claim.claim_boundary required")
    if not claim.get("evidence_status"):
        note("FAIL", "EVIDENCE_STATUS_MISSING", "claim.evidence_status required")
    if not claim.get("disposition"):
        note("FAIL", "DISPOSITION_MISSING", "claim.disposition required")
    if "unresolved_conditions" not in claim or not isinstance(
        claim.get("unresolved_conditions"), list
    ):
        note("FAIL", "UNRESOLVED_CONDITIONS_MISSING", "claim.unresolved_conditions list required")

    # Sanitization consistency
    if sanitization.get("safe_public") is True:
        if sanitization.get("contains_secrets") is True:
            note(
                "FAIL",
                "SANITIZATION_CONTRADICTION",
                "safe_public=true cannot coexist with contains_secrets=true",
            )
        if sanitization.get("contains_private_identifiers") is True and not sanitization.get(
            "redaction_performed"
        ):
            note(
                "FAIL",
                "PRIVATE_IDS_UNREDACTED",
                "safe_public=true with private identifiers requires redaction_performed=true",
            )
    if sanitization.get("allowed_for_public_intake") is True and sanitization.get(
        "contains_secrets"
    ):
        note(
            "FAIL",
            "PUBLIC_INTAKE_WITH_SECRETS",
            "allowed_for_public_intake cannot be true when contains_secrets is true",
        )

    # Health-only capability
    if cap == "HEALTH_ONLY" and claim.get("disposition") in (
        "CORROBORATE_EXISTING", "EXTEND_EXISTING",
    ):
        note(
            "HOLD",
            "HEALTH_ONLY_NOT_CAPABILITY",
            "HEALTH_ONLY claim kind is not model capability proof",
        )

    # Aggregate status
    levels = {f["level"] for f in findings}
    if "FAIL" in levels:
        status = "FAIL"
    elif "UNKNOWN" in levels and "HOLD" not in levels and "FAIL" not in levels:
        # Pure unknown (e.g. unverified hashes) without hard fails
        # If only UNKNOWN and no FAIL/HOLD: UNKNOWN unless clean
        status = "UNKNOWN"
    elif "HOLD" in levels or "UNKNOWN" in levels:
        # HOLD outranks pure pass when mixed with UNKNOWN
        if "HOLD" in levels:
            status = "HOLD"
        else:
            status = "UNKNOWN"
    elif findings:
        status = "HOLD"
    else:
        status = "PASS"

    # Zero findings + zero observed is UNKNOWN not PASS
    if status == "PASS" and observations == 0:
        status = "UNKNOWN"
        note("UNKNOWN", "ZERO_OBSERVATION_PASS_BLOCKED", "no observations; cannot PASS")

    # Unverified artifact hashes alone prevent PASS
    if status == "PASS" and any(
        r.get("result") == "ARTIFACT_HASH_UNVERIFIED" for r in artifact_hash_results
    ):
        status = "UNKNOWN"
        note(
            "UNKNOWN",
            "ARTIFACT_HASH_UNVERIFIED",
            "artifact bytes unavailable; hash not verified - not PASS",
        )

    matched = sorted({f["code"] for f in findings})
    return {
        "status": status,
        "observed_count": observations,
        "findings": findings,
        "artifact_hash_results": artifact_hash_results,
        "matched_rules": matched,
        "could_not_verify": [
            f["message"] for f in findings if f["level"] in ("UNKNOWN", "HOLD")
        ],
    }


def preflight_path(
    path: Path | str,
    *,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {
            "status": "UNKNOWN",
            "observed_count": 0,
            "findings": [{
                "level": "UNKNOWN",
                "code": "PACKET_UNREADABLE",
                "message": f"packet path not readable: {p}",
            }],
            "artifact_hash_results": [],
            "matched_rules": ["packet_unreadable"],
            "packet_path": str(p),
        }
    try:
        packet = load_packet(p)
    except Exception as e:
        return {
            "status": "FAIL",
            "observed_count": 0,
            "findings": [{
                "level": "FAIL",
                "code": "PACKET_JSON_INVALID",
                "message": str(e),
            }],
            "artifact_hash_results": [],
            "matched_rules": ["packet_json_invalid"],
            "packet_path": str(p),
        }
    report = preflight(packet, artifact_root=artifact_root or p.parent)
    report["packet_path"] = str(p)
    return report
