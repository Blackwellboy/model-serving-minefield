#!/usr/bin/env python3
"""Scan machine-generated evidence JSON without exempting its content."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PATTERNS = (
    re.compile(r"\b(?:github_pat_|gh[opusr]_)[A-Za-z0-9_]{20,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:authorization\s*:\s*bearer|api[_-]?key\s*[=:]|password\s*[=:])"),
)


def findings(value: Any, path: str = "$") -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(findings(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(findings(child, f"{path}[{index}]"))
    elif isinstance(value, str) and any(pattern.search(value) for pattern in PATTERNS):
        result.append(path)
    return result


def main(argv: list[str] | None = None) -> int:
    paths = [Path(item) for item in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        raise SystemExit("usage: check_evidence_json_secrets.py FILE...")
    found: list[str] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        found.extend(f"{path}:{item}" for item in findings(data))
    if found:
        print("credential-like evidence values found:", *found, sep="\n")
        return 1
    print(f"evidence credential scan clean: {len(paths)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
