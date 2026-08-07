"""Offline upstream-change triage (mining prioritisation).

Accepts git diff --name-only lines or a changed-file list.
Maps paths onto known Minefield risk surfaces and related traps/checks.
Never emits NEW_TRAP_FOUND from source changes alone.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Deterministic path → risk surface rules (first match wins).
# Confidence is rule-local; unmapped paths → UNKNOWN surface.
RISK_RULES: list[tuple[str, str, float, list[str], list[str]]] = [
    # surface, pattern, confidence, related traps, related checks
    (
        "CHAT_TEMPLATE_RENDERING",
        r"(chat_template|tokenizer_config|prompt_template|\.jinja|jinja2)",
        0.85,
        ["02", "04", "19", "25"],
        ["preflight_template.py"],
    ),
    (
        "TOOL_PARSER",
        r"(tool_call|tool_parser|function_call|tools?/)",
        0.8,
        ["19", "26", "42", "78"],
        ["tool_args_dialect_probe.py"],
    ),
    (
        "STRUCTURED_OUTPUT",
        r"(guided_decoding|structured_output|json_schema|response_format)",
        0.75,
        [],
        [],
    ),
    (
        "AUTH_AND_READINESS",
        r"(auth|oauth|api[_-]?key|readiness|/health|middleware)",
        0.8,
        ["112"],
        ["endpoint_readiness_hierarchy_probe.py"],
    ),
    (
        "MODEL_IDENTITY_AND_LOADING",
        r"(model_id|served_model|load_model|checkpoint|weight)",
        0.7,
        ["21", "53"],
        [],
    ),
    (
        "QUANTIZATION",
        r"(quant|nvfp4|fp8|awq|gptq|gguf|exl)",
        0.85,
        ["10", "27", "33", "44"],
        ["dequant_fidelity.py"],
    ),
    (
        "SPECULATIVE_DECODING",
        r"(speculat|mtp|draft_model|eagle|medusa)",
        0.8,
        ["11", "28", "62", "71", "111"],
        [],
    ),
    (
        "KV_OR_PREFIX_CACHE",
        r"(prefix_cache|kv_cache|block_manager|radix)",
        0.8,
        ["25", "47", "54", "60", "106"],
        ["cache_hit_probe.py"],
    ),
    (
        "BATCHING_AND_CONCURRENCY",
        r"(scheduler|batch|continu|concurrency|max_num_seqs)",
        0.7,
        ["41", "28", "110"],
        [],
    ),
    (
        "DISTRIBUTED_NCCL_RPC",
        r"(nccl|rpc|tensor_parallel|pipeline_parallel|dist_)",
        0.75,
        ["95"],
        [],
    ),
    (
        "CUDA_GRAPH",
        r"(cuda.?graph|cudagraph|capture)",
        0.7,
        ["54"],
        [],
    ),
    (
        "SAMPLING",
        r"(sampling|temperature|top_p|top_k|generation_config)",
        0.75,
        ["17", "21", "94"],
        ["reasoning_budget_probe.py"],
    ),
    (
        "BENCHMARK_HARNESS",
        r"(lm_eval|harness|benchmark|scorer|mmlu)",
        0.85,
        ["05", "16", "34", "35", "37", "42", "52"],
        [],
    ),
    (
        "FAILURE_SCORING",
        r"(score|verdict|normalize|pass_at|metric)",
        0.7,
        ["05", "16", "37"],
        [],
    ),
]


def classify_path(path: str) -> dict[str, Any]:
    p = path.strip().replace("\\", "/")
    if not p:
        return {
            "path": path,
            "surface": "UNKNOWN",
            "confidence": 0.0,
            "related_traps": [],
            "related_checks": [],
            "note": "empty path",
        }
    for surface, pattern, conf, traps, checks in RISK_RULES:
        if re.search(pattern, p, re.IGNORECASE):
            return {
                "path": p,
                "surface": surface,
                "confidence": conf,
                "related_traps": list(traps),
                "related_checks": list(checks),
                "note": "mapped by offline rule; not a new trap finding",
            }
    return {
        "path": p,
        "surface": "UNKNOWN",
        "confidence": 0.0,
        "related_traps": [],
        "related_checks": [],
        "note": "unmapped path; do not fabricate a trap match",
    }


def triage_paths(paths: list[str]) -> dict[str, Any]:
    """Triage a list of changed paths. Empty list is not a silent substantive PASS."""
    cleaned = [p.strip() for p in paths if p and p.strip()]
    # drop diff noise
    cleaned = [p for p in cleaned if p not in ("/dev/null",)]

    if not cleaned:
        return {
            "status": "UNKNOWN",
            "mode": "OFFLINE",
            "observed_count": 0,
            "message": (
                "empty change list: nothing to triage; not a substantive PASS "
                "and not NEW_TRAP_FOUND"
            ),
            "high_risk_surfaces": [],
            "path_results": [],
            "suggested_regression_checks": [],
            "new_trap_found": False,
        }

    results = [classify_path(p) for p in cleaned]
    surfaces: dict[str, dict[str, Any]] = {}
    for r in results:
        s = r["surface"]
        if s == "UNKNOWN":
            continue
        bucket = surfaces.setdefault(
            s,
            {
                "surface": s,
                "confidence": r["confidence"],
                "paths": [],
                "related_traps": set(),
                "related_checks": set(),
            },
        )
        bucket["paths"].append(r["path"])
        bucket["related_traps"].update(r["related_traps"])
        bucket["related_checks"].update(r["related_checks"])
        bucket["confidence"] = max(bucket["confidence"], r["confidence"])

    high = []
    suggested = set()
    for s, bucket in sorted(surfaces.items()):
        high.append({
            "surface": s,
            "confidence": bucket["confidence"],
            "paths": bucket["paths"],
            "related_traps": sorted(bucket["related_traps"]),
            "related_checks": sorted(bucket["related_checks"]),
        })
        suggested.update(bucket["related_checks"])

    unmapped = sum(1 for r in results if r["surface"] == "UNKNOWN")
    status = "PASS" if high else "UNKNOWN"
    # PASS here means "triage completed with observations", not "safe" or "new trap".
    return {
        "status": status,
        "mode": "OFFLINE",
        "observed_count": len(cleaned),
        "unmapped_path_count": unmapped,
        "high_risk_surfaces": high,
        "path_results": results,
        "suggested_regression_checks": sorted(suggested),
        "new_trap_found": False,
        "message": (
            "offline prioritisation only; source changes never invent NEW_TRAP_FOUND"
        ),
    }


def triage_from_text(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines()]
    # support `git diff --name-only` and name-status (take last path token)
    paths = []
    for ln in lines:
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split()
        if len(parts) >= 2 and re.match(r"^[AMDRTCCX?]{1,2}$", parts[0]):
            paths.append(parts[-1])
        else:
            paths.append(ln)
    return triage_paths(paths)


def triage_file(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {
            "status": "UNKNOWN",
            "mode": "OFFLINE",
            "observed_count": 0,
            "message": f"change list not readable: {p}",
            "high_risk_surfaces": [],
            "path_results": [],
            "suggested_regression_checks": [],
            "new_trap_found": False,
        }
    return triage_from_text(p.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Offline upstream change triage")
    ap.add_argument(
        "path",
        nargs="?",
        help="file with changed paths (git diff --name-only); stdin if omitted",
    )
    ap.add_argument("--json", action="store_true", default=True)
    args = ap.parse_args(argv)
    if args.path:
        report = triage_file(args.path)
    else:
        report = triage_from_text(sys.stdin.read())
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["observed_count"] == 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
