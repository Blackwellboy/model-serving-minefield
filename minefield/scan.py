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

import os
from itertools import islice
from pathlib import Path
from typing import Any

from .log_inspector import inspect_logs
from .model_inspector import inspect_model_folder
from .results_inspector import inspect_results
from .safe_template import inspect_template_isolated
from .static_inspector import MAX_FILE_BYTES, inspect_files

MAX_DEPTH = 3
MAX_FILES = 400
MAX_ENTRY_VISITS = 4_000
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_SCAN_FINDINGS = 2_000
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
# Files the model-folder and template inspectors read from each model folder;
# their sizes count toward the global byte budget.  Only the canonical
# chat_template.jinja is read through the folder; any other .jinja beside it is
# checked as a loose template.
MODEL_FOLDER_READS = (
    "config.json", "hf_quant_config.json", "tokenizer_config.json", "chat_template.jinja",
)


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


def _regular_size(path: Path, roots: list[Path] | None) -> int:
    """Size of a regular, non-symlink file inside the roots, else 0."""
    try:
        if path.is_symlink() or not path.is_file() or not _inside(path.resolve(), roots):
            return 0
        return path.stat().st_size
    except OSError:
        return 0


def _readable(path: Path) -> bool:
    """True when a named regular file can be opened or a named folder listed.

    Anything else (a FIFO, socket or device) is refused: opening a FIFO would
    block the scan.
    """
    try:
        if path.is_dir():
            with os.scandir(path) as entries:
                next(entries, None)
        elif path.is_file():
            with open(path, "rb"):
                pass
        else:
            return False
        return True
    except OSError:
        return False


def _is_model_folder(folder: Path) -> bool:
    for name in MODEL_MARKERS:
        marker = folder / name
        try:
            if not marker.is_symlink() and marker.is_file():
                return True
        except OSError:
            continue
    return False


def _walk(
    root: Path,
    roots: list[Path] | None,
    remaining_files: int,
    remaining_visits: int,
    seen: set[Path] | None = None,
) -> tuple[list[Path], bool, int, bool]:
    """Walk a bounded number of files and directory entries.

    Files and directories both spend the visit budget. Directory contents are
    read through a bounded scandir slice before sorting, so a single enormous
    directory is never materialised in full.
    """
    files: list[Path] = []
    visits = 0
    stack = [(root, 0)]
    while stack:
        if visits >= remaining_visits:
            return files, False, visits, True
        folder, depth = stack.pop()
        allowance = remaining_visits - visits
        try:
            with os.scandir(folder) as stream:
                raw_entries = list(islice(stream, allowance + 1))
        except OSError:
            continue
        entry_truncated = len(raw_entries) > allowance
        entries = [Path(entry.path) for entry in raw_entries[:allowance]]
        visits += len(entries)
        entries.sort(key=lambda path: path.name)
        for entry in entries:
            if len(files) >= remaining_files:
                return files, True, visits, entry_truncated
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
                elif resolved.is_file() and (seen is None or resolved not in seen):
                    files.append(resolved)
            except OSError:
                continue
        if entry_truncated:
            return files, False, visits, True
    return files, False, visits, False

def _kind(path: Path) -> str | None:
    name = path.name.lower()
    if name.endswith(".jinja"):
        return "template"
    if name in (
        "tokenizer.json", "tokenizer_config.json", "config.json",
        "generation_config.json", "hf_quant_config.json",
        "special_tokens_map.json", "added_tokens.json", "vocab.json", "vocab.txt",
        "merges.txt", "preprocessor_config.json", "processor_config.json",
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


def _record_detector_truncations(
    report: dict[str, Any],
    truncations: list[dict[str, Any]],
    detector: str,
) -> None:
    for item in report.get("truncations", []):
        if isinstance(item, dict):
            truncations.append({"detector": detector, **item})


def scan(paths: list[str], allowed_roots: list[str] | None = None) -> dict[str, Any]:
    roots = _normalise_roots(allowed_roots)
    root_strings = [str(root) for root in roots] if roots else None
    findings: list[dict[str, Any]] = []
    notes: list[str] = []
    scanned: list[dict[str, str]] = []
    model_folders: set[Path] = set()
    loose: set[Path] = set()
    discovered: set[Path] = set()
    file_truncated = False
    entry_truncated = False
    visited_entries = 0
    truncations: list[dict[str, Any]] = []
    accepted = 0

    for raw in paths:
        try:
            path = _resolve(Path(raw), roots)
        except (OSError, ValueError) as exc:
            notes.append(f"{raw}: {str(exc)[:160]}")
            continue
        if not _readable(path):
            notes.append(f"{raw}: cannot be read or listed; not checked")
            continue
        accepted += 1
        if path.is_dir():
            if _is_model_folder(path):
                model_folders.add(path)
            remaining = max(0, MAX_FILES - len(discovered))
            remaining_visits = max(0, MAX_ENTRY_VISITS - visited_entries)
            if remaining == 0:
                file_truncated = True
                break
            if remaining_visits == 0:
                entry_truncated = True
                break
            walked, hit_file_limit, visits, hit_entry_limit = _walk(
                path, roots, remaining, remaining_visits, discovered
            )
            visited_entries += visits
            file_truncated = file_truncated or hit_file_limit
            entry_truncated = entry_truncated or hit_entry_limit
            for file in walked:
                if file in discovered:
                    continue
                discovered.add(file)
                if _is_model_folder(file.parent):
                    model_folders.add(file.parent)
                    # The folder inspectors read the model metadata and template;
                    # anything else beside them (launch scripts, logs, results)
                    # still goes to the loose-file detectors.
                    if file.name == "chat_template.jinja":
                        continue
                loose.add(file)
        elif path.suffix == ".jinja":
            # A named template is rendered itself, even when only that file is
            # an allowed root and its folder is not.
            discovered.add(path)
            loose.add(path)
        elif path.name in MODEL_MARKERS or path.name == "hf_quant_config.json":
            discovered.add(path)
            # When only the named file is allowed, inspect that file alone
            # rather than widening access to its folder.
            model_folders.add(path.parent if _inside(path.parent, roots) else path)
        else:
            discovered.add(path)
            loose.add(path)
        if len(discovered) >= MAX_FILES:
            file_truncated = True
            break
        if entry_truncated:
            break

    if file_truncated:
        notes.append(
            f"scan stopped after the global {MAX_FILES}-file limit; remaining files were not checked"
        )
        truncations.append({"code": "FILE_LIMIT", "limit": MAX_FILES})
    if entry_truncated:
        notes.append(
            f"scan stopped after the global {MAX_ENTRY_VISITS}-entry visit limit; "
            "remaining files and directories were not checked"
        )
        truncations.append({"code": "ENTRY_VISIT_LIMIT", "limit": MAX_ENTRY_VISITS})

    bytes_read = 0
    for folder in sorted(model_folders):
        file_only = folder.is_file()
        folder_bytes = (
            _regular_size(folder, roots) if file_only
            else sum(_regular_size(folder / name, roots) for name in MODEL_FOLDER_READS)
        )
        if bytes_read + folder_bytes > MAX_TOTAL_BYTES:
            notes.append(
                f"{folder}: global {MAX_TOTAL_BYTES // (1024 * 1024)} MB scan budget reached; "
                "model folder skipped"
            )
            continue
        bytes_read += folder_bytes
        scanned.append({"path": str(folder), "kind": "model metadata" if file_only else "model folder"})
        try:
            model_report = inspect_model_folder(folder, allowed_roots=root_strings)
            # Cache refs are bounded per folder (1000 files of at most 256 bytes)
            # and are charged after the read.
            bytes_read += int(model_report.get("cache_ref_bytes") or 0)
            findings += _norm_report(model_report, "model folder", str(folder))
            notes += [f"{folder.name}: {note}" for note in model_report.get("notes", [])]
            if file_only and folder.name != "tokenizer_config.json":
                continue  # no template to render from config.json alone
            template = inspect_template_isolated(folder, root_strings)
            findings += _norm_report(template, "chat template", str(folder))
            notes += [f"{folder.name}: {note}" for note in template.get("notes", [])]
        except Exception as exc:
            notes.append(f"{folder}: {type(exc).__name__}: {str(exc)[:160]}")

    for file in sorted(loose):
        kind = _kind(file)
        if kind is None:
            continue
        try:
            file_size = size = file.stat().st_size
            if file.suffix == ".txt":
                size *= 2  # read once by the config detector and once by the log detector
            if kind == "template":
                # The template worker also reads the sibling tokenizer_config.json.
                size += _regular_size(file.parent / "tokenizer_config.json", roots)
            if bytes_read + size > MAX_TOTAL_BYTES:
                notes.append(
                    f"{file}: global {MAX_TOTAL_BYTES // (1024 * 1024)} MB scan budget reached; skipped"
                )
                continue
            bytes_read += size
            if file_size > MAX_FILE_BYTES and kind not in {"json", "template"}:
                notes.append(
                    f"{file}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB, skipped"
                )
                continue
            if kind == "template":
                scanned.append({"path": str(file), "kind": "chat template"})
                report = inspect_template_isolated(file, root_strings)
                findings += _norm_report(report, "chat template", str(file))
                notes += [f"{file.name}: {note}" for note in report.get("notes", [])]
            elif kind == "log":
                scanned.append({"path": str(file), "kind": "log"})
                detector_report = inspect_logs([str(file)], root_strings)
                _record_detector_truncations(detector_report, truncations, "log")
                findings += [
                    _norm_static(item, "log")
                    for item in detector_report["findings"]
                ]
            elif kind == "json":
                try:
                    report = inspect_results(file)
                except ValueError as exc:
                    if file_size > MAX_FILE_BYTES:
                        raise
                    notes.append(
                        f"{file.name}: not parsed as eval results ({str(exc)[:100]}); checked as config"
                    )
                    report = {"findings": [], "notes": ["not eval results"]}
                if report["findings"] or not report["notes"]:
                    scanned.append({"path": str(file), "kind": "eval results"})
                    findings += _norm_report(report, "eval results", str(file))
                elif file_size <= MAX_FILE_BYTES:
                    # The config detector reads the file a second time.
                    if bytes_read + file_size > MAX_TOTAL_BYTES:
                        notes.append(f"{file}: global {MAX_TOTAL_BYTES // (1024 * 1024)} MB scan budget reached; skipped")
                        continue
                    bytes_read += file_size
                    scanned.append({"path": str(file), "kind": "config"})
                    detector_report = inspect_files([str(file)], root_strings)
                    _record_detector_truncations(detector_report, truncations, "config")
                    findings += [
                        _norm_static(item, "config")
                        for item in detector_report["findings"]
                    ]
            else:
                scanned.append({
                    "path": str(file),
                    "kind": "config" if file.suffix != ".txt" else "config/log",
                })
                config_report = inspect_files([str(file)], root_strings)
                _record_detector_truncations(config_report, truncations, "config")
                findings += [
                    _norm_static(item, "config")
                    for item in config_report["findings"]
                ]
                if file.suffix == ".txt":
                    log_report = inspect_logs([str(file)], root_strings)
                    _record_detector_truncations(log_report, truncations, "log")
                    findings += [
                        _norm_static(item, "log")
                        for item in log_report["findings"]
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
    if len(ordered) > MAX_SCAN_FINDINGS:
        truncations.append({
            "code": "SCAN_FINDING_LIMIT",
            "limit": MAX_SCAN_FINDINGS,
            "available": len(ordered),
        })
        notes.append(
            f"scan finding output stopped after {MAX_SCAN_FINDINGS} distinct findings; "
            "additional findings were omitted"
        )
        ordered = ordered[:MAX_SCAN_FINDINGS]
    return {
        "kind": "scan",
        "accepted_paths": accepted,
        "scanned": scanned,
        "findings": ordered,
        "traps": sorted({item["trap_id"] for item in ordered}, key=int),
        "truncations": truncations,
        "notes": list(dict.fromkeys(notes)),
        "warning": "Each finding is a lead to check, not a diagnosis. An empty scan means no "
                   "implemented check fired, not that the setup is safe.",
    }
