"""Offline inspection of a model folder: config.json, quant config, cache refs.

Reads bounded JSON metadata and file-system facts only. No weights are opened
and no code in the folder is imported or executed. Every finding is a possible
match that names the check to run; config text does not prove what the serving
engine resolved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_CACHE_REF_FILES = 1_000
MAX_CACHE_REF_DEPTH = 4
WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt")

IMPLEMENTED_TRAPS = frozenset({"10", "21", "27", "55", "61", "71", "89", "109", "131", "143"})


def _normalise_roots(allowed_roots: list[str] | None) -> list[Path] | None:
    if not allowed_roots:
        return None
    return [Path(root).resolve(strict=True) for root in allowed_roots]


def _inside(path: Path, roots: list[Path] | None) -> bool:
    return roots is None or any(path == root or root in path.parents for root in roots)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _finding(trap: str, message: str, evidence: str = "", certainty: str = "possible") -> dict[str, Any]:
    return {"trap_id": trap, "certainty": certainty, "message": message, "evidence": evidence[:300]}


def _text_config(config: dict[str, Any]) -> dict[str, Any]:
    """Multimodal configs nest the language model under text_config."""
    nested = config.get("text_config")
    return nested if isinstance(nested, dict) else config


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _quant_excludes(config: dict[str, Any], folder: Path, roots: list[Path] | None = None) -> list[str]:
    names: list[str] = []
    qc = _as_dict(config.get("quantization_config"))
    for key in ("ignore", "modules_to_not_convert", "exclude_modules", "ignored_layers"):
        value = qc.get(key)
        if isinstance(value, list):
            names += [str(item) for item in value]
    sidecar = folder / "hf_quant_config.json"
    hf_quant = (_load_json(sidecar) if _inside(sidecar, roots) else None) or {}
    inner = _as_dict(hf_quant.get("quantization"))
    for key in ("exclude_modules", "ignore"):
        value = inner.get(key)
        if isinstance(value, list):
            names += [str(item) for item in value]
    return names


def _find_cache_root(folder: Path, roots: list[Path] | None) -> Path | None:
    """Find an HF cache root without escaping configured scan roots."""
    for candidate in (folder, *list(folder.parents)[:3]):
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not _inside(resolved, roots):
            continue
        refs = resolved / "refs"
        snapshots = resolved / "snapshots"
        try:
            if refs.is_symlink() or snapshots.is_symlink():
                continue
            if refs.is_dir() and snapshots.is_dir():
                refs_resolved = refs.resolve(strict=True)
                snapshots_resolved = snapshots.resolve(strict=True)
                if _inside(refs_resolved, roots) and _inside(snapshots_resolved, roots):
                    return resolved
        except OSError:
            continue
    return None


def _cache_ref_files(root: Path, roots: list[Path] | None) -> tuple[list[Path], bool]:
    """Return a bounded, symlink-free list of cache ref files."""
    base = root / "refs"
    files: list[Path] = []
    stack = [(base, 0)]
    while stack:
        folder, depth = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if len(files) >= MAX_CACHE_REF_FILES:
                return files, True
            try:
                if entry.is_symlink():
                    continue
                resolved = entry.resolve(strict=True)
                if not _inside(resolved, roots):
                    continue
                if resolved.is_dir():
                    if depth < MAX_CACHE_REF_DEPTH:
                        stack.append((resolved, depth + 1))
                elif resolved.is_file():
                    files.append(resolved)
            except OSError:
                continue
    return files, False


def inspect_model_folder(
    path: str | Path,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"symlink input is refused: {path}")
    roots = _normalise_roots(allowed_roots)
    try:
        resolved_target = target.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"model path is not readable: {path}") from exc
    folder = resolved_target if resolved_target.is_dir() else resolved_target.parent
    # A named metadata file may be the only allowed root.  Then the folder is
    # inspected file-only: siblings outside the roots are never read or listed.
    file_only = not _inside(folder, roots)
    if file_only and not (resolved_target.is_file() and _inside(resolved_target, roots)):
        raise ValueError(f"path is outside allowed roots: {path}")
    if not folder.is_dir():
        raise ValueError(f"not a model folder: {path}")

    report: dict[str, Any] = {
        "kind": "model_folder",
        "path": str(folder),
        "findings": [],
        "notes": [],
        "cache_ref_bytes": 0,
    }
    findings = report["findings"]
    if file_only:
        report["notes"].append(
            "only the named file is inside the allowed roots; checks that need the rest of the "
            "model folder (generation_config.json, weight shards, cache refs, quant sidecar) were not run"
        )
    config_path = folder / "config.json"
    config = _load_json(config_path) if _inside(config_path, roots) else None
    if config is None:
        report["notes"].append("no readable object-valued config.json; model-config checks skipped")
    else:
        text = _text_config(config)
        model_type = str(text.get("model_type") or config.get("model_type") or "")
        raw_quant = config.get("quantization_config")
        quant = _as_dict(raw_quant)
        if raw_quant is not None and not isinstance(raw_quant, dict):
            report["notes"].append("quantization_config is not an object; quant-specific checks were bounded")

        # 21: no generation_config.json means server defaults become "the model's settings".
        generation = folder / "generation_config.json"
        if not file_only and (generation.is_symlink() or not generation.is_file()):
            findings.append(_finding(
                "21", "No regular generation_config.json: the server's built-in sampling defaults will be used "
                "and reported as 'the model's defaults'. Set sampling explicitly."))

        # 143: Qwen3 sliding window declared but resolved to full attention.
        window = text.get("sliding_window")
        raw_layer_types = text.get("layer_types")
        layer_types = raw_layer_types if isinstance(raw_layer_types, list) else []
        if model_type.startswith("qwen3") and isinstance(window, int) and not isinstance(window, bool) \
                and window > 0 and "sliding_attention" not in layer_types:
            layers = text.get("num_hidden_layers")
            max_window_layers = text.get("max_window_layers", 28)
            if not text.get("use_sliding_window", False):
                findings.append(_finding(
                    "143", f"sliding_window={window} is declared but use_sliding_window is false or "
                    "missing, so every layer resolves to full attention.", f"model_type={model_type}"))
            elif isinstance(layers, int) and not isinstance(layers, bool) \
                    and isinstance(max_window_layers, int) and not isinstance(max_window_layers, bool) \
                    and max_window_layers >= layers:
                findings.append(_finding(
                    "143", f"use_sliding_window is on, but max_window_layers={max_window_layers} >= "
                    f"num_hidden_layers={layers}, so no layer gets the window."))

        # 55 / 61: advertised context versus trained context.
        rope = text.get("rope_scaling") or text.get("rope_parameters") or {}
        if isinstance(rope, dict):
            original = rope.get("original_max_position_embeddings")
            factor = rope.get("factor")
            advertised = text.get("max_position_embeddings")
            if isinstance(original, int) and not isinstance(original, bool) \
                    and isinstance(factor, (int, float)) and not isinstance(factor, bool) \
                    and factor > 1:
                advertised = advertised if isinstance(advertised, int) and not isinstance(advertised, bool) \
                    else int(original * factor)
                if advertised >= 2 * original:
                    detail = (
                        f"trained ~{original:,} tokens, advertised {advertised:,} via "
                        f"{rope.get('rope_type') or rope.get('type') or 'rope'} x{factor}"
                    )
                    findings.append(_finding(
                        "55", "The advertised context is a rope extension of a shorter trained context; "
                        "long-context quality is not guaranteed past the trained length.", detail))
                    findings.append(_finding(
                        "61", "Requests beyond the trained length return HTTP 200 and can fail silently; "
                        "test retrieval at the length you actually use.", detail))

        # 71 / 109: MTP drafter configuration and quantization excludes.
        mtp_keys = {
            key: text[key]
            for key in ("num_nextn_predict_layers", "mtp_num_hidden_layers", "num_mtp_layers")
            if isinstance(text.get(key), int) and not isinstance(text.get(key), bool) and text[key] > 0
        }
        excludes = _quant_excludes(config, folder, roots)
        if mtp_keys:
            key, value = next(iter(mtp_keys.items()))
            findings.append(_finding(
                "71", f"Multi-token-prediction layers are configured as {key}={value}. One MTP layer is not "
                "one draft token; read the resolved draft count from the engine's startup log and counters.",
                certainty="configuration-only"))
            excluded = [name for name in excludes if re.search(r"mtp|nextn|draft", name, re.I)]
            if excluded:
                findings.append(_finding(
                    "109", "The quantization config excludes the MTP/draft layers, so they stay in the source "
                    "format; if speculative decoding is on, the drafter may load them through the wrong kernel "
                    "path and acceptance collapses.", ", ".join(excluded[:5])))

        # 27: Qwen3-Next style fused projections missing from the quant ignore list.
        if "next" in model_type and quant and excludes and not any("in_proj" in name for name in excludes):
            findings.append(_finding(
                "27", "This hybrid model's quantization ignore list names no in_proj_* layers; community "
                "FP4 quants that quantized the fused GDN projections answered garbage. Run a ten-prompt "
                "factual probe before benchmarking speed."))

        # 10: the quant label in the folder name versus the config.
        label = re.search(r"(nvfp4|mxfp4|fp8|awq|gptq|int4|w4a16)", folder.name, re.I)
        if label:
            method = str(quant.get("quant_method") or "")
            blob = json.dumps(raw_quant, sort_keys=True).lower() if raw_quant is not None else ""
            if not quant or label.group(1).lower() not in blob:
                detail = (
                    f"declares quant_method={method or 'unknown'} without that format."
                    if quant
                    else "has no object-valued quantization_config."
                )
                findings.append(_finding(
                    "10", f"The folder name says {label.group(1).upper()} but config.json {detail} "
                    "The label does not tell you which kernels will run it.",
                    certainty="configuration-only"))

    # 89: weight shards that share an inode with another path.
    try:
        shared = [] if file_only else [
            item.name
            for item in sorted(folder.iterdir())
            if item.suffix in WEIGHT_SUFFIXES and not item.is_symlink() and item.is_file()
            and item.lstat().st_nlink > 1
        ]
    except OSError:
        shared = []
    if shared:
        findings.append(_finding(
            "89", f"{len(shared)} weight file(s) are hard links shared with another path. An in-place "
            "weight edit here also changes the other copy, so any 'stock' comparison is wrong.",
            ", ".join(shared[:5])))

    # 131: HF cache refs files must hold exactly a 40-hex commit id.
    root = _find_cache_root(folder, roots)
    if root is not None:
        refs, truncated = _cache_ref_files(root, roots)
        if truncated:
            report["notes"].append(
                f"cache-ref inspection stopped after {MAX_CACHE_REF_FILES} files; remaining refs were not checked"
            )
        for ref in refs:
            try:
                if ref.stat().st_size > 256:
                    continue
                raw = ref.read_bytes()
            except OSError:
                continue
            report["cache_ref_bytes"] += len(raw)
            if not re.fullmatch(rb"[0-9a-f]{40}", raw):
                findings.append(_finding(
                    "131", f"Cache ref {ref.relative_to(root)} is not exactly a 40-character commit id "
                    "(stray bytes or a newline); offline revision resolution will fail.", repr(raw[:60])))
    return report
