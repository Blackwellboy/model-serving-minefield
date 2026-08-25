#!/usr/bin/env python3
"""Offline sanity check: client concurrency is not execution concurrency proof.

Reads a JSON document of concurrency ladder rows and flags
CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF when concurrency rises while completed-
work throughput stays approximately flat and batch wall scales with C.

Stdlib-only. No endpoint contact. Does not prove a lock exists; it refuses the
stronger claim that client concurrency alone proves concurrent model execution.

Exit codes:
  0  inspection completed; no serialization-shaped proof failure
  1  reserved (unreachable)
  2  blocking finding (CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF or bad shape)
  3  nothing useful to inspect

    python3 checks/concurrency_execution_proof_preflight.py --ladder path.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3

# Relative tolerance: aggregate TPS considered "flat" if within this fraction
# of the lower-C baseline when concurrency at least doubles.
FLAT_TPS_TOL = 0.25
# Batch wall considered "scales with C" if wall_ratio / c_ratio >= this.
WALL_SCALE_MIN = 0.70


def _rows(doc):
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and isinstance(doc.get("rows"), list):
        return doc["rows"]
    return None


def evaluate(doc):
    """Return (exit_code, findings:list[str], flags:list[str])."""
    rows = _rows(doc)
    if rows is None:
        return BLOCKING, ["document must be a list of rows or {\"rows\": [...]}"], []
    if not rows:
        return NOTHING, ["0 concurrency rows; nothing was inspected"], []

    parsed = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            return BLOCKING, [f"row {i} is not an object"], []
        try:
            c = int(r["concurrency"])
            wall = float(r["batch_wall"])
            tps = float(r["aggregate_tps"])
        except (KeyError, TypeError, ValueError) as exc:
            return BLOCKING, [f"row {i} missing/invalid required fields: {exc}"], []
        if c < 1 or wall <= 0 or tps < 0:
            return BLOCKING, [f"row {i} has non-positive concurrency/wall or negative tps"], []
        active = r.get("active_sequences")
        parsed.append({"concurrency": c, "batch_wall": wall, "aggregate_tps": tps,
                       "active_sequences": active, "label": r.get("label")})

    by_c = {}
    for r in parsed:
        by_c.setdefault(r["concurrency"], []).append(r)
    levels = sorted(by_c)
    if len(levels) < 2:
        return NOTHING, ["need at least two distinct concurrency levels to compare"], []

    findings = []
    flags = []
    base_c = levels[0]
    base = by_c[base_c][0]
    for c in levels[1:]:
        row = by_c[c][0]
        c_ratio = c / base_c
        if c_ratio < 1.5:
            continue
        wall_ratio = row["batch_wall"] / base["batch_wall"]
        tps_ratio = row["aggregate_tps"] / base["aggregate_tps"] if base["aggregate_tps"] else 0.0
        wall_scales = wall_ratio >= WALL_SCALE_MIN * c_ratio
        tps_flat = abs(tps_ratio - 1.0) <= FLAT_TPS_TOL
        active_ok = True
        if row.get("active_sequences") is not None and base.get("active_sequences") is not None:
            try:
                # If reported active sequences do not rise with C, that strengthens the flag.
                active_ok = float(row["active_sequences"]) <= float(base["active_sequences"]) * 1.25
            except (TypeError, ValueError):
                active_ok = True
        if wall_scales and tps_flat and active_ok:
            flags.append("CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF")
            findings.append(
                f"C{base_c}->C{c}: batch_wall x{wall_ratio:.2f} (C x{c_ratio:.2f}) while "
                f"aggregate_tps x{tps_ratio:.2f} stays ~flat - client concurrency is not "
                f"execution-concurrency proof (trap 135)."
            )

    if flags:
        return BLOCKING, findings, sorted(set(flags))
    findings.append(
        f"inspected {len(parsed)} rows across C={levels}; no serialization-shaped "
        f"client-vs-execution proof failure under the default thresholds."
    )
    return OK, findings, []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ladder", required=True, help="JSON ladder path")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)

    path = Path(args.ladder)
    try:
        doc = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKING: cannot read ladder: {exc}", file=sys.stderr)
        return BLOCKING

    code, findings, flags = evaluate(doc)
    for line in findings:
        print(line)
    if flags:
        print("flags:", ", ".join(flags))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "status": {OK: "PASS", BLOCKING: "BLOCKING", NOTHING: "NOTHING"}[code],
            "findings": findings,
            "flags": flags,
        }, indent=2) + "\n")
    return code


# --- check contract controls ---

def _neg_serialized_ladder():
    doc = {"rows": [
        {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0},
        {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.2},
        {"concurrency": 4, "batch_wall": 8.0, "aggregate_tps": 14.8},
    ]}
    code, _, flags = evaluate(doc)
    return code if "CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF" in flags else OK


def _neg_bad_shape():
    code, _, _ = evaluate({"rows": [{"concurrency": 1, "batch_wall": "x"}]})
    return code


def _empty_set():
    code, _, _ = evaluate({"rows": []})
    return code


NEGATIVE_CONTROLS = [
    ("serialized_ladder_flags", _neg_serialized_ladder),
    ("bad_shape_blocks", _neg_bad_shape),
]
EMPTY_SET_CONTROL = ("empty_rows_not_success", _empty_set)

REGRESSION_ASSERTS = [
    ("scaling_throughput_is_ok", lambda: evaluate({"rows": [
        {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0},
        {"concurrency": 2, "batch_wall": 2.1, "aggregate_tps": 29.0},
        {"concurrency": 4, "batch_wall": 2.2, "aggregate_tps": 55.0},
    ]})[0] == OK),
]


if __name__ == "__main__":
    raise SystemExit(main())
