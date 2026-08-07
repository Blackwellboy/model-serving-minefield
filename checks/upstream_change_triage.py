#!/usr/bin/env python3
"""upstream_change_triage: offline risk-surface prioritisation for changed paths.

Mining tool only. Never claims NEW_TRAP_FOUND from diffs alone.

    python3 checks/upstream_change_triage.py --changes path/list.txt
    git diff --name-only BASE...HEAD | python3 checks/upstream_change_triage.py

Exit codes:
  0  triage completed with at least one observed path
  3  empty change list / nothing observed (NOT a silent substantive PASS)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minefield.upstream_change_triage import (  # noqa: E402
    triage_from_text,
    triage_paths,
)


def adjudicate_report(report: dict) -> int:
    """Map a triage report to check exit codes, including policy rejects."""
    if not isinstance(report, dict) or report.get("observed_count", 0) == 0:
        return NOTHING
    if report.get("new_trap_found") is True:
        return BLOCKING
    # Unmapped paths must not invent trap links
    for pr in report.get("path_results") or []:
        if pr.get("surface") == "UNKNOWN" and pr.get("related_traps"):
            return BLOCKING
    return OK


def evaluate_text(text: str):
    report = triage_from_text(text)
    return adjudicate_report(report), report


def _empty():
    return evaluate_text("")[0]


def _neg_new_trap_claim():
    return adjudicate_report({
        "status": "PASS",
        "observed_count": 1,
        "new_trap_found": True,
        "path_results": [{"path": "x", "surface": "QUANTIZATION", "related_traps": ["10"]}],
    })


def _neg_unmapped_with_traps():
    return adjudicate_report({
        "status": "PASS",
        "observed_count": 1,
        "new_trap_found": False,
        "path_results": [{
            "path": "nope.xyz",
            "surface": "UNKNOWN",
            "related_traps": ["99"],
        }],
    })


NEGATIVE_CONTROLS = [
    ("new_trap_found claim is blocking", _neg_new_trap_claim),
    ("unmapped path with fabricated traps is blocking", _neg_unmapped_with_traps),
]
EMPTY_SET_CONTROL = ("empty change list is not success", _empty)
REGRESSION_ASSERTS = [
    ("template path maps to CHAT_TEMPLATE_RENDERING",
     lambda: triage_paths(["foo/chat_template.jinja"])["high_risk_surfaces"][0]["surface"]
     == "CHAT_TEMPLATE_RENDERING"),
    ("quant path maps to QUANTIZATION",
     lambda: triage_paths(["layers/quantization/fp8.py"])["high_risk_surfaces"][0]["surface"]
     == "QUANTIZATION"),
    ("unknown path does not fabricate traps",
     lambda: (
         triage_paths(["zzz/nope.xyz"])["path_results"][0]["surface"] == "UNKNOWN"
         and not triage_paths(["zzz/nope.xyz"])["path_results"][0]["related_traps"]
         and triage_paths(["zzz/nope.xyz"])["new_trap_found"] is False
     )),
    ("empty list observed_count 0",
     lambda: triage_paths([])["observed_count"] == 0),
    ("never sets new_trap_found",
     lambda: triage_paths(["a/b/chat_template.jinja"])["new_trap_found"] is False),
]


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--changes", help="file of changed paths")
    ap.add_argument("--json", dest="json_out", help="write report JSON")
    args = ap.parse_args(argv)

    if args.changes:
        text = Path(args.changes).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    code, report = evaluate_text(text)
    out = json.dumps(report, indent=2, sort_keys=True)
    print(out)
    if args.json_out:
        Path(args.json_out).write_text(out + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
