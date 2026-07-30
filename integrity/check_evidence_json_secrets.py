#!/usr/bin/env python3
"""Scan machine-generated evidence JSON without exempting its content."""

from __future__ import annotations

import json
import math
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

SENSITIVE_KEYS = re.compile(
    r"(?i)^(?:password|passwd|pwd|secret|client_secret|api[_-]?key|"
    r"access[_-]?token|auth[_-]?token|authorization|credential|"
    r"private[_-]?key)$"
)
HIGH_ENTROPY = re.compile(r"^[A-Za-z0-9_+/=-]{20,}$")
PUBLIC_DIGEST = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", re.I)
SAFE_HIGH_ENTROPY_KEYS = {
    "revision",
    "sha256",
    "content_sha256",
    "base_main",
    "vllm_revision",
    "kimi_k3_support_revision",
}


def _entropy(value: str) -> float:
    counts = {character: value.count(character) for character in set(value)}
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
    )


def _string_is_suspicious(value: str, key: str | None) -> bool:
    if any(pattern.search(value) for pattern in PATTERNS):
        return True
    if key is not None and SENSITIVE_KEYS.fullmatch(key) and value.strip():
        return True
    if (
        HIGH_ENTROPY.fullmatch(value)
        and not PUBLIC_DIGEST.fullmatch(value)
        and key not in SAFE_HIGH_ENTROPY_KEYS
        and _entropy(value) >= 4.0
    ):
        return True
    return False


def findings(value: Any, path: str = "$", key: str | None = None) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            result.extend(findings(child, f"{path}.{child_key}", child_key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(findings(child, f"{path}[{index}]", key))
    elif isinstance(value, str) and _string_is_suspicious(value, key):
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
