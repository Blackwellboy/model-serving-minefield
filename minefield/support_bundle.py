"""Explicit, previewable, deterministic support bundle collection."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import zipfile
from pathlib import Path
from typing import Any

from .redaction import redact_text, redact_value

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_TAIL_BYTES = 256 * 1024


def _safe_name(index: int, path: Path, suffix: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.name)[:80] or "evidence"
    return f"{index:03d}-{stem}.{suffix}"


def _read(path: Path) -> str:
    if path.is_symlink():
        raise ValueError(f"symlink input refused: {path}")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"not a regular file: {path}")
    size = resolved.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise ValueError(f"input exceeds {MAX_INPUT_BYTES} bytes: {path}")
    data = resolved.read_bytes()
    if b"\x00" in data[:4096]:
        raise ValueError(f"binary input refused: {path}")
    return data[-MAX_TAIL_BYTES:].decode("utf-8", errors="replace")


def plan(
    *,
    configs: list[str] | None = None,
    logs: list[str] | None = None,
    doctor_report: str | None = None,
    diagnosis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    files: dict[str, bytes] = {}
    redactions: list[dict[str, Any]] = []
    for index, raw in enumerate(configs or [], 1):
        path = Path(raw)
        clean, report = redact_text(_read(path))
        name = f"config/{_safe_name(index, path, 'redacted.txt')}"
        files[name] = clean.encode()
        redactions.extend({"file": name, **item} for item in report)
    for index, raw in enumerate(logs or [], 1):
        path = Path(raw)
        clean, report = redact_text(_read(path))
        name = f"logs/{_safe_name(index, path, 'tail.redacted.txt')}"
        files[name] = clean.encode()
        redactions.extend({"file": name, **item} for item in report)
    if doctor_report:
        clean, report = redact_text(_read(Path(doctor_report)))
        files["doctor.json"] = clean.encode()
        redactions.extend({"file": "doctor.json", **item} for item in report)
    clean_diagnosis, report = redact_value(diagnosis or {"findings": []})
    files["diagnosis.json"] = (
        json.dumps(clean_diagnosis, indent=2, sort_keys=True) + "\n"
    ).encode()
    redactions.extend({"file": "diagnosis.json", **item} for item in report)
    files["system-summary.json"] = (
        json.dumps({
            "platform": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "note": "No hostname, username, environment dump, or hardware probe collected.",
        }, indent=2, sort_keys=True) + "\n"
    ).encode()
    files["versions.json"] = b'{\n  "collection": "explicit-input-only"\n}\n'
    files["matched-traps.md"] = b"# Matched traps\n\nSee `diagnosis.json`; possible matches are not confirmed.\n"
    files["reproduction-notes.md"] = (
        b"# Reproduction notes\n\nAdd bounded confirm/refute results here before sharing.\n"
    )
    privacy = {
        "explicit_inputs_only": True,
        "network_contact": "none",
        "redactions": redactions,
        "files": sorted(files),
        "warning": "Review every file before sharing; redaction cannot prove anonymity.",
    }
    files["privacy-report.json"] = (
        json.dumps(privacy, indent=2, sort_keys=True) + "\n"
    ).encode()
    return {
        "files": files,
        "preview": {
            "files": [{"path": name, "bytes": len(data)} for name, data in sorted(files.items())],
            "redactions": redactions,
            "total_bytes": sum(map(len, files.values())),
        },
    }


def write_bundle(output: str, bundle_plan: dict[str, Any]) -> dict[str, Any]:
    target = Path(output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    files = dict(bundle_plan["files"])
    manifest = "path\tbytes\tsha256\n" + "\n".join(
        f"{name}\t{len(data)}\t{hashlib.sha256(data).hexdigest()}"
        for name, data in sorted(files.items())
    ) + "\n"
    files["MANIFEST.txt"] = manifest.encode()
    sums = "\n".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}"
        for name, data in sorted(files.items())
    ) + "\n"
    files["SHA256SUMS"] = sums.encode()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"unsafe archive name: {name}")
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return {
        "output": str(target),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "files": sorted(files),
    }

