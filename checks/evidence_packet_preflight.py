#!/usr/bin/env python3
"""evidence_packet_preflight: offline Evidence Packet integrity gate.

Validates machine-readable Evidence Packet v1 documents. Does not call
endpoints, does not restart services, does not allocate trap numbers.

Exit codes (Minefield check contract):
  0  PASS
  1  unreachable / unreadable input treated as hard failure path for CLI
  2  FAIL (blocking integrity finding)
  3  UNKNOWN or HOLD (inspected with unresolved verification) - NOT a pass

    python3 checks/evidence_packet_preflight.py --packet path.json
    python3 checks/evidence_packet_preflight.py --packet path.json --json out.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minefield.evidence_packet import preflight, preflight_path  # noqa: E402


def evaluate_packet(doc, artifact_root=None):
    report = preflight(doc, artifact_root=artifact_root)
    status = report["status"]
    if status == "PASS":
        return OK, report
    if status == "FAIL":
        return BLOCKING, report
    if status in ("HOLD", "UNKNOWN"):
        return NOTHING, report
    return NOTHING, report


def _fixture_pass():
    p = ROOT / "docs/evidence-packet.examples/pass.example.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    return evaluate_packet(doc)[0]


def _fixture_bad():
    p = ROOT / "docs/evidence-packet.examples/bad.example.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    code, _ = evaluate_packet(doc)
    return code


def _fixture_unknown():
    p = ROOT / "docs/evidence-packet.examples/unknown.example.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    return evaluate_packet(doc)[0]


def _fixture_empty():
    return evaluate_packet({})[0]


def _fixture_zero_obs_reproduced():
    p = ROOT / "docs/evidence-packet.examples/pass.example.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["execution"]["observed_count"] = 0
    doc["claim"]["evidence_status"] = "reproduced here"
    return evaluate_packet(doc)[0]


NEGATIVE_CONTROLS = [
    ("intentionally bad packet is blocking or not-clean", _fixture_bad),
    ("zero-observation reproduced claim is not clean", _fixture_zero_obs_reproduced),
]
EMPTY_SET_CONTROL = ("empty packet is not success", _fixture_empty)
REGRESSION_ASSERTS = [
    ("clean pass example still reaches exit 0", lambda: _fixture_pass() == OK),
    ("unknown example is not exit 0", lambda: _fixture_unknown() != OK),
]


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet", required=True, help="path to Evidence Packet JSON")
    ap.add_argument("--artifact-root", help="root for resolving relative artifact paths")
    ap.add_argument("--json", dest="json_out", help="write machine-readable report")
    args = ap.parse_args(argv)

    path = Path(args.packet)
    if not path.is_file():
        report = {
            "status": "UNKNOWN",
            "observed_count": 0,
            "findings": [{
                "level": "UNKNOWN",
                "code": "PACKET_UNREADABLE",
                "message": f"not a file: {path}",
            }],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return NOTHING

    root = Path(args.artifact_root) if args.artifact_root else path.parent
    report = preflight_path(path, artifact_root=root)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")

    status = report["status"]
    if status == "PASS":
        return OK
    if status == "FAIL":
        return BLOCKING
    return NOTHING


if __name__ == "__main__":
    raise SystemExit(main())
