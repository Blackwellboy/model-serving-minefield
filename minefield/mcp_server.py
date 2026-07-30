"""Minimal read-only MCP stdio server backed by the generated registry."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from .coverage import build_coverage
from .guided_experiments import specifications
from .log_inspector import inspect_logs
from .matching import search
from .registry import load_registry
from .static_inspector import inspect_files

TOOLS = {
    "search_symptom": "Rank possible traps from symptom and optional stack/model/version.",
    "get_trap": "Return one canonical trap record.",
    "get_stack_checks": "Return likely traps and checks for a serving stack.",
    "get_model_risks": "Return model-family matches without treating absence as safety.",
    "get_coverage_summary": "Return overlapping diagnostic coverage by modality.",
    "interpret_doctor_report": "Separate doctor problem/clean/inconclusive/unavailable scope.",
    "build_reproduction_plan": "Return bounded experiment specifications for trap IDs.",
    "prepare_issue_report": "Prepare a scrubbed Markdown issue draft from supplied text.",
    "inspect_config": "Inspect explicit files within configured allowed roots.",
    "inspect_logs": "Inspect explicit logs within configured allowed roots.",
}


def _result(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, sort_keys=True)}]}


def call_tool(name: str, args: dict[str, Any], registry: dict[str, Any]) -> Any:
    if name == "search_symptom":
        return search(registry, args.get("symptom", ""), stack=args.get("stack"),
                      model=args.get("model"), version=args.get("version"),
                      evidence_status=args.get("evidence_status"))
    if name == "get_trap":
        return next((entry for entry in registry["entries"] if entry["id"] == str(args["id"]).zfill(2)), None)
    if name == "get_stack_checks":
        return search(registry, args.get("stack", ""), stack=args.get("stack"), limit=20)
    if name == "get_model_risks":
        return {
            "matches": search(registry, args.get("model", ""), model=args.get("model"), limit=20),
            "warning": "Absence from the registry is not evidence of safety.",
        }
    if name == "get_coverage_summary":
        return build_coverage(registry)["summary"]
    if name == "interpret_doctor_report":
        report = args.get("report", {})
        findings = report.get("findings", [])
        return {
            "problems": [item for item in findings if item.get("level") == "PROBLEM"],
            "checked_clean": [item for item in findings if item.get("level") == "OK"],
            "inconclusive": [item for item in findings if item.get("level") == "INCONCLUSIVE"],
            "could_not_check": [item for item in findings if item.get("level") == "UNKNOWN"],
            "coverage": report.get("coverage", {}),
            "warning": "Unimplemented scope remains unknown.",
        }
    if name == "build_reproduction_plan":
        wanted = {str(item).zfill(2) for item in args.get("trap_ids", [])}
        return [item for item in specifications(registry) if item["trap_id"] in wanted]
    if name == "prepare_issue_report":
        text = str(args.get("evidence", ""))
        from .redaction import redact_text
        clean, redactions = redact_text(text)
        return {"markdown": "# Minefield report\n\n" + clean, "redactions": redactions}
    if name == "inspect_config":
        return inspect_files(args.get("paths", []), args.get("allowed_roots"))
    if name == "inspect_logs":
        return inspect_logs(args.get("paths", []), args.get("allowed_roots"))
    raise ValueError(f"unknown tool: {name}")


def serve(stdin: Any = sys.stdin, stdout: Any = sys.stdout) -> int:
    registry = load_registry()
    for line in stdin:
        request: Any = None
        try:
            request = json.loads(line)
            method = request.get("method")
            if method == "initialize":
                value = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "model-serving-minefield", "version": "0.1.0"},
                }
            elif method == "tools/list":
                value = {"tools": [{
                    "name": name,
                    "description": description,
                    "inputSchema": {"type": "object", "additionalProperties": True},
                } for name, description in TOOLS.items()]}
            elif method == "tools/call":
                params = request.get("params", {})
                value = _result(call_tool(params["name"], params.get("arguments", {}), registry))
            elif method == "notifications/initialized":
                continue
            else:
                raise ValueError(f"unsupported method: {method}")
            response = {"jsonrpc": "2.0", "id": request.get("id"), "result": value}
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if isinstance(request, dict) else None,
                "error": {"code": -32602, "message": str(exc)},
            }
        stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        stdout.flush()
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
