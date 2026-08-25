#!/usr/bin/env python3
"""Offline maximum-defensible benchmark attribution checker.

The checker does not contact endpoints or mutate state. It answers only this
question: from the supplied A/B metadata, what is the strongest attribution
class the comparison can honestly support?

Exit codes:
  0  inspection completed (claim may still be END_TO_END_COMPOSITE_ONLY)
  1  reserved for unreachable/input transport failures
  2  blocking schema/shape failure or --gate-intended failure
  3  nothing useful to inspect
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3
ROOT = Path(__file__).resolve().parents[1]

LAYERS = ("MODEL", "SERVING_ENGINE", "TRANSPORT")

MODEL_KEYS = (
    "checkpoint_revision",
    "artifact_digest",
    "correctness_gate",
)
SERVING_KEYS = (
    "engine_build",
    "image_digest",
    "endpoint_or_host_identity",
    "flags_digest_or_normalized_flags",
    "actual_isl",
    "actual_osl",
    "concurrency",
)
TRANSPORT_KEYS = (
    "path_class",
    "interface",
    "path_proof",
    "staging_class",
)

# Fields needed to call an unchanged layer "held". Optional image_digest may be
# absent on both arms; asymmetric presence still shows up as a changed field.
MODEL_HOLD_KEYS = ("checkpoint_revision", "artifact_digest")
SERVING_HOLD_KEYS = (
    "engine_build",
    "endpoint_or_host_identity",
    "flags_digest_or_normalized_flags",
    "actual_isl",
    "actual_osl",
    "concurrency",
)
TRANSPORT_HOLD_KEYS = (
    "path_class",
    "interface",
    "path_proof",
    "staging_class",
)

SERVING_REQUIRED_FOR_CLAIM = (
    "engine_build",
    "endpoint_or_host_identity",
    "flags_digest_or_normalized_flags",
    "actual_isl",
    "actual_osl",
    "concurrency",
)

ISL_OSL_REL_TOL = 0.02
ISL_OSL_ABS_TOL = 1.0


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _norm(value):
    return value.strip() if isinstance(value, str) else value


def _values_differ(a, b, *, key: str | None = None) -> bool:
    """Compare controls; tolerate tiny drift only for realized ISL/OSL.

    Concurrency and all other numeric controls compare exactly. Applying token
    length tolerance to concurrency was a review-found attribution bug: c1 vs
    c2 could otherwise be treated as the same serving condition.
    """
    if not _present(a) and not _present(b):
        return False
    if not _present(a) or not _present(b):
        return True
    if key in {"actual_isl", "actual_osl"} and isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > max(
            ISL_OSL_ABS_TOL,
            ISL_OSL_REL_TOL * max(abs(float(a)), abs(float(b)), 1.0),
        )
    return _norm(a) != _norm(b)


def _path_proof_ok(value) -> str:
    """Return PRESENT | ABSENT | INSUFFICIENT for path evidence.

    A literal PRESENT/PASS is an explicit structured assertion. Free text is
    deliberately fail-closed: link-up, negotiated speed or ping alone cannot
    prove which interface carried the benchmark. Free text must mention actual
    route/interface selection plus traffic/counter/peer/bind evidence.
    """
    if not _present(value):
        return "ABSENT"
    text = str(value).strip().upper()
    if text in {"ABSENT", "MISSING", "NONE", "NO", "FALSE", "0"}:
        return "ABSENT"
    if text in {"INSUFFICIENT", "WEAK", "PARTIAL", "UNKNOWN"}:
        return "INSUFFICIENT"
    if text in {"PRESENT", "YES", "TRUE", "OK", "PASS", "1"}:
        return "PRESENT"

    negative = ("NO PROOF", "UNPROVEN", "LINK ONLY", "PING ONLY", "LINK-UP ONLY")
    if any(token in text for token in negative):
        return "INSUFFICIENT"

    route_evidence = any(token in text for token in (
        "ROUTE", "DEV ", "INTERFACE", "SOURCE BIND", "BOUND SOURCE", "NEIGH", "ARP",
    ))
    traffic_evidence = any(token in text for token in (
        "COUNTER", "TX/RX", "RX/TX", "TX ", "RX ", "PACKET", "PEER-SIDE", "PEER SIDE",
    ))
    if route_evidence and traffic_evidence:
        return "PRESENT"

    # Explicitly reject the tempting evidence named by Trap 134.
    if any(token in text for token in ("LINK UP", "LINK-UP", "GB/S", "GBPS", "PING")):
        return "INSUFFICIENT"
    return "INSUFFICIENT"


def _correctness_ok(value) -> str:
    if not _present(value):
        return "ABSENT"
    text = str(value).strip().upper()
    if text in {"PASS", "PASSED", "OK", "GREEN", "TRUE", "YES"}:
        return "PASS"
    if text in {"FAIL", "FAILED", "RED", "FALSE", "NO"}:
        return "FAIL"
    if text in {"ABSENT", "MISSING", "NONE", "UNKNOWN"}:
        return "ABSENT"
    return "UNKNOWN"


def _gpudirect_inferred_from_managed(transport: dict) -> bool:
    if transport.get("gpudirect_claimed") is not True:
        return False
    evidence = str(transport.get("gpudirect_evidence") or "").upper()
    staging = str(transport.get("staging_class") or "").upper()
    weak = (
        not evidence
        or evidence in {"ABSENT", "NONE", "INFERRED", "CUDA_MANAGED_ONLY", "MANAGED_ONLY"}
        or "CUDA_MANAGED" in evidence
    )
    managed = "MANAGED" in staging or "CUDA_MANAGED" in evidence
    return weak and managed


def _snapshot(arm: dict, layer: str) -> dict:
    key = {
        "MODEL": "model",
        "SERVING_ENGINE": "serving_engine",
        "TRANSPORT": "transport",
    }[layer]
    value = arm.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _keys(layer: str):
    return {
        "MODEL": MODEL_KEYS,
        "SERVING_ENGINE": SERVING_KEYS,
        "TRANSPORT": TRANSPORT_KEYS,
    }[layer]


def _hold_keys(layer: str):
    return {
        "MODEL": MODEL_HOLD_KEYS,
        "SERVING_ENGINE": SERVING_HOLD_KEYS,
        "TRANSPORT": TRANSPORT_HOLD_KEYS,
    }[layer]


def _empty_report(status: str, reason: str, *, missing=None) -> dict:
    return {
        "status": status,
        "changed_dimensions": [],
        "missing_required_fields": list(missing or []),
        "held_dimensions": [],
        "unheld_dimensions": list(LAYERS),
        "path_proof_status": "ABSENT",
        "correctness_gate_status": "ABSENT",
        "max_defensible_claim": "END_TO_END_COMPOSITE_ONLY",
        "reasons": [reason],
        "gpudirect_inference_rejected": False,
        "intended_changed_layer": None,
    }


def evaluate_pair(doc: dict) -> dict:
    if not isinstance(doc, dict) or not doc:
        return _empty_report("UNKNOWN", "empty or non-object document", missing=["document"])

    intended = doc.get("intended_changed_layer")
    if intended not in LAYERS:
        return _empty_report(
            "FAIL",
            "intended_changed_layer must be MODEL|SERVING_ENGINE|TRANSPORT",
            missing=["intended_changed_layer"],
        )

    # Validate raw arms before fallback/coercion. A document containing only an
    # intended layer is a blocking shape failure, not a successful inspection.
    raw_a = doc.get("arm_a")
    raw_b = doc.get("arm_b")
    if not isinstance(raw_a, dict) or not isinstance(raw_b, dict):
        return _empty_report("FAIL", "arm_a and arm_b must be objects", missing=["arm_a", "arm_b"])
    arm_a, arm_b = raw_a, raw_b

    reasons: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    held: list[str] = []
    unheld: list[str] = []

    for layer in LAYERS:
        sa, sb = _snapshot(arm_a, layer), _snapshot(arm_b, layer)
        prefix = {
            "MODEL": "model",
            "SERVING_ENGINE": "serving_engine",
            "TRANSPORT": "transport",
        }[layer]

        layer_changed = False
        for key in _keys(layer):
            va, vb = sa.get(key), sb.get(key)
            if not _present(va):
                missing.append(f"arm_a.{prefix}.{key}")
            if not _present(vb):
                missing.append(f"arm_b.{prefix}.{key}")
            if _values_differ(va, vb, key=key):
                layer_changed = True

        hold_ready = all(
            _present(sa.get(key))
            and _present(sb.get(key))
            and not _values_differ(sa.get(key), sb.get(key), key=key)
            for key in _hold_keys(layer)
        )

        if layer_changed:
            changed.append(layer)
            if layer != intended:
                unheld.append(layer)
                reasons.append(f"{layer} differs while intended change is {intended}")
        elif hold_ready:
            held.append(layer)
        else:
            unheld.append(layer)
            reasons.append(f"{layer} cannot be treated as held: required controls missing or unequal")

    pa = _path_proof_ok(_snapshot(arm_a, "TRANSPORT").get("path_proof"))
    pb = _path_proof_ok(_snapshot(arm_b, "TRANSPORT").get("path_proof"))
    if pa == pb == "PRESENT":
        path_proof_status = "PRESENT"
    elif pa == pb == "ABSENT":
        path_proof_status = "ABSENT"
    else:
        path_proof_status = "INSUFFICIENT"
    if path_proof_status != "PRESENT":
        reasons.append(f"path proof not proven on both arms (arm_a={pa}, arm_b={pb})")

    ca = _correctness_ok(_snapshot(arm_a, "MODEL").get("correctness_gate"))
    cb = _correctness_ok(_snapshot(arm_b, "MODEL").get("correctness_gate"))
    if ca == cb == "PASS":
        correctness_gate_status = "PASS"
    elif "FAIL" in {ca, cb}:
        correctness_gate_status = "FAIL"
        reasons.append("correctness_gate failed on at least one arm")
    elif "ABSENT" in {ca, cb}:
        correctness_gate_status = "ABSENT"
        reasons.append("correctness_gate absent on at least one arm")
    else:
        correctness_gate_status = "UNKNOWN"
        reasons.append("correctness_gate is not a clear PASS on both arms")

    gpudirect_rejected = False
    for label, arm in (("arm_a", arm_a), ("arm_b", arm_b)):
        if _gpudirect_inferred_from_managed(_snapshot(arm, "TRANSPORT")):
            gpudirect_rejected = True
            reasons.append(f"{label}: GPUDirect claim inferred from CUDA-managed/staging alone is insufficient")

    intended_changed = intended in changed
    other_layers = [layer for layer in LAYERS if layer != intended]
    others_held = all(layer in held for layer in other_layers)
    if not intended_changed:
        reasons.append(f"intended layer {intended} has no concrete metadata change")
        others_held = False

    # Missing required fields lower, never raise, attribution confidence.
    if intended == "MODEL":
        for arm_name, arm in (("arm_a", arm_a), ("arm_b", arm_b)):
            model = _snapshot(arm, "MODEL")
            for key in ("checkpoint_revision", "artifact_digest"):
                if not _present(model.get(key)):
                    reasons.append(f"MODEL claim blocked: missing {arm_name}.model.{key}")
                    others_held = False

    if intended == "SERVING_ENGINE":
        for arm_name, arm in (("arm_a", arm_a), ("arm_b", arm_b)):
            serving = _snapshot(arm, "SERVING_ENGINE")
            for key in SERVING_REQUIRED_FOR_CLAIM:
                if not _present(serving.get(key)):
                    reasons.append(f"SERVING_ENGINE claim blocked: missing {arm_name}.serving_engine.{key}")
                    others_held = False

    if intended == "TRANSPORT":
        if path_proof_status != "PRESENT":
            reasons.append("TRANSPORT claim requires actual path proof on both arms")
            others_held = False
        if gpudirect_rejected:
            reasons.append("TRANSPORT claim blocked while GPUDirect evidence is insufficient")
            others_held = False

    if correctness_gate_status != "PASS":
        reasons.append("performance attribution requires PASS correctness_gate on both arms")
        others_held = False

    max_claim = intended if others_held and intended_changed and not gpudirect_rejected else "END_TO_END_COMPOSITE_ONLY"

    def uniq(values):
        out = []
        for value in values:
            if value not in out:
                out.append(value)
        return out

    return {
        "status": "PASS",
        "changed_dimensions": uniq(changed),
        "missing_required_fields": uniq(missing),
        "held_dimensions": uniq(held),
        "unheld_dimensions": uniq(unheld),
        "path_proof_status": path_proof_status,
        "correctness_gate_status": correctness_gate_status,
        "max_defensible_claim": max_claim,
        "reasons": uniq(reasons),
        "gpudirect_inference_rejected": gpudirect_rejected,
        "intended_changed_layer": intended,
    }


def evaluate_path(path: Path) -> tuple[int, dict]:
    if not path.is_file():
        return NOTHING, _empty_report("UNKNOWN", f"not a file: {path}", missing=[str(path)])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - checker must report arbitrary parse failures
        return BLOCKING, _empty_report("FAIL", f"unreadable JSON: {exc}", missing=[str(path)])
    report = evaluate_pair(doc)
    if report["status"] == "FAIL":
        return BLOCKING, report
    if report["status"] == "UNKNOWN":
        return NOTHING, report
    return OK, report


def gate_intended(report: dict) -> int:
    if report.get("status") == "FAIL":
        return BLOCKING
    if report.get("status") == "UNKNOWN":
        return NOTHING
    intended = report.get("intended_changed_layer")
    return OK if intended in LAYERS and report.get("max_defensible_claim") == intended else BLOCKING


def _load_example(name: str) -> dict:
    return json.loads((ROOT / "docs" / name).read_text(encoding="utf-8"))


def _control_model_but_transport_differs():
    return gate_intended(evaluate_pair(_load_example("benchmark-attribution.bad-example.json")))


def _control_transport_missing_path_proof():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["transport"]["path_proof"] = "ABSENT"
    doc["arm_b"]["transport"]["path_proof"] = "ABSENT"
    return gate_intended(evaluate_pair(doc))


def _control_transport_link_only_path_proof():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["transport"]["path_proof"] = "link UP at 1 Gb/s"
    doc["arm_b"]["transport"]["path_proof"] = "link UP at 1 Gb/s"
    return gate_intended(evaluate_pair(doc))


def _control_serving_missing_isl():
    doc = _load_example("benchmark-attribution.example.json")
    doc["intended_changed_layer"] = "SERVING_ENGINE"
    doc["arm_a"]["transport"] = dict(doc["arm_b"]["transport"])
    doc["arm_a"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=old"
    doc["arm_b"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=new"
    doc["arm_a"]["serving_engine"]["actual_isl"] = None
    doc["arm_b"]["serving_engine"]["actual_isl"] = None
    return gate_intended(evaluate_pair(doc))


def _control_serving_missing_concurrency():
    doc = _load_example("benchmark-attribution.example.json")
    doc["intended_changed_layer"] = "SERVING_ENGINE"
    doc["arm_a"]["transport"] = dict(doc["arm_b"]["transport"])
    doc["arm_a"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=old"
    doc["arm_b"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=new"
    doc["arm_a"]["serving_engine"]["concurrency"] = None
    doc["arm_b"]["serving_engine"]["concurrency"] = None
    return gate_intended(evaluate_pair(doc))


def _control_transport_concurrency_differs():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["serving_engine"]["concurrency"] = 1
    doc["arm_b"]["serving_engine"]["concurrency"] = 2
    return gate_intended(evaluate_pair(doc))


def _control_gpudirect_from_managed():
    return gate_intended(evaluate_pair(_load_example("benchmark-attribution.bad-example.json")))


def _control_transport_endpoint_identity_differs():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["serving_engine"]["endpoint_or_host_identity"] = "peer-a"
    doc["arm_b"]["serving_engine"]["endpoint_or_host_identity"] = "peer-b"
    return gate_intended(evaluate_pair(doc))


def _control_correctness_absent():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["model"]["correctness_gate"] = "ABSENT"
    doc["arm_b"]["model"]["correctness_gate"] = "ABSENT"
    return gate_intended(evaluate_pair(doc))


def _control_missing_arms():
    return gate_intended(evaluate_pair({"intended_changed_layer": "TRANSPORT"}))


def _control_empty():
    return gate_intended(evaluate_pair({}))


NEGATIVE_CONTROLS = [
    ("intended MODEL but transport differs is blocked", _control_model_but_transport_differs),
    ("TRANSPORT without path proof is blocked", _control_transport_missing_path_proof),
    ("link-up-only free-text path proof is blocked", _control_transport_link_only_path_proof),
    ("SERVING_ENGINE with missing ISL is blocked", _control_serving_missing_isl),
    ("SERVING_ENGINE with missing concurrency is blocked", _control_serving_missing_concurrency),
    ("TRANSPORT with c1 vs c2 serving concurrency is composite", _control_transport_concurrency_differs),
    ("GPUDirect inferred from managed staging is blocked", _control_gpudirect_from_managed),
    ("TRANSPORT with different endpoint identity is composite", _control_transport_endpoint_identity_differs),
    ("absent correctness gate is blocked", _control_correctness_absent),
    ("missing benchmark arms is a blocking shape failure", _control_missing_arms),
]

EMPTY_SET_CONTROL = ("empty document is not success", _control_empty)

REGRESSION_ASSERTS = [
    (
        "clean TRANSPORT example gates as TRANSPORT",
        lambda: gate_intended(evaluate_pair(_load_example("benchmark-attribution.example.json"))) == OK,
    ),
    (
        "clean TRANSPORT example classifies TRANSPORT",
        lambda: evaluate_pair(_load_example("benchmark-attribution.example.json"))["max_defensible_claim"] == "TRANSPORT",
    ),
]


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", required=True, help="benchmark attribution pair JSON")
    parser.add_argument("--gate-intended", action="store_true", help="exit 2 unless intended claim is defensible")
    parser.add_argument("--json", dest="json_out", help="write machine-readable report")
    args = parser.parse_args(argv)

    code, report = evaluate_path(Path(args.pair))
    if code == OK and args.gate_intended:
        code = gate_intended(report)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
