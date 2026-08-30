#!/usr/bin/env python3
"""Fail when an open [trap] issue is absent from registry/OPEN_TRAP_ISSUES.md.

This is deliberately issue-state aware. An open issue whose title begins
"[trap]" is treated as unsettled Minefield intake until it is either represented
in the preregistered open queue or closed/dispositioned. Pull requests returned
by GitHub's issues endpoint are ignored.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / "registry" / "OPEN_TRAP_ISSUES.md"
DEFAULT_REPO = "Blackwellboy/model-serving-minefield"
SECTION_RE = re.compile(
    r"(?ms)^### (Q\d+)\.[^\n]*\n(?P<body>.*?)(?=^### Q\d+\.|^---\n\n## CLOSED|\Z)"
)


def open_trap_issues(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        raise ValueError("GitHub issues payload must be a JSON list")
    out: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("pull_request"):
            continue
        if item.get("state") != "open":
            continue
        title = str(item.get("title", "")).strip().lower()
        if not title.startswith("[trap]"):
            continue
        number = item.get("number")
        if isinstance(number, int) and number > 0:
            out.append(item)
    return sorted(out, key=lambda x: x["number"])


def queue_sections(queue_text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(0)) for m in SECTION_RE.finditer(queue_text)]


def validate_queue(payload: object, queue_text: str, repo: str = DEFAULT_REPO) -> list[str]:
    findings: list[str] = []
    sections = queue_sections(queue_text)
    seen: dict[int, str] = {}

    for issue in open_trap_issues(payload):
        number = issue["number"]
        url = f"https://github.com/{repo}/issues/{number}"
        owners = [qid for qid, section in sections if url in section]
        if not owners:
            findings.append(
                f"open [trap] issue #{number} is not represented in registry/OPEN_TRAP_ISSUES.md"
            )
            continue
        if len(owners) > 1:
            findings.append(
                f"open [trap] issue #{number} appears in multiple OPEN sections: {', '.join(owners)}"
            )
            continue
        qid = owners[0]
        seen[number] = qid
        section = next(section for sid, section in sections if sid == qid)
        if "- **CONFIRM.**" not in section:
            findings.append(f"{qid} for issue #{number} has no preregistered CONFIRM criterion")
        if "- **REFUTE.**" not in section:
            findings.append(f"{qid} for issue #{number} has no preregistered REFUTE criterion")

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues-json", required=True, type=Path)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--github", action="store_true")
    args = parser.parse_args(argv)

    payload = json.loads(args.issues_json.read_text(encoding="utf-8"))
    queue_text = args.queue.read_text(encoding="utf-8")
    findings = validate_queue(payload, queue_text, args.repo)

    if findings:
        for finding in findings:
            if args.github:
                print(f"::error title=open queue::{finding}")
            else:
                print(f"FAIL: {finding}")
        return 1

    count = len(open_trap_issues(payload))
    print(f"OPEN ISSUE QUEUE CLEAN: {count} open [trap] issue(s) represented with CONFIRM/REFUTE criteria")
    return 0


if __name__ == "__main__":
    sys.exit(main())
