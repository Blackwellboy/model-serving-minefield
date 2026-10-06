"""Contextual log signatures; harmless keyword mentions are negative controls."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .static_inspector import (
    MAX_FILE_BYTES,
    MAX_FINDINGS_PER_FILE,
    MAX_MATCHES_PER_RULE,
    _read_text_file,
)

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
    # 0.2.1 additions. Each signature is the concrete line the trap entry
    # names, so a keyword mention on its own does not fire.
    ("51", r"(?:perplexity|\bppl\b)[^\n]{0,60}[=:\s]\s*[-+]?nan\b",
     "Perplexity is NaN. If other backends are clean on the same file, suspect the backend, not the quant."),
    ("72", r"(?:\b5\d\d\b|Internal Server Error)[^\n]{0,200}(?:image_url|audio_url|video_url|media|No such file)",
     "A media-fetch problem is reported as a 5xx server error; retries and alerts will treat a client error as an outage."),
    ("85", r"enable_thinking[^\n]{0,160}(?:valid boolean|bool_parsing|must be a bool)",
     "The server rejected enable_thinking sent as a string; it type-checks the kwarg even when the template ignores it."),
    ("98", r"(?:dflash|speculative|num_speculative_tokens)[\s\S]{0,4000}?(?:CUDA out of memory|OutOfMemoryError)",
     "An out-of-memory error follows speculative-decoding setup; sequence capacity x draft depth can exceed unified memory."),
    ("101", r"TypeError:[^\n]{0,200}got an unexpected keyword argument",
     "A keyword argument was rejected at call time; a library minor-version bump may have removed it."),
    ("112", r"device-side assert triggered",
     "A CUDA device-side assert fired; the engine may be dead while the container still reports Up."),
    ("115", r"(?:exit(?:ed)?(?: with)?(?: code| status)?\s*[:=]?\s*137\b|\bOOMKilled\b)",
     "Exit 137 is SIGKILL. Do not record it as the OOM killer without a kernel or cgroup OOM event for that PID."),
    ("116", r"embed_?tok(?:en)?s?[^\n]{0,120}(?:failed|error)",
     "The first forward failed in the embedding path; a successful load does not prove the first-forward dtype path."),
    ("117", r"[\"']fuse_gemm_comms[\"']\s*:\s*False",
     "The resolved engine config shows fuse_gemm_comms False; the flag was accepted and then disabled."),
    ("119", r"Free memory on device[^\n]{0,160}less than desired GPU memory utilization",
     "Startup refused the memory fraction. Find this first error before blaming NCCL errors from other ranks."),
    ("123", r"VLLM::EngineCore[^\n]{0,160}\d+\s*MiB",
     "A vLLM EngineCore process still holds GPU memory; an orphan from a killed API server blocks the next launch."),
    ("131", r"(?:RevisionNotFoundError|LocalEntryNotFoundError|Cannot find an appropriate cached snapshot)",
     "Offline revision resolution failed; inspect the HF cache refs/* files for stray bytes."),
    ("140", r"(?:sparse[_ ]?mla|indexer|FlashMLA)[\s\S]{0,2000}?(?:illegal memory access|cudaErrorIllegalAddress)",
     "An illegal address follows sparse-MLA/indexer activity; metadata may name a request row that does not exist."),
    ("142", r"(?:IsADirectoryError|Is a directory)[^\n]{0,200}(?:\.json|\.gguf|\.safetensors|\.jinja|config|model|tokenizer)",
     "A model or config path turned out to be a directory; Docker may have created it from a missing bind source."),
)
IMPLEMENTED_TRAPS = frozenset(rule[0] for rule in RULES)


def signatures_in_text(text: str) -> dict[str, str]:
    """{trap_id: rationale} for every signature present in pasted text.

    The same rules as a log file scan, applied to what a person pasted into a
    question, so `minefield <error line>` finds the trap the line belongs to.
    Pasted lines arrive wrapped by terminals and issue editors ("on startup
    is" / "less than desired"), which breaks single-line signatures, so a copy
    with the whitespace joined is checked too.
    """
    if not text:
        return {}
    joined = " ".join(text.split())
    return {trap_id: rationale for trap_id, pattern, rationale in RULES
            if re.search(pattern, text, re.I | re.M) or re.search(pattern, joined, re.I)}


def inspect_logs(paths: list[str], allowed_roots: list[str] | None = None) -> dict[str, Any]:
    roots = [Path(root) for root in allowed_roots] if allowed_roots else None
    findings = []
    truncations = []
    for raw_path in paths:
        path, data = _read_text_file(Path(raw_path), roots)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"log exceeds {MAX_FILE_BYTES} bytes: {path}")
        file_findings = 0
        file_capped = False
        for trap_id, pattern, rationale in RULES:
            if file_capped:
                break
            rule_matches = 0
            for match in re.finditer(pattern, data, re.I | re.M):
                if rule_matches >= MAX_MATCHES_PER_RULE:
                    truncations.append({
                        "code": "RULE_MATCH_LIMIT",
                        "file": str(path),
                        "trap_id": trap_id,
                        "limit": MAX_MATCHES_PER_RULE,
                    })
                    break
                if file_findings >= MAX_FINDINGS_PER_FILE:
                    truncations.append({
                        "code": "FILE_FINDING_LIMIT",
                        "file": str(path),
                        "limit": MAX_FINDINGS_PER_FILE,
                    })
                    file_capped = True
                    break
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
                    "direct_probe_result": "not_supplied",
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
                rule_matches += 1
                file_findings += 1
    return {
        "kind": "log_scan",
        "files": len(paths),
        "findings": findings,
        "truncations": truncations,
    }
