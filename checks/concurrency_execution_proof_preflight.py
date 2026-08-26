#!/usr/bin/env python3
"""Offline sanity check: client concurrency is not execution concurrency proof.

Reads a JSON document of concurrency ladder rows and flags
CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF when concurrency rises while completed-
work throughput stays approximately flat and batch wall scales with C.

Stdlib-only. No endpoint contact. Does not prove a lock exists; it refuses the
stronger claim that client concurrency alone proves concurrent model execution.

`active_sequences`, when present, is contextual annotation only. A rising
accepted/live sequence count must NOT suppress the wall/throughput flag: that
is exactly the admission-versus-execution distinction Trap 135 describes.

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
import math
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


def _finite_number(value, *, allow_zero: bool = True) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    if num < 0:
        return None
    if not allow_zero and num == 0:
        return None
    return num


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
        if "concurrency" not in r or "batch_wall" not in r or "aggregate_tps" not in r:
            return BLOCKING, [f"row {i} missing required fields concurrency/batch_wall/aggregate_tps"], []
        c = _finite_number(r["concurrency"], allow_zero=False)
        wall = _finite_number(r["batch_wall"], allow_zero=False)
        tps = _finite_number(r["aggregate_tps"], allow_zero=True)
        if c is None or wall is None or tps is None or c < 1:
            return BLOCKING, [
                f"row {i} has invalid concurrency/wall/tps "
                f"(require finite concurrency>=1, wall>0, tps>=0; got "
                f"concurrency={r.get('concurrency')!r} wall={r.get('batch_wall')!r} "
                f"tps={r.get('aggregate_tps')!r})"
            ], []
        c_int = int(c)
        if abs(c - c_int) > 1e-9:
            return BLOCKING, [f"row {i} concurrency must be an integer level"], []
        active_raw = r.get("active_sequences", None)
        active = None
        if active_raw is not None:
            active = _finite_number(active_raw, allow_zero=True)
            if active is None:
                return BLOCKING, [
                    f"row {i} active_sequences must be finite and >=0 when present "
                    f"(got {active_raw!r})"
                ], []
        parsed.append({
            "concurrency": c_int,
            "batch_wall": wall,
            "aggregate_tps": tps,
            "active_sequences": active,
            "label": r.get("label"),
        })

    by_c: dict[int, list] = {}
    for r in parsed:
        by_c.setdefault(r["concurrency"], []).append(r)
    levels = sorted(by_c)
    if len(levels) < 2:
        return NOTHING, ["need at least two distinct concurrency levels to compare"], []

    # Duplicate concurrency levels: require consistent completed-work metrics.
    for c, group in by_c.items():
        if len(group) < 2:
            continue
        walls = {round(item["batch_wall"], 6) for item in group}
        tpss = {round(item["aggregate_tps"], 6) for item in group}
        if len(walls) > 1 or len(tpss) > 1:
            return BLOCKING, [
                f"duplicate concurrency C{c} rows disagree on batch_wall/aggregate_tps"
            ], []

    # No completed-work throughput anywhere: nothing useful to prove scaling.
    if all(item["aggregate_tps"] <= 0 for item in parsed):
        return NOTHING, [
            "all rows have aggregate_tps<=0; no completed-work throughput to compare "
            "(cannot prove or refute execution concurrency)"
        ], []

    findings = []
    flags = []
    notes = []
    comparable_pairs = 0
    base_c = levels[0]
    base = by_c[base_c][0]

    if base["aggregate_tps"] <= 0:
        # Cannot form a flatness ratio from a zero baseline.
        positives = [c for c in levels[1:] if by_c[c][0]["aggregate_tps"] > 0]
        if positives:
            return NOTHING, [
                f"baseline C{base_c} aggregate_tps is 0 while later levels are positive; "
                f"refusing a fake ratio from a zero baseline"
            ], []
        return NOTHING, [
            f"baseline C{base_c} aggregate_tps is 0; no completed-work baseline to compare"
        ], []

    for c in levels[1:]:
        row = by_c[c][0]
        c_ratio = c / base_c
        if c_ratio < 1.5:
            continue
        if row["aggregate_tps"] < 0:
            return BLOCKING, [f"row C{c} has negative aggregate_tps"], []
        comparable_pairs += 1
        wall_ratio = row["batch_wall"] / base["batch_wall"]
        tps_ratio = row["aggregate_tps"] / base["aggregate_tps"]
        wall_scales = wall_ratio >= WALL_SCALE_MIN * c_ratio
        tps_flat = abs(tps_ratio - 1.0) <= FLAT_TPS_TOL

        active_note = ""
        if row.get("active_sequences") is not None and base.get("active_sequences") is not None:
            try:
                active_ratio = float(row["active_sequences"]) / float(base["active_sequences"]) \
                    if float(base["active_sequences"]) > 0 else None
            except (TypeError, ValueError, ZeroDivisionError):
                active_ratio = None
            if active_ratio is not None and active_ratio >= 1.5:
                active_note = (
                    " reported active_sequences rose with client concurrency, but "
                    "completed-work scaling still does not prove simultaneous execution;"
                )
            elif active_ratio is not None and active_ratio <= 1.25:
                active_note = (
                    " reported active_sequences stayed ~flat, consistent with "
                    "serialized execution;"
                )

        if wall_scales and tps_flat:
            flags.append("CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF")
            findings.append(
                f"C{base_c}->C{c}: batch_wall x{wall_ratio:.2f} (C x{c_ratio:.2f}) while "
                f"aggregate_tps x{tps_ratio:.2f} stays ~flat -{active_note} "
                f"client concurrency is not execution-concurrency proof (trap 135)."
            )
        elif wall_scales and not tps_flat:
            notes.append(
                f"C{base_c}->C{c}: wall scaled (x{wall_ratio:.2f}) but aggregate_tps "
                f"moved (x{tps_ratio:.2f}); not flagged as serialization-shaped."
            )

    if comparable_pairs == 0:
        return NOTHING, [
            "no concurrency pairs with C rising by >=1.5x; nothing useful to compare"
        ], []

    if flags:
        return BLOCKING, findings + notes, sorted(set(flags))
    findings.append(
        f"inspected {len(parsed)} rows across C={levels}; no serialization-shaped "
        f"client-vs-execution proof failure under the default thresholds."
    )
    return OK, findings + notes, []


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
    ("active_sequences_rise_still_flags", lambda: (
        (lambda code, _f, flags: code == BLOCKING and "CLIENT_CONCURRENCY_NOT_EXECUTION_PROOF" in flags)(
            *evaluate({"rows": [
                {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 15.0, "active_sequences": 1},
                {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.0, "active_sequences": 2},
                {"concurrency": 4, "batch_wall": 8.0, "aggregate_tps": 15.0, "active_sequences": 4},
            ]})
        )
    )),
    ("zero_throughput_is_not_ok", lambda: evaluate({"rows": [
        {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": 0},
        {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 0},
        {"concurrency": 4, "batch_wall": 8.0, "aggregate_tps": 0},
    ]})[0] != OK),
    ("nan_tps_blocks", lambda: evaluate({"rows": [
        {"concurrency": 1, "batch_wall": 2.0, "aggregate_tps": float("nan")},
        {"concurrency": 2, "batch_wall": 4.0, "aggregate_tps": 15.0},
    ]})[0] == BLOCKING),
]


if __name__ == "__main__":
    raise SystemExit(main())
