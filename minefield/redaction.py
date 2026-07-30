"""Conservative redaction for evidence that may enter a support bundle."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

PATTERNS = (
    ("authorization", re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+")),
    ("api-key", re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)[^\s,;]+")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("private-ip", re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("windows-user-path", re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")),
    ("unix-home-path", re.compile(r"(?<![\w/])/(?:home|Users)/[^/\s]+")),
)


def redact_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    report: list[dict[str, Any]] = []
    result = unicodedata.normalize("NFKC", text)
    result = re.sub("[\u200b\u200c\u200d\u2060\ufeff]", "", result)
    if result != text:
        report.append({"kind": "unicode-normalization", "count": 1})
    for label, pattern in PATTERNS:
        count = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            prefix = match.group(1) if match.lastindex else ""
            return prefix + f"<REDACTED:{label}>"

        result = pattern.sub(replace, result)
        if count:
            report.append({"kind": label, "count": count})
    return result, report


def redact_value(value: Any) -> tuple[Any, list[dict[str, Any]]]:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        output, reports = [], []
        for item in value:
            clean, report = redact_value(item)
            output.append(clean)
            reports.extend(report)
        return output, reports
    if isinstance(value, dict):
        output, reports = {}, []
        for key, item in value.items():
            if re.search(r"(?i)(token|secret|password|authorization|cookie|api.?key)", str(key)):
                output[key] = "<REDACTED:secret-field>"
                reports.append({"kind": "secret-field", "count": 1})
            else:
                clean, report = redact_value(item)
                output[key] = clean
                reports.extend(report)
        return output, reports
    return value, []
