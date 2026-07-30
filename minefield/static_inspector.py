"""Bounded static inspection of files explicitly supplied by the user."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 2 * 1024 * 1024
RULES = (
    ("01", r"\breasoning_content\b(?![\s\S]{0,160}\breasoning\b)", "suspicious",
     "Only one reasoning response-field name is referenced."),
    ("07", r"\breasoning_effort\b", "configuration-only",
     "A reasoning control is configured; runtime/template use still needs proof."),
    ("21", r"(?:--generation-config\s+auto|generation_config\s*[:=]\s*(?:null|none))",
     "suspicious", "Generation defaults may fall back to server built-ins."),
    ("53", r"(?:pkill\s+-f|taskkill\s+.*\/IM)[^\n]*(?:python|server|llama|vllm)",
     "suspicious", "Process-name restart logic does not prove which PID owns the port."),
    ("70", r"--reasoning-parser\s+\S+", "configuration-only",
     "A named parser is configured; confirm the running build actually bundles it."),
    ("79", r"(?:num_ctx|max_model_len|n_ctx)\s*[:=]\s*(\d{7,})",
     "requiring-runtime-confirmation", "A very large context is declared; acceptance is not usability."),
    ("90", r"(?:CUDA_ARCH|CMAKE_CUDA_ARCHITECTURES)\s*[:=]\s*[\"']?(?:80|86|89)[\"']?",
     "suspicious", "The build architecture list may omit newer GPUs."),
    ("101", r"\btransformers\s*(?:==|~=|>=)\s*(?:4\.(?:4[5-9]|[5-9]\d)|[5-9]\.)",
     "requiring-runtime-confirmation", "A Transformers version constraint may cross a removed-kwarg boundary."),
    ("103", r"\btorch(?:==\S+)?[\s\S]{0,100}\btorchvision(?:==\S+)?",
     "configuration-only", "Torch and torchvision are jointly present; ABI compatibility needs an import check."),
    ("104", r"(?:ExecStart|command:|args:)[^\n]*(?:--max-model-len|--ctx-size|--reasoning-parser)",
     "configuration-only", "A launcher persists serving flags; compare it with the intended live configuration."),
)
IMPLEMENTED_TRAPS = frozenset(rule[0] for rule in RULES)


def _safe_file(path: Path, allowed_roots: list[Path] | None) -> Path:
    if path.is_symlink():
        raise ValueError(f"symlink input is refused: {path}")
    resolved = path.resolve(strict=True)
    if allowed_roots and not any(
        resolved == root.resolve() or root.resolve() in resolved.parents
        for root in allowed_roots
    ):
        raise ValueError(f"path is outside allowed roots: {path}")
    if not resolved.is_file():
        raise ValueError(f"not a regular file: {path}")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes: {path}")
    return resolved


def inspect_files(paths: list[str], allowed_roots: list[str] | None = None) -> dict[str, Any]:
    roots = [Path(root) for root in allowed_roots] if allowed_roots else None
    findings = []
    for raw_path in paths:
        path = _safe_file(Path(raw_path), roots)
        data = path.read_text(encoding="utf-8", errors="replace")
        for trap_id, pattern, certainty, explanation in RULES:
            for match in re.finditer(pattern, data, re.I | re.M):
                line = data.count("\n", 0, match.start()) + 1
                findings.append({
                    "trap_ids": [trap_id],
                    "match_confidence": certainty,
                    "evidence_status": "registry evidence status must be read from the matched trap",
                    "condition_match": [f"static pattern matched in {path.name}"],
                    "condition_mismatch": [],
                    "confirmation_check": explanation,
                    "refutation_check": "Inspect the effective runtime configuration and startup evidence.",
                    "safest_mitigation": "No automatic mutation; confirm the effective value first.",
                    "mutation_authority_warning": "Configuration was read only.",
                    "what_remains_unknown": "Static text does not prove the running process used this setting.",
                    "file": str(path),
                    "line": line,
                    "matched_signature": match.group(0)[:240],
                })
    return {"kind": "static_config", "files": len(paths), "findings": findings}
