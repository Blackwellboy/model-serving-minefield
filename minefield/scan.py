"""`minefield scan`: run every offline detector over the files you point it at.

You name files or folders (a compose file, a launch script, a model folder,
server logs, an eval results file). Each is classified by name and shape and
handed to the matching detectors. Only the paths you name are read; folders
are walked a few levels deep, symlinks are never followed, and nothing is
executed except chat templates, which render inside Jinja's sandbox.

Every finding is a lead naming a trap and the check to run, never a verdict.
An empty scan means none of the implemented checks fired, not that the setup
is safe.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .log_inspector import inspect_logs
from .model_inspector import inspect_model_folder
from .results_inspector import inspect_results
from .static_inspector import MAX_FILE_BYTES, inspect_files
from .template_inspector import inspect_template

MAX_DEPTH = 3
MAX_FILES = 400
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "site-packages", ".cache", "blobs"}
MODEL_MARKERS = ("config.json", "tokenizer_config.json", "chat_template.jinja")
LOG_SUFFIXES = {".log", ".out", ".err"}
CONFIG_SUFFIXES = {
    ".sh", ".bash", ".zsh", ".yml", ".yaml", ".service", ".env", ".toml", ".cfg", ".conf",
    ".ini", ".py", ".txt", ".json", ".dockerfile", ".ps1", ".bat",
}
CONFIG_NAMES = {"dockerfile", "makefile", "containerfile", "compose", ".env"}


def _is_model_folder(folder: Path) -> bool:
    return any((folder / name).is_file() for name in MODEL_MARKERS)


def _walk(root: Path) -> list[Path]:
    files: list[Path] = []
    stack = [(root, 0)]
    while stack and len(files) < MAX_FILES:
        folder, depth = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink() or entry.name.startswith(".") and entry.name != ".env":
                continue
            if entry.is_dir():
                if depth < MAX_DEPTH and entry.name not in SKIP_DIRS:
                    stack.append((entry, depth + 1))
            elif entry.is_file():
                files.append(entry)
    return files


def _kind(path: Path) -> str | None:
    name = path.name.lower()
    if name.endswith(".jinja"):
        return "template"
    if name in ("tokenizer.json", "tokenizer_config.json", "config.json", "generation_config.json",
                "hf_quant_config.json") or name.endswith(".safetensors.index.json"):
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
        "message": item.get("observed_symptom") if detector == "config" else item.get("proposed_mechanism"),
        "evidence": item.get("matched_signature", "")[:200],
    }


def _norm_report(report: dict[str, Any], detector: str, file: str) -> list[dict[str, Any]]:
    return [{"trap_id": f["trap_id"], "detector": detector, "file": file, "line": None,
             "certainty": f.get("certainty", "possible"), "message": f["message"],
             "evidence": f.get("evidence", "")} for f in report.get("findings", [])]


def scan(paths: list[str]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    notes: list[str] = []
    scanned: list[dict[str, str]] = []
    model_folders: set[Path] = set()
    loose: list[Path] = []

    for raw in paths:
        path = Path(raw)
        if path.is_symlink():
            notes.append(f"{raw}: symlink refused")
            continue
        if not path.exists():
            notes.append(f"{raw}: not found")
            continue
        if path.is_dir():
            if _is_model_folder(path):
                model_folders.add(path.resolve())
            for file in _walk(path):
                if _is_model_folder(file.parent):
                    model_folders.add(file.parent.resolve())
                else:
                    loose.append(file)
        elif path.name in MODEL_MARKERS or path.name == "hf_quant_config.json":
            model_folders.add(path.parent.resolve())
        else:
            loose.append(path)

    for folder in sorted(model_folders):
        scanned.append({"path": str(folder), "kind": "model folder"})
        try:
            findings += _norm_report(inspect_model_folder(folder), "model folder", str(folder))
            template = inspect_template(folder)
            findings += _norm_report(template, "chat template", str(folder))
            notes += [f"{folder.name}: {n}" for n in template.get("notes", [])]
        except Exception as exc:
            notes.append(f"{folder}: {type(exc).__name__}: {str(exc)[:160]}")

    for file in loose:
        kind = _kind(file)
        if kind is None:
            continue
        try:
            if file.stat().st_size > MAX_FILE_BYTES and kind != "json":
                notes.append(f"{file}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB, skipped")
                continue
            if kind == "template":
                scanned.append({"path": str(file), "kind": "chat template"})
                report = inspect_template(file)
                findings += _norm_report(report, "chat template", str(file))
                notes += [f"{file.name}: {n}" for n in report.get("notes", [])]
            elif kind == "log":
                scanned.append({"path": str(file), "kind": "log"})
                findings += [_norm_static(f, "log") for f in inspect_logs([str(file)])["findings"]]
            elif kind == "json":
                report = inspect_results(file)
                if report["findings"] or not report["notes"]:
                    scanned.append({"path": str(file), "kind": "eval results"})
                    findings += _norm_report(report, "eval results", str(file))
                elif file.stat().st_size <= MAX_FILE_BYTES:
                    scanned.append({"path": str(file), "kind": "config"})
                    findings += [_norm_static(f, "config") for f in inspect_files([str(file)])["findings"]]
            else:
                scanned.append({"path": str(file), "kind": "config" if file.suffix != ".txt" else "config/log"})
                findings += [_norm_static(f, "config") for f in inspect_files([str(file)])["findings"]]
                if file.suffix == ".txt":
                    findings += [_norm_static(f, "log") for f in inspect_logs([str(file)])["findings"]]
        except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            notes.append(f"{file}: {str(exc)[:160]}")

    # One line per (trap, file, message); repeated matches are counted, not repeated.
    merged: dict[tuple, dict[str, Any]] = {}
    for item in findings:
        key = (item["trap_id"], item["file"], item["message"])
        if key in merged:
            merged[key]["count"] += 1
        else:
            merged[key] = {**item, "count": 1}
    ordered = sorted(merged.values(), key=lambda f: (str(f["file"]), int(f["trap_id"])))
    return {
        "kind": "scan",
        "scanned": scanned,
        "findings": ordered,
        "traps": sorted({f["trap_id"] for f in ordered}, key=int),
        "notes": notes,
        "warning": "Each finding is a lead to check, not a diagnosis. An empty scan means no "
                   "implemented check fired, not that the setup is safe.",
    }
