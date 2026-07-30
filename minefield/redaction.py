"""Conservative redaction for evidence that may enter a support bundle."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

ASSIGNMENT_PATTERNS = (
    (
        "authorization",
        re.compile(
            r"""(?ix)
            (?P<prefix>(?:"authorization"|'authorization'|authorization)\s*[:=]\s*)
            (?:"(?P<double>(?:\\.|[^"\\])*)"
              |'(?P<single>(?:\\.|[^'\\])*)'
              |(?P<bare>(?:bearer\s+)?[^\s,;}\]]+))
            """
        ),
    ),
    (
        "api-key",
        re.compile(
            r"""(?ix)
            (?P<prefix>
              (?:"(?:api[_-]?key|token|secret|password)"
                |'(?:api[_-]?key|token|secret|password)'
                |(?:api[_-]?key|token|secret|password))
              \s*[:=]\s*
            )
            (?:"(?P<double>(?:\\.|[^"\\])*)"
              |'(?P<single>(?:\\.|[^'\\])*)'
              |(?P<bare>[^\s,;}\]]+))
            """
        ),
    ),
    (
        "cookie",
        re.compile(
            r"""(?ix)
            (?P<prefix>(?:"(?:cookie|set-cookie)"|'(?:cookie|set-cookie)'|(?:cookie|set-cookie))
              \s*[:=]\s*)
            (?:"(?P<double>(?:\\.|[^"\\])*)"
              |'(?P<single>(?:\\.|[^'\\])*)'
              |(?P<bare>[^\r\n]+))
            """
        ),
    ),
)

PATTERNS = (
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("ipv4", re.compile(r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])")),
    ("ipv6", re.compile(r"(?i)(?<![0-9a-f:])(?=[0-9a-f:]*[0-9a-f])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![0-9a-f:])")),
    ("windows-path", re.compile(r"(?i)(?<![\w])(?:[A-Z]:\\|\\\\[^\\\s]+\\)[^\r\n\"'<>|]+")),
    ("unix-path", re.compile(r"(?<![\w])/(?:home|Users|root|var|tmp|opt|srv|etc)/[^\s\"'<>]+")),
    ("hostname", re.compile(r"(?i)(\bhost(?:name)?\s*[:=]\s*)[a-z0-9][a-z0-9.-]{1,252}")),
    ("bracketed-hostname", re.compile(r"(?i)\[(?=[a-z0-9.-]*[a-z-])[a-z0-9][a-z0-9.-]{1,252}\]")),
    ("domain-name", re.compile(
        r"(?i)\b(?![a-z0-9_.-]+\.(?:json|ya?ml|toml|txt|log|py|md|bin|gguf|safetensors)\b)"
        r"(?=[a-z0-9.-]*[a-z])(?:[a-z0-9-]+\.)+[a-z]{2,63}\b"
    )),
    ("username", re.compile(r"(?i)(\buser(?:name)?\s*[:=]\s*)[a-z0-9._-]{1,64}")),
)


def redact_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    report: list[dict[str, Any]] = []
    result = unicodedata.normalize("NFKC", text)
    result = re.sub("[\u200b\u200c\u200d\u2060\ufeff]", "", result)
    if result != text:
        report.append({"kind": "unicode-normalization", "count": 1})
    for label, pattern in ASSIGNMENT_PATTERNS:
        count = 0

        def replace_assignment(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            quote = '"' if match.group("double") is not None else (
                "'" if match.group("single") is not None else ""
            )
            return (
                match.group("prefix")
                + quote
                + f"<REDACTED:{label}>"
                + quote
            )

        result = pattern.sub(replace_assignment, result)
        if count:
            report.append({"kind": label, "count": count})
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


def redact_document(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Use structured redaction for a complete JSON document, else text-safe fallback."""
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            value = json.loads(stripped)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        else:
            clean, report = redact_value(value)
            suffix = "\n" if text.endswith(("\n", "\r")) else ""
            return json.dumps(clean, indent=2, sort_keys=True) + suffix, report
    return redact_text(text)


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
            normalized_key = unicodedata.normalize("NFKC", str(key))
            normalized_key = re.sub(
                "[\u200b\u200c\u200d\u2060\ufeff]", "", normalized_key
            )
            if re.search(
                r"(?i)(token|secret|password|authorization|cookie|api.?key)",
                normalized_key,
            ):
                output[key] = "<REDACTED:secret-field>"
                reports.append({"kind": "secret-field", "count": 1})
            else:
                clean, report = redact_value(item)
                output[key] = clean
                reports.extend(report)
        return output, reports
    return value, []
