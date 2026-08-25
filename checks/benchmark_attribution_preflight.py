#!/usr/bin/env python3
"""benchmark_attribution_preflight: offline max-defensible throughput claim class.

Compares two benchmark metadata arms and reports the strongest claim that is
still defensible. Does not contact endpoints, fetch remotes, or mutate state.

Exit codes (Minefield check contract):
  0  PASS for the *inspection* (report produced; class may still be COMPOSITE)
  1  input unreadable
  2  blocking schema/shape failure
  3  inspected nothing useful (empty input)

    python3 checks/benchmark_attribution_preflight.py --pair path.json
    python3 checks/benchmark_attribution_preflight.py --pair path.json --json out.json

Doctor probes live endpoints. This checker only audits attribution metadata.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3

ROOT = Path(__file__).resolve().parents[1]

LAYERS = ("MODEL", "SERVING_ENGINE", "TRANSPORT")
CLAIM_CLASSES = (
    "MODEL",
    "SERVING_ENGINE",
    "TRANSPORT",
    "END_TO_END_COMPOSITE_ONLY",
)

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

# Keys that must be present+equal for a layer to count as held.
# Optional digests may be null on both sides without breaking a hold.
MODEL_HOLD_KEYS = (
    "checkpoint_revision",
    "artifact_digest",
)
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

# Serving fields that must be present and comparable for a clean SERVING_ENGINE claim.
SERVING_REQUIRED_FOR_CLAIM = (
    "engine_build",
    "flags_digest_or_normalized_flags",
    "actual_isl",
    "actual_osl",
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
    if isinstance(value, str):
        return value.strip()
    return value


def _path_proof_ok(value) -> str:
    """Return PRESENT | ABSENT | INSUFFICIENT."""
    if not _present(value):
        return "ABSENT"
    text = str(value).strip().upper()
    if text in {"ABSENT", "MISSING", "NONE", "NO", "FALSE", "0"}:
        return "ABSENT"
    if text in {"INSUFFICIENT", "WEAK", "PARTIAL", "UNKNOWN"}:
        return "INSUFFICIENT"
    if text in {"PRESENT", "YES", "TRUE", "OK", "PASS", "1"}:
        return "PRESENT"
    # Free-text evidence counts as present only if not obviously negative.
    if any(tok in text for tok in ("ABSENT", "MISSING", "NONE", "NO PROOF", "UNPROVEN")):
        return "INSUFFICIENT"
    return "PRESENT"


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
    claimed = transport.get("gpudirect_claimed")
    evidence = transport.get("gpudirect_evidence")
    staging = transport.get("staging_class")
    if claimed is not True:
        return False
    ev = "" if evidence is None else str(evidence).upper()
    st = "" if staging is None else str(staging).upper()
    weak = (
        "CUDA_MANAGED" in ev
        or "MANAGED_ONLY" in ev
        or ev in {"", "ABSENT", "NONE", "INFERRED", "CUDA_MANAGED_ONLY"}
    )
    managed = "MANAGED" in st or "CUDA_MANAGED" in st
    return weak and (managed or "CUDA_MANAGED" in ev)


def _values_differ(a, b) -> bool:
    # Both missing: no observed change. Absence never proves equality for
    # *holding* a layer - that is handled by required-field presence checks.
    if not _present(a) and not _present(b):
        return False
    if not _present(a) or not _present(b):
        # Asymmetric missing: cannot treat as held/equal.
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > max(
            ISL_OSL_ABS_TOL,
            ISL_OSL_REL_TOL * max(abs(float(a)), abs(float(b)), 1.0),
        )
    return _norm(a) != _norm(b)


def _layer_snapshot(arm: dict, layer: str) -> dict:
    if layer == "MODEL":
        return dict(arm.get("model") or {})
    if layer == "SERVING_ENGINE":
        return dict(arm.get("serving_engine") or {})
    if layer == "TRANSPORT":
        return dict(arm.get("transport") or {})
    return {}


def _required_keys(layer: str):
    if layer == "MODEL":
        return MODEL_KEYS
    if layer == "SERVING_ENGINE":
        return SERVING_KEYS
    if layer == "TRANSPORT":
        return TRANSPORT_KEYS
    return ()


def _hold_keys(layer: str):
    if layer == "MODEL":
        return MODEL_HOLD_KEYS
    if layer == "SERVING_ENGINE":
        return SERVING_HOLD_KEYS
    if layer == "TRANSPORT":
        return TRANSPORT_HOLD_KEYS
    return ()


def evaluate_pair(doc: dict) -> dict:
    reasons = []
    missing = []
    changed = []
    held = []
    unheld = []

    if not isinstance(doc, dict) or not doc:
        return {
            "status": "UNKNOWN",
            "changed_dimensions": [],
            "missing_required_fields": ["document"],
            "held_dimensions": [],
            "unheld_dimensions": [],
            "path_proof_status": "ABSENT",
            "correctness_gate_status": "ABSENT",
            "max_defensible_claim": "END_TO_END_COMPOSITE_ONLY",
            "reasons": ["empty or non-object document"],
            "gpudirect_inference_rejected": False,
        }

    intended = doc.get("intended_changed_layer")
    arm_a = doc.get("arm_a") or {}
    arm_b = doc.get("arm_b") or {}

    if intended not in LAYERS:
        return {
            "status": "FAIL",
            "changed_dimensions": [],
            "missing_required_fields": ["intended_changed_layer"],
            "held_dimensions": [],
            "unheld_dimensions": list(LAYERS),
            "path_proof_status": "ABSENT",
            "correctness_gate_status": "ABSENT",
            "max_defensible_claim": "END_TO_END_COMPOSITE_ONLY",
            "reasons": ["intended_changed_layer must be MODEL|SERVING_ENGINE|TRANSPORT"],
            "gpudirect_inference_rejected": False,
        }

    if not isinstance(arm_a, dict) or not isinstance(arm_b, dict):
        return {
            "status": "FAIL",
            "changed_dimensions": [],
            "missing_required_fields": ["arm_a", "arm_b"],
            "held_dimensions": [],
            "unheld_dimensions": list(LAYERS),
            "path_proof_status": "ABSENT",
            "correctness_gate_status": "ABSENT",
            "max_defensible_claim": "END_TO_END_COMPOSITE_ONLY",
            "reasons": ["arm_a and arm_b must be objects"],
            "gpudirect_inference_rejected": False,
        }

    for layer in LAYERS:
        keys = _required_keys(layer)
        snap_a = _layer_snapshot(arm_a, layer)
        snap_b = _layer_snapshot(arm_b, layer)
        prefix = {
            "MODEL": "model",
            "SERVING_ENGINE": "serving_engine",
            "TRANSPORT": "transport",
        }[layer]
        layer_changed = False
        for key in keys:
            va = snap_a.get(key)
            vb = snap_b.get(key)
            if not _present(va):
                missing.append(f"arm_a.{prefix}.{key}")
            if not _present(vb):
                missing.append(f"arm_b.{prefix}.{key}")
            if _values_differ(va, vb):
                layer_changed = True
        hold_keys = _hold_keys(layer)
        hold_ready = all(
            _present(snap_a.get(k)) and _present(snap_b.get(k)) and not _values_differ(
                snap_a.get(k), snap_b.get(k)
            )
            for k in hold_keys
        )
        if layer_changed:
            changed.append(layer)
            if layer != intended:
                unheld.append(layer)
                reasons.append(
                    f"{layer} differs or is incompletely specified while intended change is {intended}"
                )
            elif not hold_ready and layer == intended:
                # Intended layer changed but incomplete on hold keys of other meaning - no-op.
                pass
        else:
            if hold_ready:
                held.append(layer)
            else:
                unheld.append(layer)
                reasons.append(f"{layer} cannot be treated as held: required fields missing or unequal")

    # Path proof across arms (both must be PRESENT for TRANSPORT claims).
    pa = _path_proof_ok((arm_a.get("transport") or {}).get("path_proof"))
    pb = _path_proof_ok((arm_b.get("transport") or {}).get("path_proof"))
    if pa == "PRESENT" and pb == "PRESENT":
        path_proof_status = "PRESENT"
    elif pa == "ABSENT" and pb == "ABSENT":
        path_proof_status = "ABSENT"
    else:
        path_proof_status = "INSUFFICIENT"
        reasons.append(f"path_proof asymmetric or weak (arm_a={pa}, arm_b={pb})")

    ca = _correctness_ok((arm_a.get("model") or {}).get("correctness_gate"))
    cb = _correctness_ok((arm_b.get("model") or {}).get("correctness_gate"))
    if ca == "PASS" and cb == "PASS":
        correctness_gate_status = "PASS"
    elif ca == "FAIL" or cb == "FAIL":
        correctness_gate_status = "FAIL"
        reasons.append("correctness_gate failed on at least one arm")
    elif ca == "ABSENT" or cb == "ABSENT":
        correctness_gate_status = "ABSENT"
        reasons.append("correctness_gate absent on at least one arm")
    else:
        correctness_gate_status = "UNKNOWN"
        reasons.append("correctness_gate not a clear PASS on both arms")

    gpudirect_rejected = False
    for label, arm in (("arm_a", arm_a), ("arm_b", arm_b)):
        tr = arm.get("transport") or {}
        if _gpudirect_inferred_from_managed(tr):
            gpudirect_rejected = True
            reasons.append(
                f"{label}: GPUDirect claim inferred from CUDA-managed/staging alone is insufficient"
            )

    # Conservative claim selection.
    max_claim = "END_TO_END_COMPOSITE_ONLY"

    other_layers = [L for L in LAYERS if L != intended]
    others_held = all(L in held for L in other_layers)
    intended_changed = intended in changed
    # If intended layer fields are identical, there is no clean single-layer delta.
    if not intended_changed:
        reasons.append(
            f"intended layer {intended} does not show a concrete metadata change between arms"
        )
        others_held = False

    if gpudirect_rejected and intended == "TRANSPORT":
        reasons.append("TRANSPORT claim blocked while GPUDirect inference is insufficient")
        others_held = False

    if intended == "TRANSPORT" and path_proof_status != "PRESENT":
        reasons.append("TRANSPORT claim requires path_proof=PRESENT on both arms")
        others_held = False

    if intended == "SERVING_ENGINE":
        for arm_name, arm in (("arm_a", arm_a), ("arm_b", arm_b)):
            se = arm.get("serving_engine") or {}
            for key in SERVING_REQUIRED_FOR_CLAIM:
                if not _present(se.get(key)):
                    reasons.append(
                        f"SERVING_ENGINE claim blocked: missing {arm_name}.serving_engine.{key}"
                    )
                    others_held = False
        # Material ISL/OSL mismatch blocks clean serving attribution.
        sa = arm_a.get("serving_engine") or {}
        sb = arm_b.get("serving_engine") or {}
        if _values_differ(sa.get("actual_isl"), sb.get("actual_isl")) or _values_differ(
            sa.get("actual_osl"), sb.get("actual_osl")
        ):
            # If ISL/OSL are the intended serving change, still require them present;
            # differing ISL/OSL with missing fields already failed above.
            # When they differ, serving-engine claim is only clean if that is explicit
            # in flags/build change AND both values are present - still conservative:
            # material depth mismatch without held model+transport => composite.
            if "SERVING_ENGINE" in changed and others_held:
                reasons.append(
                    "actual ISL/OSL differ between arms; serving-engine attribution "
                    "requires those depths to be the controlled variable with both present"
                )
            # If model/transport not held, already composite. If they are held and
            # ISL/OSL differ as part of serving change, allow only when flags/build also
            # recorded; still mark composite when depths differ without flags change.
            flags_differ = _values_differ(
                sa.get("flags_digest_or_normalized_flags"),
                sb.get("flags_digest_or_normalized_flags"),
            ) or _values_differ(sa.get("engine_build"), sb.get("engine_build"))
            if not flags_differ:
                reasons.append(
                    "ISL/OSL differ without engine/flags change; cannot claim clean SERVING_ENGINE"
                )
                others_held = False

    if intended == "MODEL":
        for arm_name, arm in (("arm_a", arm_a), ("arm_b", arm_b)):
            mo = arm.get("model") or {}
            for key in ("checkpoint_revision", "artifact_digest"):
                if not _present(mo.get(key)):
                    reasons.append(f"MODEL claim blocked: missing {arm_name}.model.{key}")
                    others_held = False

    # Performance comparisons without correctness gate are claim-limited.
    if correctness_gate_status != "PASS":
        reasons.append(
            "performance comparison lacks a PASS correctness_gate on both arms; "
            "claim limited to END_TO_END_COMPOSITE_ONLY"
        )
        others_held = False

    if others_held and intended_changed and not gpudirect_rejected:
        if intended == "TRANSPORT" and path_proof_status == "PRESENT":
            max_claim = "TRANSPORT"
        elif intended == "SERVING_ENGINE":
            max_claim = "SERVING_ENGINE"
        elif intended == "MODEL":
            max_claim = "MODEL"
        else:
            max_claim = "END_TO_END_COMPOSITE_ONLY"
    else:
        max_claim = "END_TO_END_COMPOSITE_ONLY"

    # Deduplicate lists while preserving order.
    def _uniq(seq):
        out = []
        for x in seq:
            if x not in out:
                out.append(x)
        return out

    status = "PASS"
    return {
        "status": status,
        "changed_dimensions": _uniq(changed),
        "missing_required_fields": _uniq(missing),
        "held_dimensions": _uniq(held),
        "unheld_dimensions": _uniq(unheld),
        "path_proof_status": path_proof_status,
        "correctness_gate_status": correctness_gate_status,
        "max_defensible_claim": max_claim,
        "reasons": _uniq(reasons),
        "gpudirect_inference_rejected": gpudirect_rejected,
        "intended_changed_layer": intended,
    }



def evaluate_path(path: Path) -> tuple[int, dict]:
    if not path.is_file():
        report = {
            "status": "UNKNOWN",
            "changed_dimensions": [],
            "missing_required_fields": [str(path)],
            "held_dimensions": [],
            "unheld_dimensions": [],
            "path_proof_status": "ABSENT",
            "correctness_gate_status": "ABSENT",
            "max_defensible_claim": "END_TO_END_COMPOSITE_ONLY",
            "reasons": [f"not a file: {path}"],
            "gpudirect_inference_rejected": False,
        }
        return NOTHING, report
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report any parse failure
        report = {
            "status": "FAIL",
            "changed_dimensions": [],
            "missing_required_fields": [str(path)],
            "held_dimensions": [],
            "unheld_dimensions": [],
            "path_proof_status": "ABSENT",
            "correctness_gate_status": "ABSENT",
            "max_defensible_claim": "END_TO_END_COMPOSITE_ONLY",
            "reasons": [f"unreadable JSON: {exc}"],
            "gpudirect_inference_rejected": False,
        }
        return BLOCKING, report
    report = evaluate_pair(doc)
    if report.get("status") == "FAIL":
        return BLOCKING, report
    if report.get("status") == "UNKNOWN":
        return NOTHING, report
    return OK, report


def gate_intended(report: dict) -> int:
    """Exit helper for contract/tests: intended claim must be defensible."""
    if report.get("status") == "FAIL":
        return BLOCKING
    if report.get("status") == "UNKNOWN":
        return NOTHING
    intended = report.get("intended_changed_layer")
    max_claim = report.get("max_defensible_claim")
    if intended in LAYERS and max_claim == intended:
        return OK
    return BLOCKING


def _load_example(name: str) -> dict:
    return json.loads((ROOT / "docs" / name).read_text(encoding="utf-8"))


def _control_model_but_transport_differs():
    return gate_intended(evaluate_pair(_load_example("benchmark-attribution.bad-example.json")))


def _control_transport_missing_path_proof():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["transport"]["path_proof"] = "ABSENT"
    doc["arm_b"]["transport"]["path_proof"] = "ABSENT"
    return gate_intended(evaluate_pair(doc))


def _control_serving_missing_isl():
    doc = _load_example("benchmark-attribution.example.json")
    doc["intended_changed_layer"] = "SERVING_ENGINE"
    # Hold transport identical with proof.
    doc["arm_a"]["transport"] = dict(doc["arm_b"]["transport"])
    doc["arm_a"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=old"
    doc["arm_b"]["serving_engine"]["flags_digest_or_normalized_flags"] = "flags=new"
    doc["arm_a"]["serving_engine"]["actual_isl"] = None
    doc["arm_b"]["serving_engine"]["actual_isl"] = None
    return gate_intended(evaluate_pair(doc))


def _control_gpudirect_from_managed():
    report = evaluate_pair(_load_example("benchmark-attribution.bad-example.json"))
    if not report.get("gpudirect_inference_rejected"):
        return OK  # defect: should reject - make control fail by returning OK? No: control must NOT return OK.
    # Gate should block the intended MODEL claim on the bad example.
    return gate_intended(report)


def _control_transport_endpoint_identity_differs():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["serving_engine"]["endpoint_or_host_identity"] = "spark-peer-wifi-era"
    doc["arm_b"]["serving_engine"]["endpoint_or_host_identity"] = "spark-peer-wired-era"
    return gate_intended(evaluate_pair(doc))


def _control_correctness_absent():
    doc = _load_example("benchmark-attribution.example.json")
    doc["arm_a"]["model"]["correctness_gate"] = "ABSENT"
    doc["arm_b"]["model"]["correctness_gate"] = "ABSENT"
    return gate_intended(evaluate_pair(doc))


def _control_empty():
    return gate_intended(evaluate_pair({}))


def _control_malformed_intended():
    return gate_intended(evaluate_pair({"schema_version": "1.0", "arm_a": {}, "arm_b": {}}))


NEGATIVE_CONTROLS = [
    ("intended MODEL but transport differs is not a clean MODEL gate", _control_model_but_transport_differs),
    ("intended TRANSPORT without path proof is not a clean TRANSPORT gate", _control_transport_missing_path_proof),
    ("SERVING_ENGINE with missing ISL is not a clean SERVING_ENGINE gate", _control_serving_missing_isl),
    ("GPUDirect inferred from CUDA-managed is not a clean intended gate", _control_gpudirect_from_managed),
    ("absent correctness gate is not a clean TRANSPORT gate", _control_correctness_absent),
    ("TRANSPORT intended but endpoint identity differs is composite", _control_transport_endpoint_identity_differs),
    ("missing intended_changed_layer is blocking", _control_malformed_intended),
]

EMPTY_SET_CONTROL = ("empty document is not success", _control_empty)

REGRESSION_ASSERTS = [
    (
        "clean TRANSPORT example still gates as TRANSPORT",
        lambda: gate_intended(evaluate_pair(_load_example("benchmark-attribution.example.json"))) == OK,
    ),
    (
        "clean TRANSPORT example classifies TRANSPORT",
        lambda: evaluate_pair(_load_example("benchmark-attribution.example.json"))["max_defensible_claim"]
        == "TRANSPORT",
    ),
]


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", required=True, help="path to benchmark attribution pair JSON")
    ap.add_argument(
        "--gate-intended",
        action="store_true",
        help="exit 2 unless max_defensible_claim equals intended_changed_layer",
    )
    ap.add_argument("--json", dest="json_out", help="write machine-readable report")
    args = ap.parse_args(argv)

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
