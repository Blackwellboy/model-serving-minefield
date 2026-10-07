"""Bounded static inspection of files explicitly supplied by the user."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NamedTuple

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_MATCHES_PER_RULE = 8
MAX_FINDINGS_PER_FILE = 256
class Rule(NamedTuple):
    trap_id: str
    pattern: str
    certainty: str
    explanation: str
    # Optional file-level context: the rule fires only if `requires` also
    # matches somewhere in the same file, and never if `excludes` does. This
    # keeps advisory rules quiet on files where the risky setting is already
    # handled (for example a KV pool pinned in bytes).
    requires: str | None = None
    excludes: str | None = None


RULES = tuple(Rule(*rule) for rule in (
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
    ("103", r"\btorch\s*(?:==|~=|>=|<=)\s*\S+[\s\S]{0,100}"
     r"\btorchvision\s*(?:==|~=|>=|<=)\s*\S+",
     "configuration-only", "Torch and torchvision are jointly present; ABI compatibility needs an import check."),
    ("104", r"(?:ExecStart|command:|args:)[^\n]*(?:--max-model-len|--ctx-size|--reasoning-parser)",
     "configuration-only", "A launcher persists serving flags; compare it with the intended live configuration."),
    # Launch-command and container rules (0.2.1). Each names the setting the
    # trap entry identifies; each is advisory until the running process is
    # checked.
    ("13", r"(?:--gpu-memory-utilization|gpu_memory_utilization)[\s=:\"']+0?\.(?:8[5-9]|9\d)\b",
     "requiring-runtime-confirmation",
     "A high GPU memory fraction is set. On unified-memory machines (DGX Spark/GB10, GH200, Apple) "
     "it can starve the OS; pin the KV cache in bytes instead.",
     None, r"kv[-_]cache[-_]memory[-_]bytes"),
    ("18", r"(?:(?:-fa|--flash-attn)[ =](?:off|0|false)\b|attn_implementation\s*[=:]\s*[\"']?eager)",
     "suspicious", "Flash attention is switched off; decode can halve at long context."),
    ("32", r"mlx_lm\.server[^\n]*--max-tokens",
     "configuration-only", "mlx_lm.server --max-tokens is a per-request default, not a cap; clients can exceed it."),
    ("33", r"(?:--override-kv[^\n]*expert_used_count|--hf-overrides[^\n]*num_experts_per_tok|num_experts_per_tok\s*=\s*\d)",
     "suspicious", "The MoE active-expert count is overridden; raising it can lower accuracy with no error."),
    ("45", r"(?:-ctk|--cache-type-k)\s+(\w+)\b[\s\S]{0,300}?(?:-ctv|--cache-type-v)\s+(?!\1\b)\w+",
     "suspicious", "K and V cache use different quant types; unsupported pairs silently fall back to CPU "
     "unless the build enables all flash-attention quant pairs."),
    ("48", r"https?://[A-Za-z0-9-]+\.local\b",
     "suspicious", "The endpoint is an mDNS .local name; a dead IPv6 route can add ~30 s per request. "
     "Try the IPv4 address."),
    ("97", r"(?:-ngl|--n-gpu-layers|--gpu-layers)[ =](?:[0-9]|[1-8][0-9]|9[0-8])\b",
     "requiring-runtime-confirmation", "An explicit GPU layer count is set. If it is below the model's layer "
     "count, part of the model runs on CPU (22-31x slower decode) and nothing in the log says so."),
    ("98", r"(?:--speculative[-_]config|speculative_config)[^\n]*(?:dflash|mtp|eagle|draft)",
     "requiring-runtime-confirmation", "Speculative decoding without an explicit --max-num-seqs uses the default "
     "sequence capacity, which has coincided with OOMs on unified memory.",
     None, r"max[-_]num[-_]seqs"),
    ("114", r"NCCL_IB_GID_INDEX\s*[=:]\s*[\"']?\d+",
     "suspicious", "One fixed RDMA GID index is set; GID tables differ per host, so this is not portable."),
    ("117", r"fuse_gemm_comms[\"']?\s*[:=]\s*[\"']?(?:true|True|1)\b",
     "requiring-runtime-confirmation", "fuse_gemm_comms is requested; vLLM can echo it enabled and then resolve it "
     "to False. Check the resolved engine config, not the CLI echo."),
    ("118", r"--include-log-monitor[= ]false",
     "suspicious", "Ray's log monitor is off, so a healthy multi-node boot looks hung from the driver log."),
    ("122", r"[\"']method[\"']\s*:\s*[\"'][a-z0-9_]*mtp[\"']",
     "requiring-runtime-confirmation", "MTP speculative decoding with default CUDA graphs. On vLLM 0.27.1 FULL "
     "capture has corrupted Qwen3.8 MTP verification without errors.",
     r"vllm", r"enforce[-_]eager|num_speculative_tokens_per_batch_size|PIECEWISE"),
    ("127", r"-\s*[\"']?[^\s:\"'#]+\.py:[^\s:\"']*(?:site|dist)-packages[^\s:\"']*\.py",
     "suspicious", "A single .py file is bind-mounted over a module inside the image; an image update can "
     "turn that into a crash loop."),
    ("130", r"(?:max_cudagraph_capture_size|cudagraph_capture_sizes|--max-cudagraph-capture-size)",
     "configuration-only", "CUDA-graph capture sizes are set with speculative decoding; confirm in the startup "
     "log that the largest captured size covers max_num_seqs x (draft tokens + 1).",
     r"speculative|num_speculative_tokens"),
    ("138", r"(?:[\"']method[\"']\s*:\s*[\"']ngram[\"']|--speculative-model[= ]\[?ngram|prompt_lookup)",
     "configuration-only", "N-gram prompt-lookup speculation is on; if this lane serves JSON or structured "
     "output, verify every response with a strict parser."),
    ("142", r"(?:(?:\s-v|--volume)[ =][\"']?(?:\.{1,2}/|~/|/|\$)[^\s:\"']*:/|^\s*-\s+[\"']?(?:\.{1,2}/|~/|/)[^\s:\"']+:/)",
     "configuration-only", "Short bind-mount syntax: if the host path is missing, Docker creates an empty "
     "directory and the server fails later. Use --mount type=bind (or compose long syntax) for model/config files."),
    ("144", r"--enable-deterministic-inference\b",
     "requiring-runtime-confirmation",
     "SGLang deterministic inference is enabled on a FlashInfer-capable launch. On the affected historical build "
     "this also forced a fixed 2 GiB prefill workspace; long prompts need a version-scoped workspace check.",
     r"(?:sglang|flashinfer)"),
    ("147", r"(?:(?:-v|--volume)[ =][^\s]+:/run:ro\b|^\s*-\s+[^\s]+:/run:ro\s*$|--mount[^\n]*target=/run[^\n]*(?:readonly|read-only))",
     "suspicious",
     "A GPU container bind-mounts /run read-only. NVIDIA Container Toolkit needs writable scratch space there, "
     "so this can fail before the container entrypoint starts."),
    ("150", r"docker\s+save\b[^\n]{0,500}(?:\||>)[^\n]{0,500}docker\s+load\b",
     "configuration-only",
     "A docker save -> docker load pipe is used as if it were sender-disk-free streaming. On the measured classic "
     "exporter, save staged a full temporary copy on the sending Docker data-root first."),
    ("161", r"--speculative-num-draft-tokens(?:=|\s+)2\b",
     "requiring-runtime-confirmation",
     "DFlash draft budget 2 is configured. On the reported NVFP4/DFlash2 lane this was a deterministic startup "
     "failure during draft-worker CUDA-graph FP4 capture; treat startup as a measured cell.",
     r"(?:DFLASH|dflash)"),
    ("148", r"ensure_ascii\s*=\s*True",
     "configuration-only",
     "Tool/schema JSON is explicitly ASCII-escaped before prompt construction. Compare rendered prompt tokens with "
     "verbatim Unicode serialization before treating two engine requests as identical.",
     r"(?:tool|function|schema|chat[_ -]?template|messages?)"),
    ("151", r"(?:cp|patch|sed)[^\n]{0,240}(?:site|dist)-packages",
     "suspicious",
     "The image mutates files inside an installed package and also performs a pip uninstall/install upgrade. Files "
     "added by the patch are not in the old RECORD and can survive into the new version.",
     r"pip(?:3)?\s+(?:uninstall|install)[\s\S]{0,1600}pip(?:3)?\s+(?:install|uninstall)"),
    ("153", r"(?:151667[^\n]{0,240}151668|151668[^\n]{0,240}151667)",
     "suspicious",
     "A thinking-budget implementation hard-codes Qwen3 think marker IDs 151667/151668. Verify them against the "
     "served tokenizer before using the budget on Qwen3.5/3.8-family checkpoints.",
     r"(?:Qwen3ThinkingBudgetLogitProcessor|thinking[_ -]?budget)"),
    ("154", r"(?:tensorfold|TensorFold)[^\n]{0,160}(?:0\.6\.1|v0\.6\.1)",
     "requiring-runtime-confirmation",
     "TensorFold 0.6.1 is selected for an NVFP4 lane without an explicit precision mode. That version changed the "
     "default arithmetic; pin --precision and requalify long greedy output.",
     r"(?:NVFP4|nvfp4)", r"(?:--precision\b|precision\s*[:=])"),
))

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


def _read_text_file(path: Path, allowed_roots: list[Path] | None) -> tuple[Path, str]:
    resolved = _safe_file(path, allowed_roots)
    data = resolved.read_bytes()
    if b"\x00" in data:
        raise ValueError(f"binary input is refused: {path}")
    try:
        return resolved, data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input is not valid UTF-8 text: {path}") from exc


def inspect_files(paths: list[str], allowed_roots: list[str] | None = None) -> dict[str, Any]:
    roots = [Path(root) for root in allowed_roots] if allowed_roots else None
    findings = []
    truncations = []
    for raw_path in paths:
        path, data = _read_text_file(Path(raw_path), roots)
        file_findings = 0
        file_capped = False
        for rule in RULES:
            if file_capped:
                break
            trap_id, pattern, certainty, explanation = rule[:4]
            if rule.requires and not re.search(rule.requires, data, re.I | re.M):
                continue
            if rule.excludes and re.search(rule.excludes, data, re.I | re.M):
                continue
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
                line = data.count("\n", 0, match.start()) + 1
                findings.append({
                    "trap_ids": [trap_id],
                    "trap_id": trap_id,
                    "diagnosis_level": "INCONCLUSIVE",
                    "match_confidence": "INCONCLUSIVE",
                    "evidence_status": "registry evidence status must be read from the matched trap",
                    "matched_conditions": [f"static invariant candidate matched in {path.name}"],
                    "mismatched_conditions": [],
                    "unknown_conditions": ["runtime behavior was not observed"],
                    "direct_probe_support": False,
                    "direct_probe_result": "not_supplied",
                    "mechanism_status": "PROPOSED_NOT_PROVEN",
                    "observed_symptom": explanation,
                    "pattern_resemblance": "A static pattern matched; static text is not runtime proof.",
                    "supported_mechanism": "",
                    "proposed_mechanism": explanation,
                    "unresolved_mechanism": "The effective runtime value is unknown.",
                    "confirmation_check": explanation,
                    "refutation_check": "Inspect the effective runtime configuration and startup evidence.",
                    "conditional_mitigation": "No automatic mutation; confirm the effective value first.",
                    "mutation_authority_warning": "Configuration was read only.",
                    "remaining_unknowns": ["Static text does not prove the running process used this setting."],
                    "file": str(path),
                    "line": line,
                    "matched_signature": match.group(0)[:240],
                    "certainty": certainty,
                })
                rule_matches += 1
                file_findings += 1
    return {
        "kind": "static_config",
        "files": len(paths),
        "findings": findings,
        "truncations": truncations,
    }
