"""Bounded classification of inline-system behavior from rendered evidence.

This module never contacts an endpoint and never executes checkpoint code. It
classifies already captured renders, token evidence, or endpoint response
files. Source inspection and model output alone are deliberately insufficient
for a definitive rendered-prompt classification.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

CLASSIFICATIONS = (
    "ROLE_MARKED",
    "DROPPED",
    "WELDED_TO_USER",
    "REJECTED",
    "AMBIGUOUS",
    "INCONCLUSIVE",
)

EVIDENCE_SURFACES = (
    "SOURCE_INSPECTED_AT_PINNED_REVISION",
    "TEMPLATE_EXECUTED_AT_PINNED_REVISION",
    "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
    "ENDPOINT_RENDER_REPRODUCED",
    "MODEL_OUTPUT_REPRODUCED",
    "UNDER_TEST",
    "INCONCLUSIVE",
)

RENDER_SURFACES = {
    "TEMPLATE_EXECUTED_AT_PINNED_REVISION",
    "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
    "ENDPOINT_RENDER_REPRODUCED",
}

MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_MARKERS = 64
MAX_TARGETS = 32


class EvidenceError(ValueError):
    """The evidence manifest is malformed or exceeds a hard bound."""


def _bounded_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise EvidenceError(f"{field} must be a string")
    if len(value.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise EvidenceError(f"{field} exceeds the size limit")
    return value


def _record_text(record: dict[str, Any], name: str) -> tuple[str | None, list[str]]:
    """Extract one authoritative decoded render and detect disagreements."""
    candidates: list[tuple[str, str]] = []
    for key in (
        "rendered_text",
        "decoded_text",
        "rendered_prompt",
        "prompt",
        "decoded_from_token_ids",
        "decoded_from_token_strings",
    ):
        value = _bounded_text(record.get(key), f"{name}.{key}")
        if value is not None:
            candidates.append((key, value))
    token_strings = record.get("token_strings")
    if token_strings is not None:
        if (
            not isinstance(token_strings, list)
            or any(not isinstance(item, str) for item in token_strings)
        ):
            raise EvidenceError(f"{name}.token_strings must be an array of strings")
        value = _bounded_text(
            "".join(token_strings), f"{name}.token_strings joined"
        )
        candidates.append(("token_strings", value or ""))
    response = record.get("endpoint_response")
    if response is not None:
        if not isinstance(response, dict):
            raise EvidenceError(f"{name}.endpoint_response must be an object")
        for key in ("rendered_text", "rendered_prompt", "prompt", "decoded_text"):
            value = _bounded_text(response.get(key), f"{name}.endpoint_response.{key}")
            if value is not None:
                candidates.append((f"endpoint_response.{key}", value))
    if not candidates:
        return None, []
    first = candidates[0][1]
    disagreement = [key for key, value in candidates[1:] if value != first]
    return first, disagreement


def _is_rejected(record: dict[str, Any]) -> bool:
    """Return true only for an explicit semantic constructor rejection."""
    return (
        record.get("rejected") is True
        and record.get("rejection_stage") in {"constructor", "request_validation"}
    )


def _has_capture_failure(record: dict[str, Any]) -> bool:
    if record.get("capture_failed") is True:
        return True
    for source in (record, record.get("endpoint_response")):
        if not isinstance(source, dict):
            continue
        status = source.get("status", source.get("status_code"))
        if isinstance(status, int) and status >= 400:
            return True
        if source.get("error") not in (None, "", False):
            return True
    return record.get("rejected") is True


def _normalise_markers(value: Any) -> list[dict[str, str | None]]:
    if value is None:
        return []
    markers: list[dict[str, str | None]] = []
    if isinstance(value, dict):
        expanded = []
        for role, items in value.items():
            if isinstance(items, str):
                items = [items]
            if not isinstance(items, list):
                raise EvidenceError("marker values must be strings or arrays")
            expanded.extend({"role": role, "open": item} for item in items)
        value = expanded
    if not isinstance(value, list) or len(value) > MAX_MARKERS:
        raise EvidenceError(f"markers must be an array of at most {MAX_MARKERS} items")
    for item in value:
        if not isinstance(item, dict):
            raise EvidenceError("each marker must be an object")
        role = item.get("role")
        opening = item.get("open")
        closing = item.get("close")
        if role not in {"system", "user", "assistant", "tool", "developer", "root"}:
            raise EvidenceError(f"unsupported marker role: {role}")
        if not isinstance(opening, str) or not opening:
            raise EvidenceError("marker open must be a non-empty string")
        if closing is not None and (not isinstance(closing, str) or not closing):
            raise EvidenceError("marker close must be a non-empty string")
        if closing == opening:
            raise EvidenceError("marker open and close must differ")
        markers.append({"role": role, "open": opening, "close": closing})
    openings = [str(marker["open"]) for marker in markers]
    if len(set(openings)) != len(openings):
        raise EvidenceError("marker open strings must be unique")
    for index, opening in enumerate(openings):
        if any(
            opening.startswith(other) or other.startswith(opening)
            for other in openings[index + 1 :]
        ):
            raise EvidenceError("marker open strings must not overlap by prefix")
    return markers


def _marker_events(text: str, markers: list[dict[str, str | None]]) -> list[dict[str, Any]]:
    events = []
    for marker in markers:
        start = 0
        while True:
            pos = text.find(str(marker["open"]), start)
            if pos < 0:
                break
            events.append({
                "role": marker["role"],
                "open": marker["open"],
                "close": marker["close"],
                "marker_start": pos,
                "content_start": pos + len(str(marker["open"])),
            })
            start = pos + max(1, len(str(marker["open"])))
    events.sort(key=lambda item: (item["marker_start"], -len(str(item["open"])), str(item["role"])))
    return events


def _spans(
    text: str, markers: list[dict[str, str | None]]
) -> tuple[list[dict[str, Any]], list[str]]:
    events = _marker_events(text, markers)
    spans = []
    invalid = []
    for index, event in enumerate(events):
        next_start = events[index + 1]["marker_start"] if index + 1 < len(events) else len(text)
        end = next_start
        if event["close"]:
            close_at = text.find(str(event["close"]), event["content_start"])
            if close_at < 0 and event["role"] in {"system", "user"}:
                invalid.append(f"missing close for marker {event['open']}")
            elif close_at > next_start and event["role"] in {"system", "user"}:
                invalid.append(f"another role marker precedes close for {event['open']}")
            else:
                end = close_at
        spans.append({
            "role": event["role"],
            "start": event["content_start"],
            "end": end,
            "open": event["open"],
        })
    return spans, sorted(set(invalid))


def _roles_for(text: str, target: str, spans: list[dict[str, Any]]) -> list[str]:
    roles = []
    start = 0
    while True:
        pos = text.find(target, start)
        if pos < 0:
            break
        containing = sorted({
            str(span["role"]) for span in spans
            if span["start"] <= pos and pos + len(target) <= span["end"]
        })
        roles.extend(containing or ["unmarked"])
        start = pos + max(1, len(target))
    return sorted(set(roles))


def _message_contents(record: dict[str, Any]) -> list[str]:
    messages = record.get("messages", [])
    if not isinstance(messages, list):
        raise EvidenceError("primary.messages must be an array")
    contents = []
    for message in messages:
        if not isinstance(message, dict):
            raise EvidenceError("each message must be an object")
        content = message.get("content")
        if isinstance(content, str):
            contents.append(content)
    return contents


def _result(
    classification: str,
    *,
    surface: str,
    reasons: list[str],
    target_present: bool | None = None,
    system_marker_found: bool | None = None,
    inside_user_span: bool | None = None,
    matches_no_system_control: bool | None = None,
    rejected: bool = False,
    roles_by_target: dict[str, list[str]] | None = None,
    artifact_sha256: str | None = None,
) -> dict[str, Any]:
    if classification not in CLASSIFICATIONS:
        raise AssertionError(classification)
    return {
        "schema_version": "1.0",
        "classification": classification,
        "evidence_surface": surface,
        "target_present": target_present,
        "system_marker_found": system_marker_found,
        "inside_user_span": inside_user_span,
        "matches_no_system_control": matches_no_system_control,
        "rejected": rejected,
        "roles_by_target": roles_by_target or {},
        "artifact_sha256": artifact_sha256,
        "reasons": list(reasons),
        "warning": (
            "Classification applies only to this rendered evidence, immutable "
            "revision, renderer, entrypoint, and marker configuration."
        ),
    }


def classify_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Classify one bounded evidence manifest without executing its contents."""
    if not isinstance(manifest, dict):
        raise EvidenceError("manifest must be an object")
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_EVIDENCE_BYTES:
        raise EvidenceError("manifest exceeds the size limit")
    artifact_sha256 = hashlib.sha256(encoded).hexdigest()
    if manifest.get("schema_version") != "1.0":
        raise EvidenceError("schema_version must be 1.0")
    model = manifest.get("model")
    if (
        not isinstance(model, dict)
        or not isinstance(model.get("name"), str)
        or not model["name"]
        or not isinstance(model.get("revision"), str)
        or re.fullmatch(r"[0-9a-f]{40}", model["revision"]) is None
    ):
        raise EvidenceError("model requires a name and a 40-hex immutable revision")
    for required in ("evidence_surface", "target_texts", "primary", "controls"):
        if required not in manifest:
            raise EvidenceError(f"required manifest field is missing: {required}")
    surface = manifest.get("evidence_surface", "INCONCLUSIVE")
    if surface not in EVIDENCE_SURFACES:
        raise EvidenceError(f"unsupported evidence_surface: {surface}")
    primary = manifest.get("primary")
    if not isinstance(primary, dict):
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["primary rendered evidence is missing"],
        )
    if surface not in RENDER_SURFACES:
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=[
                "source inspection or model output is not executed rendered-prompt evidence"
            ],
        )
    if _is_rejected(primary):
        return _result(
            "REJECTED", surface=surface, artifact_sha256=artifact_sha256,
            rejected=True, target_present=False,
            reasons=["the renderer or endpoint explicitly rejected the primary probe"],
        )
    if _has_capture_failure(primary):
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["the primary evidence capture failed or contains ambiguous error metadata"],
        )
    text, disagreement = _record_text(primary, "primary")
    if disagreement:
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["decoded, token-derived, or endpoint render evidence disagrees: "
                     + ", ".join(disagreement)],
        )
    if text is None:
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["primary probe has no decoded render"],
        )
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        raise EvidenceError("controls must be an object")
    no_system = controls.get("no_system")
    leading_system = controls.get("leading_system")
    no_system_text = None
    leading_text = None
    for name, record in (("controls.no_system", no_system),
                         ("controls.leading_system", leading_system)):
        if record is None:
            continue
        if not isinstance(record, dict):
            raise EvidenceError(f"{name} must be an object")
        if _is_rejected(record) or _has_capture_failure(record):
            return _result(
                "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
                reasons=[f"{name} was rejected or its evidence capture failed"],
            )
        rendered, conflict = _record_text(record, name)
        if conflict:
            return _result(
                "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
                reasons=[f"{name} render evidence disagrees: " + ", ".join(conflict)],
            )
        if name.endswith("no_system"):
            no_system_text = rendered
        else:
            leading_text = rendered
    if no_system is None or leading_system is None:
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["both no-system and leading-system controls are required"],
        )
    if no_system_text is None or leading_text is None:
        return _result(
            "INCONCLUSIVE", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["both controls require decoded rendered evidence"],
        )
    targets = manifest.get("target_texts", ["LATESYS"])
    if (not isinstance(targets, list) or not targets or len(targets) > MAX_TARGETS
            or any(not isinstance(item, str) or not item for item in targets)):
        raise EvidenceError(f"target_texts must contain 1-{MAX_TARGETS} non-empty strings")
    if len(set(targets)) != len(targets):
        raise EvidenceError("target_texts must be unique")
    if any(target != target.strip() for target in targets):
        raise EvidenceError("target_texts must not have leading or trailing whitespace")
    system_messages = {
        message.get("content")
        for message in primary.get("messages", [])
        if isinstance(message, dict) and message.get("role") == "system"
    }
    if any(target not in system_messages for target in targets):
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            reasons=["each target must exactly equal an inline system-message payload"],
        )
    present = {target: target in text for target in targets}
    matches_control = no_system_text is not None and text == no_system_text
    if not any(present.values()):
        if matches_control:
            return _result(
                "DROPPED", surface=surface, artifact_sha256=artifact_sha256,
                target_present=False, system_marker_found=False,
                inside_user_span=False, matches_no_system_control=True,
                reasons=[
                    "all target text is absent and the primary render exactly matches "
                    "the no-system control",
                    "DROPPED is non-welding but lossy",
                ],
            )
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=False, matches_no_system_control=matches_control,
            reasons=[
                "target text is absent but the primary render does not match the "
                "no-system control"
            ],
        )
    if not all(present.values()):
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, matches_no_system_control=matches_control,
            reasons=["some inline-system targets are present and others are absent"],
        )
    markers = _normalise_markers(manifest.get("markers"))
    if not markers:
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, matches_no_system_control=matches_control,
            reasons=["target text is present but no role-boundary markers were supplied"],
        )
    trusted = manifest.get("trusted_structural_markers", [])
    if not isinstance(trusted, list) or any(not isinstance(item, str) for item in trusted):
        raise EvidenceError("trusted_structural_markers must be an array of strings")
    if trusted:
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, matches_no_system_control=matches_control,
            reasons=["caller-asserted trusted structural markers are not accepted"],
        )
    if any(
        str(marker["open"]) in target
        or (marker["close"] is not None and str(marker["close"]) in target)
        for marker in markers
        for target in targets
    ):
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, matches_no_system_control=matches_control,
            reasons=["an inline-system target contains configured marker text"],
        )
    contents = _message_contents(primary)
    tainted = sorted({
        str(marker["open"]) for marker in markers
        if any(str(marker["open"]) in content for content in contents)
        and str(marker["open"]) not in trusted
    })
    if tainted:
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, matches_no_system_control=matches_control,
            reasons=[
                "a configured marker also appears in user-supplied content and "
                "is not token-verified as structural: " + ", ".join(tainted)
            ],
        )
    spans, invalid_spans = _spans(text, markers)
    if invalid_spans:
        return _result(
            "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, matches_no_system_control=matches_control,
            reasons=["role-boundary structure is malformed: " + "; ".join(invalid_spans)],
        )
    roles_by_target = {target: _roles_for(text, target, spans) for target in targets}
    role_sets = [set(roles) for roles in roles_by_target.values()]
    system_marker_found = any("system" in roles for roles in role_sets)
    inside_user = any("user" in roles for roles in role_sets)
    if system_marker_found:
        system_markers = [marker for marker in markers if marker["role"] == "system"]
        if leading_text is None:
            return _result(
                "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
                target_present=True, system_marker_found=True,
                inside_user_span=inside_user, matches_no_system_control=matches_control,
                roles_by_target=roles_by_target,
                reasons=["system marker was not validated against the leading-system control"],
            )
        leading_spans, invalid_leading = _spans(leading_text, system_markers)
        if invalid_leading:
            return _result(
                "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
                target_present=True, system_marker_found=True,
                inside_user_span=inside_user, matches_no_system_control=matches_control,
                roles_by_target=roles_by_target,
                reasons=["leading-system marker structure is malformed"],
            )
        leading_target = str(manifest.get("leading_system_text", "S"))
        if "system" not in _roles_for(leading_text, leading_target, leading_spans):
            return _result(
                "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
                target_present=True, system_marker_found=True,
                inside_user_span=inside_user, matches_no_system_control=matches_control,
                roles_by_target=roles_by_target,
                reasons=["configured system marker does not bound the leading-system control"],
            )
    if all(roles == {"system"} for roles in role_sets):
        return _result(
            "ROLE_MARKED", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, system_marker_found=True,
            inside_user_span=False, matches_no_system_control=matches_control,
            roles_by_target=roles_by_target,
            reasons=["every inline-system target is inside a validated system-role span"],
        )
    if all(roles == {"user"} for roles in role_sets):
        without_targets = text
        for target in targets:
            without_targets = without_targets.replace(target, "", 1)
        if without_targets != no_system_text:
            return _result(
                "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
                target_present=True, system_marker_found=False,
                inside_user_span=True, matches_no_system_control=matches_control,
                roles_by_target=roles_by_target,
                reasons=[
                    "removing the inline-system targets does not reproduce the "
                    "no-system control exactly"
                ],
            )
        return _result(
            "WELDED_TO_USER", surface=surface, artifact_sha256=artifact_sha256,
            target_present=True, system_marker_found=False,
            inside_user_span=True, matches_no_system_control=matches_control,
            roles_by_target=roles_by_target,
            reasons=["every inline-system target is inside a user-role span"],
        )
    return _result(
        "AMBIGUOUS", surface=surface, artifact_sha256=artifact_sha256,
        target_present=True, system_marker_found=system_marker_found,
        inside_user_span=inside_user, matches_no_system_control=matches_control,
        roles_by_target=roles_by_target,
        reasons=["the supplied boundaries do not place every target in one role class"],
    )


def load_manifest(path: str | Path) -> dict[str, Any]:
    target = Path(path).resolve(strict=True)
    if not target.is_file() or target.is_symlink():
        raise EvidenceError("manifest path must be a regular non-symlink file")
    if target.stat().st_size > MAX_EVIDENCE_BYTES:
        raise EvidenceError("manifest exceeds the size limit")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"could not read manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError("manifest must contain a JSON object")
    return value


def inspect_template(path: str | Path) -> dict[str, Any]:
    """Hash a supplied local template without executing it."""
    target = Path(path).resolve(strict=True)
    if not target.is_file() or target.is_symlink():
        raise EvidenceError("template path must be a regular non-symlink file")
    if target.stat().st_size > MAX_EVIDENCE_BYTES:
        raise EvidenceError("template exceeds the size limit")
    data = target.read_bytes()
    return {
        "name": target.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "evidence_surface": "SOURCE_INSPECTED_AT_PINNED_REVISION",
        "execution_warning": (
            "The classifier hashes local Jinja source but does not execute it. "
            "Supply a pinned executed render manifest for classification."
        ),
    }
