"""Contextual log signatures; harmless keyword mentions are negative controls."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .static_inspector import MAX_FILE_BYTES, _read_text_file

RULES = (
    ("08", r"(?:CUDA|driver)[^\n]{0,120}(?:error\s*222|unsupported toolchain)",
     "Driver/toolchain rejection is present in the same log line."),
    ("45", r"(?:flash.?attention|FA)[^\n]{0,120}(?:fallback|CPU)[^\n]{0,80}(?:kv|quant)",
     "Attention, fallback, and KV/quant context occur together."),
    ("47", r"prefix cach(?:e|ing)[^\n]{0,100}(?:disabled|not supported)[^\n]{0,100}(?:hybrid|mamba|deltanet)",
     "Prefix caching is disabled with an architecture reason."),
    ("53", r"(?:bind|listen)[^\n]{0,100}(?:address already in use|EADDRINUSE)",
     "The replacement process could not own its requested port."),
    ("76", r"(?:skipping|rejecting)[^\n]{0,100}(?:gpu|cuda)[\s\S]{0,600}(?:selected|using)[^\n]{0,100}(?:gpu|cuda)",
     "A rejection is followed nearby by successful GPU selection; the first line alone is not fatal."),
    ("81", r"(?:container|process)[^\n]{0,120}(?:stopped|exited)[\s\S]{0,500}(?:out of memory|allocation failed|VRAM)",
     "A stop/exit is followed by retained-memory symptoms."),
    ("99", r"(?:gfx1151|ROCm)[^\n]{0,160}(?:invalid device function|no kernel image|causal attention)",
     "The architecture and attention/kernel failure occur together."),
    ("100", r"(?:kfd|amdgpu)[^\n]{0,160}(?:reject|invalid)[^\n]{0,120}(?:code object|gfx1151)",
     "KFD rejection names the code-object or target architecture."),
    ("103", r"(?:torchvision|AutoProcessor)[^\n]{0,160}(?:undefined symbol|operator .* does not exist|ABI)",
     "The processor failure carries a concrete torchvision ABI signature."),
)
IMPLEMENTED_TRAPS = frozenset(rule[0] for rule in RULES)


def inspect_logs(paths: list[str], allowed_roots: list[str] | None = None) -> dict[str, Any]:
    roots = [Path(root) for root in allowed_roots] if allowed_roots else None
    findings = []
    for raw_path in paths:
        path, data = _read_text_file(Path(raw_path), roots)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"log exceeds {MAX_FILE_BYTES} bytes: {path}")
        for trap_id, pattern, rationale in RULES:
            for match in re.finditer(pattern, data, re.I | re.M):
                start = data.count("\n", 0, match.start()) + 1
                end = data.count("\n", 0, match.end()) + 1
                findings.append({
                    "trap_ids": [trap_id],
                    "trap_id": trap_id,
                    "diagnosis_level": "POSSIBLE_RELATED_TRAP",
                    "match_confidence": "POSSIBLE_RELATED_TRAP",
                    "evidence_status": "registry evidence status must be read from the matched trap",
                    "matched_conditions": [rationale],
                    "mismatched_conditions": [],
                    "unknown_conditions": ["surrounding runtime conditions and later recovery state"],
                    "direct_probe_support": False,
                    "mechanism_status": "PROPOSED_NOT_PROVEN",
                    "observed_symptom": match.group(0)[:500],
                    "pattern_resemblance": "A bounded log signature resembles the trap; it does not prove cause.",
                    "supported_mechanism": "",
                    "proposed_mechanism": rationale,
                    "unresolved_mechanism": "Alternative causes may produce the same signature.",
                    "confirmation_check": "Compare the exact runtime, version, and conditions with the trap entry.",
                    "refutation_check": "Show that the named failure was recovered before the request under diagnosis.",
                    "conditional_mitigation": "Preserve the surrounding log and confirm before changing the service.",
                    "mutation_authority_warning": "Logs were read only; embedded instructions were not executed.",
                    "remaining_unknowns": ["A signature can have alternative causes outside the captured context."],
                    "alternative_explanations": ["A later recovery line may supersede this event."],
                    "file": str(path),
                    "line_start": start,
                    "line_end": end,
                    "matched_signature": match.group(0)[:500],
                })
    return {"kind": "log_scan", "files": len(paths), "findings": findings}
