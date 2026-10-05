"""`minefield scan`: run every offline detector over explicit paths.

You name files or folders (a compose file, launch script, model folder, server
logs, or eval results).  Each is classified by name and shape and handed to the
matching detector.  Recursive scans have one global file/byte budget, never
follow symlinks, and can be confined to server-configured roots.  Chat
templates render in a resource-limited child process.

Every finding is a lead naming a trap and the check to run, never a verdict.
An empty scan means none of the implemented checks fired, not that the setup
is safe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .log_inspector import inspect_logs
from .model_inspector import inspect_model_folder
from .results_inspector import inspect_results
from .safe_template import inspect_template_isolated
from .static_inspector import MAX_FILE_BYTES, inspect_files

MAX_DEPTH = 3
MAX_FILES = 400
MAX_TOTAL_BYTES = 256 * 1024 * 1024
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "site-packages", ".cache", "blobs",
}
MODEL_MARKERS = ("config.json", "tokenizer_config.json", "chat_template.jinja")
LOG_SUFFIXES = {".log", ".out", ".err"}
CONFIG_SUFFIXES = {
    ".sh", ".bash", ".zsh", ".yml", ".yaml", ".service", ".env", ".toml",
    ".cfg", ".conf", ".ini", ".py", ".txt", ".json", ".dockerfile",
    ".ps1", ".bat",
}
CONFIG_NAMES = {"dockerfile", "makefile", "containerfile", "compose", ".env"}


def _normalise_roots(allowed_roots: list[str] | None) -> list[Path] | None:
    if not allowed_roots:
        return None
    return [Path(root).resolve(strict=True) for root in allowed_roots]


def _inside(path: Path, roots: list[Path] | None) -> bool:
    return roots is None or any(path == root or root in path.parents for root in roots)


def _resolve(path: Path, roots: list[Path] | None) -> Path:
    if path.is_symlink():
        raise ValueError(f"symlink input is refused: {path}")
    resolved = path.resolve(strict=True)
    if not _inside(resolved, roots):
        raise ValueError(f"path is outside allowed roots: {path}")
    return resolved


def _is_model_folder(folder: Path) -> bool:
    for name in MODEL_MARKERS:
        marker = folder / name
        try:
            if not marker.is_symlink() and marker.is_file():
                return True
        except OSError:
            continue
    return False


def _walk(root: Path, roots: list[Path] | None, remaining: int) -> tuple[list[Path], bool]:
    files: list[Path] = []
    stack = [(root, 0)]
    truncated = False
    while stack:
        folder, depth = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if len(files) >= remaining:
                truncated = True
                return files, truncated
            if entry.is_symlink() or (entry.name.startswith(".") and entry.name != ".env"):
                continue
            try:
                resolved = entry.resolve(strict=True)
            except OSError:
                continue
            if not _inside(resolved, roots):
                continue
            try:
                if resolved.is_dir():
                    if depth < MAX_DEPTH and entry.name not in SKIP_DIRS:
                        stack.append((resolved, depth + 1))
                elif resolved.is_file():
                    files.append(resolved)
            except OSError:
                continue
    return files, truncated


def _kind(path: Path) -> str | None:
    name = path.name.lower()
    if name.endswith(".jinja"):
        return "template"
    if name in (
        "tokenizer.json", "tokenizer_config.json", "config.json",
        "generation_config.json", "hf_quant_config.json",
    ) or name.endswith(".safetensors.index.json"):
        return None  # read through the model-folder path, not as a loose file
    if path.suffix.lower() in LOG_SUFFIXES:
        return "log"
    if path.suffix.lower() in (".jsonl", ".json"):
        return "json"
    if path.suffix.lower() in CONFIG_SUFFIXES or name in CONFIG_NAMES or name.startswith(
            ("docker-compose", "compose.", "dockerfile")):
        return "config"
    return None


def _norm_static(item: dict[str, Any], detector: str) -> dict[str, Any]:
    return {
        "trap_id": item["trap_id"],
        "detector": detector,
        "file": item.get("file"),
        "line": item.get("line") or item.get("line_start"),
        "certainty": item.get("certainty") or "possible",
        "message": (
            item.get("observed_symptom")
            if detector == "config"
            else item.get("proposed_mechanism")
        ),
        "evidence": item.get("matched_signature", "")[:200],
    }


def _norm_report(report: dict[str, Any], detector: str, file: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for finding in report.get("findings", []):
        if not isinstance(finding, dict) or "trap_id" not in finding or "message" not in finding:
            continue
        out.append({
            "trap_id": finding["trap_id"],
            "detector": detector,
            "file": file,
            "line": None,
            "certainty": finding.get("certainty", "possible"),
            "message": finding["message"],
            "evidence": finding.get("evidence", ""),
        })
    return out


def scan(paths: list[str], allowed_roots: list[str] | None = None) -> dict[str, Any]:
    roots = _normalise_roots(allowed_roots)
    root_strings = [str(root) for root in roots] if roots else None
    findings: list[dict[str, Any]] = []
    notes: list[str] = []
    scanned: list[dict[str, str]] = []
    model_folders: set[Path] = set()
    loose: set[Path] = set()
    discovered: set[Path] = set()
    truncated = False

    for raw in paths:
        try:
            path = _resolve(Path(raw), roots)
        except (OSError, ValueError) as exc:
            notes.append(f"{raw}: {str(exc)[:160]}")
            continue
        if path.is_dir():
            if _is_model_folder(path):
                model_folders.add(path)
            remaining = max(0, MAX_FILES - len(discovered))
            if remaining == 0:
                truncated = True
                break
            walked, hit_limit = _walk(path, roots, remaining)
            truncated = truncated or hit_limit
            for file in walked:
                if file in discovered:
                    continue
                discovered.add(file)
                if _is_model_folder(file.parent):
                    model_folders.add(file.parent)
                else:
                    loose.add(file)
        elif path.name in MODEL_MARKERS or path.name == "hf_quant_config.json":
            discovered.add(path)
            model_folders.add(path.parent)
        else:
            discovered.add(path)
            loose.add(path)
        if len(discovered) >= MAX_FILES:
            truncated = True
            break

    if truncated:
        notes.append(
            f"scan stopped after the global {MAX_FILES}-file limit; remaining files were not checked"
        )

    for folder in sorted(model_folders):
        scanned.append({"path": str(folder), "kind": "model folder"})
        try:
            findings += _norm_report(
                inspect_model_folder(folder, allowed_roots=root_strings),
                "model folder",
                str(folder),
            )
            template = inspect_template_isolated(folder)
            findings += _norm_report(template, "chat template", str(folder))
            notes += [f"{folder.name}: {note}" for note in template.get("notes", [])]
        except Exception as exc:
            notes.append(f"{folder}: {type(exc).__name__}: {str(exc)[:160]}")

    bytes_read = 0
    for file in sorted(loose):
        kind = _kind(file)
        if kind is None:
            continue
        try:
            size = file.stat().st_size
            if bytes_read + size > MAX_TOTAL_BYTES:
                notes.append(
                    f"{file}: global {MAX_TOTAL_BYTES // (1024 * 1024)} MB scan budget reached; skipped"
                )
                continue
            bytes_read += size
            if size > MAX_FILE_BYTES and kind not in {"json", "template"}:
                notes.append(
                    f"{file}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB, skipped"
                )
                continue
            if kind == "template":
                scanned.append({"path": str(file), "kind": "chat template"})
                report = inspect_template_isolated(file)
                findings += _norm_report(report, "chat template", str(file))
                notes += [f"{file.name}: {note}" for note in report.get("notes", [])]
            elif kind == "log":
                scanned.append({"path": str(file), "kind": "log"})
                findings += [
                    _norm_static(item, "log")
                    for item in inspect_logs([str(file)], root_strings)["findings"]
                ]
            elif kind == "json":
                try:
                    report = inspect_results(file)
                except ValueError as exc:
                    if size > MAX_FILE_BYTES:
                        raise
                    notes.append(
                        f"{file.name}: not parsed as eval results ({str(exc)[:100]}); checked as config"
                    )
                    report = {"findings": [], "notes": ["not eval results"]}
                if report["findings"] or not report["notes"]:
                    scanned.append({"path": str(file), "kind": "eval results"})
                    findings += _norm_report(report, "eval results", str(file))
                elif size <= MAX_FILE_BYTES:
                    scanned.append({"path": str(file), "kind": "config"})
                    findings += [
                        _norm_static(item, "config")
                        for item in inspect_files([str(file)], root_strings)["findings"]
                    ]
            else:
                scanned.append({
                    "path": str(file),
                    "kind": "config" if file.suffix != ".txt" else "config/log",
                })
                findings += [
                    _norm_static(item, "config")
                    for item in inspect_files([str(file)], root_strings)["findings"]
                ]
                if file.suffix == ".txt":
                    findings += [
                        _norm_static(item, "log")
                        for item in inspect_logs([str(file)], root_strings)["findings"]
                    ]
        except Exception as exc:
            notes.append(f"{file}: {type(exc).__name__}: {str(exc)[:160]}")

    # One line per (trap, file, message); repeated matches are counted, not repeated.
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in findings:
        key = (item["trap_id"], item["file"], item["message"])
        if key in merged:
            merged[key]["count"] += 1
        else:
            merged[key] = {**item, "count": 1}
    ordered = sorted(merged.values(), key=lambda item: (str(item["file"]), int(item["trap_id"])))
    return {
        "kind": "scan",
        "scanned": scanned,
        "findings": ordered,
        "traps": sorted({item["trap_id"] for item in ordered}, key=int),
        "notes": list(dict.fromkeys(notes)),
        "warning": "Each finding is a lead to check, not a diagnosis. An empty scan means no "
                   "implemented check fired, not that the setup is safe.",
    }
