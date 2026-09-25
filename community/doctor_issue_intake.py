"""Normalize pasted minefield-doctor JSON from a GitHub issue form.

Issue text is untrusted public input. This module only parses JSON and renders
bounded Markdown; it never executes content from the report.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

MARKER = "<!-- minefield-doctor-normalized -->"


def extract_section(body: str, heading: str = "Doctor JSON") -> str:
    pattern = rf"^###\s+{re.escape(heading)}\s*$\n+(.*?)(?=^###\s+|\Z)"
    match = re.search(pattern, body or "", flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError(f"issue body has no '{heading}' section")
    value = match.group(1).strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", value, flags=re.DOTALL | re.IGNORECASE)
    return fence.group(1).strip() if fence else value


def parse_doctor_json(body: str) -> dict[str, Any]:
    raw = extract_section(body)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Doctor JSON must be an object")
    return data


def _version(data: dict[str, Any]) -> str:
    for key in ("version", "stack_version", "server_version", "build"):
        value = data.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    evidence = data.get("evidence")
    if isinstance(evidence, dict):
        for key in ("version", "stack_version", "server_version", "build"):
            value = evidence.get(key)
            if value not in (None, "", [], {}):
                return str(value)
    return "not reported"


def _count(value: Any) -> str:
    if isinstance(value, (list, tuple, set, dict)):
        return str(len(value))
    if isinstance(value, int):
        return str(value)
    return "?"


def _trap_ids(findings: Any, level: str) -> list[str]:
    out: set[str] = set()
    if not isinstance(findings, list):
        return []
    for finding in findings:
        if not isinstance(finding, dict) or str(finding.get("level", "")).upper() != level:
            continue
        traps = finding.get("traps") or []
        if isinstance(traps, (str, int)):
            traps = [traps]
        if isinstance(traps, list):
            for trap in traps:
                text = str(trap).strip()
                if text:
                    out.add(text.zfill(2) if text.isdigit() else text)
    return sorted(out, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))


def normalize(data: dict[str, Any]) -> str:
    stack = str(data.get("stack") or "not reported")
    model = str(data.get("model") or "not reported")
    coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}
    findings = data.get("findings")

    problems = _trap_ids(findings, "PROBLEM")
    inconclusive = _trap_ids(findings, "INCONCLUSIVE")
    unknown = _trap_ids(findings, "UNKNOWN")
    clean = _trap_ids(findings, "OK")

    lines = [
        MARKER,
        "### Normalized Minefield Doctor intake",
        "",
        "> Auto-extracted from the reporter's pasted Doctor JSON. This is routing metadata, not independent confirmation of a trap.",
        "",
        f"- **Stack:** {stack}",
        f"- **Version/build:** {_version(data)}",
        f"- **Model:** {model}",
        f"- **Requests made:** {data.get('requests_made', 'not reported')}",
        f"- **Coverage:** implemented {_count(coverage.get('implemented'))}; "
        f"executed {_count(coverage.get('executed_on_stack') or coverage.get('executed'))}; "
        f"clean {_count(coverage.get('clean'))}; problems {_count(coverage.get('problems'))}; "
        f"inconclusive {_count(coverage.get('inconclusive'))}; "
        f"not implemented {_count(coverage.get('not_implemented'))}",
        f"- **PROBLEM trap IDs:** {', '.join(problems) if problems else 'none reported'}",
        f"- **INCONCLUSIVE trap IDs:** {', '.join(inconclusive) if inconclusive else 'none reported'}",
        f"- **UNKNOWN trap IDs:** {', '.join(unknown) if unknown else 'none reported'}",
        f"- **OK/CLEAN trap IDs:** {', '.join(clean) if clean else 'none reported'}",
    ]
    coverage_line = data.get("coverage_line")
    if coverage_line:
        lines.extend(["", f"Doctor coverage line: `{str(coverage_line).replace(chr(96), '')}`"])
    return "\n".join(lines) + "\n"


def normalize_issue(body: str) -> str:
    return normalize(parse_doctor_json(body))


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Doctor JSON from a GitHub issue body")
    parser.add_argument("--issue-body", required=True, help="Path containing the issue body")
    parser.add_argument("--output", required=True, help="Markdown output path")
    args = parser.parse_args()
    try:
        with open(args.issue_body, encoding="utf-8") as fh:
            body = fh.read()
        rendered = normalize_issue(body)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        rendered = (
            MARKER
            + "\n### Normalized Minefield Doctor intake\n\n"
            + f"Could not parse the pasted Doctor JSON: `{type(exc).__name__}: {str(exc)[:300]}`\n"
            + "Please edit the issue and paste the complete JSON object produced by Minefield Doctor.\n"
        )
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
