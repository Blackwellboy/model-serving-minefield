"""Minimal read-only MCP stdio server backed by the generated registry."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .coverage import build_coverage
from .diagnosis_contract import CONDITION_FIELDS
from .guided_experiments import specifications
from .log_inspector import inspect_logs
from .matching import diagnose, search
from .registry import load_registry
from .static_inspector import inspect_files

TOOLS = {
    "search_symptom": "Return diagnosis-contract candidates from symptom and explicit conditions.",
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
MAX_REQUEST_BYTES = 1024 * 1024
MAX_TEXT_ARGUMENT = 256 * 1024
CONDITION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        field: {"type": ["string", "integer"]}
        for field in CONDITION_FIELDS
    },
}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_symptom": {"properties": {
        "symptom": {"type": "string"}, "stack": {"type": "string"},
        "model": {"type": "string"}, "version": {"type": "string"},
        "evidence_status": {"type": "string"},
        "conditions": CONDITION_SCHEMA,
        "direct_probe_trap_ids": {
            "type": "array", "maxItems": 50, "items": {"type": ["string", "integer"]},
        },
        "direct_probe_results": {
            "type": "object",
            "maxProperties": 50,
            "additionalProperties": {
                "type": "string",
                "enum": ["confirmed", "refuted", "inconclusive"],
            },
        },
        "mechanism_probe_trap_ids": {
            "type": "array", "maxItems": 50, "items": {"type": ["string", "integer"]},
        },
    }},
    "get_trap": {"required": ["id"], "properties": {"id": {"type": ["string", "integer"]}}},
    "get_stack_checks": {"required": ["stack"], "properties": {"stack": {"type": "string"}}},
    "get_model_risks": {"required": ["model"], "properties": {"model": {"type": "string"}}},
    "get_coverage_summary": {"properties": {}},
    "interpret_doctor_report": {"required": ["report"], "properties": {"report": {"type": "object"}}},
    "build_reproduction_plan": {"required": ["trap_ids"], "properties": {
        "trap_ids": {"type": "array", "maxItems": 50, "items": {"type": ["string", "integer"]}},
    }},
    "prepare_issue_report": {"required": ["evidence"], "properties": {
        "evidence": {"type": "string", "maxLength": MAX_TEXT_ARGUMENT},
    }},
    "inspect_config": {"required": ["paths"], "properties": {
        "paths": {"type": "array", "maxItems": 50, "items": {"type": "string"}},
    }},
    "inspect_logs": {"required": ["paths"], "properties": {
        "paths": {"type": "array", "maxItems": 50, "items": {"type": "string"}},
    }},
}


def _schema_for(name: str) -> dict[str, Any]:
    schema = TOOL_SCHEMAS[name]
    return {"type": "object", "additionalProperties": False, **schema}


def _validate_args(name: str, args: Any) -> dict[str, Any]:
    if name not in TOOL_SCHEMAS:
        raise ValueError(f"unknown tool: {name}")
    if not isinstance(args, dict):
        raise ValueError("tool arguments must be an object")
    schema = TOOL_SCHEMAS[name]
    unknown = sorted(set(args) - set(schema["properties"]))
    if unknown:
        raise ValueError("unknown arguments: " + ", ".join(unknown))
    missing = [key for key in schema.get("required", []) if key not in args]
    if missing:
        raise ValueError("missing required arguments: " + ", ".join(missing))
    for key, value in args.items():
        rule = schema["properties"][key]
        kinds = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        valid = (
            ("string" in kinds and isinstance(value, str))
            or ("integer" in kinds and isinstance(value, int) and not isinstance(value, bool))
            or ("array" in kinds and isinstance(value, list))
            or ("object" in kinds and isinstance(value, dict))
        )
        if not valid:
            raise ValueError(f"{key} has the wrong type")
        if isinstance(value, str) and len(value) > rule.get("maxLength", MAX_TEXT_ARGUMENT):
            raise ValueError(f"{key} exceeds the size limit")
        if isinstance(value, list):
            if len(value) > rule.get("maxItems", 50):
                raise ValueError(f"{key} has too many items")
            item_types = rule.get("items", {}).get("type", [])
            if isinstance(item_types, str):
                item_types = [item_types]
            if any(not (
                ("string" in item_types and isinstance(item, str))
                or ("integer" in item_types and isinstance(item, int) and not isinstance(item, bool))
            ) for item in value):
                raise ValueError(f"{key} contains an item with the wrong type")
        if key == "conditions":
            unknown_conditions = sorted(set(value) - set(CONDITION_FIELDS))
            if unknown_conditions:
                raise ValueError(
                    "unknown condition fields: " + ", ".join(unknown_conditions)
                )
            if any(
                not isinstance(item, (str, int)) or isinstance(item, bool)
                for item in value.values()
            ):
                raise ValueError("condition values must be strings or integers")
        if key == "direct_probe_results":
            if len(value) > rule["maxProperties"]:
                raise ValueError("direct_probe_results has too many items")
            if any(
                not isinstance(trap_id, str)
                or outcome not in {"confirmed", "refuted", "inconclusive"}
                for trap_id, outcome in value.items()
            ):
                raise ValueError("direct_probe_results contains an invalid result")
    return args


def _configured_roots() -> list[str]:
    raw = os.environ.get("MINEFIELD_ALLOWED_ROOTS", "")
    return [str(Path(item).resolve(strict=True)) for item in raw.split(os.pathsep) if item]


def _result(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, sort_keys=True)}]}


def call_tool(
    name: str,
    args: dict[str, Any],
    registry: dict[str, Any],
    *,
    allowed_roots: list[str] | None = None,
) -> Any:
    args = _validate_args(name, args)
    if name == "search_symptom":
        return diagnose(
            registry, args.get("symptom", ""), stack=args.get("stack"),
            model=args.get("model"), version=args.get("version"),
            conditions=args.get("conditions"),
            direct_probe_trap_ids=args.get("direct_probe_trap_ids"),
            direct_probe_results=args.get("direct_probe_results"),
            mechanism_probe_trap_ids=args.get("mechanism_probe_trap_ids"),
            evidence_status=args.get("evidence_status"),
        )
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
            "executed_trap_ids": sorted({
                str(item.get("trap_id", "")).zfill(2) for item in findings
                if item.get("trap_id") is not None
            }),
            "diagnosis_level": "INCONCLUSIVE",
            "warning": (
                "CLEAN applies only to executed checks. Unimplemented, absent, "
                "or failed interpretation scope remains unknown."
            ),
        }
    if name == "build_reproduction_plan":
        wanted = {str(item).zfill(2) for item in args.get("trap_ids", [])}
        return [item for item in specifications(registry) if item["trap_id"] in wanted]
    if name == "prepare_issue_report":
        text = str(args.get("evidence", ""))
        from .redaction import redact_document
        clean, redactions = redact_document(text)
        return {"markdown": "# Minefield report\n\n" + clean, "redactions": redactions}
    if name == "inspect_config":
        if not allowed_roots:
            raise ValueError("inspect_config is disabled until MINEFIELD_ALLOWED_ROOTS is configured")
        return inspect_files(args["paths"], allowed_roots)
    if name == "inspect_logs":
        if not allowed_roots:
            raise ValueError("inspect_logs is disabled until MINEFIELD_ALLOWED_ROOTS is configured")
        return inspect_logs(args["paths"], allowed_roots)
    raise ValueError(f"unknown tool: {name}")


def serve(
    stdin: Any = sys.stdin,
    stdout: Any = sys.stdout,
    *,
    allowed_roots: list[str] | None = None,
) -> int:
    registry = load_registry()
    roots = _configured_roots() if allowed_roots is None else allowed_roots
    for line in stdin:
        request: Any = None
        try:
            if len(line.encode("utf-8")) > MAX_REQUEST_BYTES:
                raise ValueError("request exceeds the size limit")
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                raise ValueError("request must be a JSON-RPC 2.0 object")
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
                    "inputSchema": _schema_for(name),
                } for name, description in TOOLS.items()]}
            elif method == "tools/call":
                params = request.get("params", {})
                if not isinstance(params, dict):
                    raise ValueError("params must be an object")
                value = _result(call_tool(
                    params["name"], params.get("arguments", {}), registry,
                    allowed_roots=roots,
                ))
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
