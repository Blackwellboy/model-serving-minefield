#!/usr/bin/env python3
"""Offline preflight for Trap 140: semantic no-progress loops.

Input JSON:
{
  "events": [
    {
      "exact_signature": "sig-a",
      "semantic_class": "generate_script",
      "rejection_class": "INCOMPLETE_SCRIPT",
      "progress": false
    }
  ]
}

The check looks for a consecutive streak of distinct exact signatures that
share one semantic class and one rejection class while making no progress.
It does not execute tools. Exit 0 = inspected and clean, 2 = blocking finding,
3 = nothing inspected.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OK = 0
BLOCKING = 2
NOTHING_INSPECTED = 3


def evaluate(payload: dict, threshold: int = 3) -> tuple[int, dict]:
    events = payload.get("events") or []
    if not events:
        return NOTHING_INSPECTED, {
            "verdict": "NOTHING_INSPECTED",
            "checked": 0,
            "findings": [],
        }

    findings = []
    streak_key = None
    streak_events = []

    for idx, event in enumerate(events, 1):
        semantic = str(event.get("semantic_class") or "").strip()
        rejection = str(event.get("rejection_class") or "").strip()
        signature = str(event.get("exact_signature") or "").strip()
        progress = bool(event.get("progress"))

        if progress or not semantic or not rejection or not signature:
            streak_key = None
            streak_events = []
            continue

        key = (semantic, rejection)
        if key != streak_key:
            streak_key = key
            streak_events = []
        streak_events.append((idx, signature))

        unique = {sig for _i, sig in streak_events}
        if len(streak_events) >= threshold and len(unique) >= threshold:
            findings.append({
                "code": "SEMANTIC_NO_PROGRESS_LOOP",
                "semantic_class": semantic,
                "rejection_class": rejection,
                "threshold": threshold,
                "event_indexes": [i for i, _sig in streak_events[-threshold:]],
                "distinct_exact_signatures": len(unique),
            })
            break

    return (BLOCKING if findings else OK), {
        "verdict": "PROBLEM" if findings else "CLEAN",
        "checked": len(events),
        "threshold": threshold,
        "findings": findings,
    }


def _bad_fixture() -> int:
    return evaluate({"events": [
        {"exact_signature": "a", "semantic_class": "generate_script", "rejection_class": "INCOMPLETE_SCRIPT", "progress": False},
        {"exact_signature": "b", "semantic_class": "generate_script", "rejection_class": "INCOMPLETE_SCRIPT", "progress": False},
        {"exact_signature": "c", "semantic_class": "generate_script", "rejection_class": "INCOMPLETE_SCRIPT", "progress": False},
    ]})[0]


def _empty_fixture() -> int:
    return evaluate({"events": []})[0]


def _progress_breaks_streak() -> bool:
    code, _ = evaluate({"events": [
        {"exact_signature": "a", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": False},
        {"exact_signature": "b", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": True},
        {"exact_signature": "c", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": False},
        {"exact_signature": "d", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": False},
    ]})
    return code == OK


def _same_exact_signature_not_owned_here() -> bool:
    code, _ = evaluate({"events": [
        {"exact_signature": "same", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": False},
        {"exact_signature": "same", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": False},
        {"exact_signature": "same", "semantic_class": "inspect", "rejection_class": "NO_RESULT", "progress": False},
    ]})
    return code == OK


NEGATIVE_CONTROLS = [
    ("three distinct signatures repeat one failed strategy", _bad_fixture),
]
EMPTY_SET_CONTROL = ("no tool events", _empty_fixture)
REGRESSION_ASSERTS = [
    ("real progress resets the semantic streak", _progress_breaks_streak),
    ("exact-repeat loop remains owned by exact-signature guard", _same_exact_signature_not_owned_here),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fixture", help="JSON fixture containing events[]")
    ap.add_argument("--threshold", type=int, default=3)
    ap.add_argument("--json", action="store_true", dest="as_json")
    ns = ap.parse_args(argv)
    if ns.threshold < 2:
        ap.error("--threshold must be >= 2")
    payload = json.loads(Path(ns.fixture).read_text(encoding="utf-8"))
    code, result = evaluate(payload, threshold=ns.threshold)
    if ns.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["verdict"])
        for finding in result["findings"]:
            print(json.dumps(finding, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
