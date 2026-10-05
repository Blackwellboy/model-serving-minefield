"""Resource-isolated chat-template inspection for recursive scans.

``template_inspector`` uses Jinja's immutable sandbox and a trace timeout, which
blocks Python object traversal and long template loops.  A single native
operation or filter can still allocate a very large object before the trace
function runs again.  Recursive CLI/MCP scans therefore render templates in a
short-lived child process with an address-space and CPU limit on POSIX hosts.

On platforms where a hard memory limit is not available, recursive scans skip
rendering and say so explicitly instead of treating an unchecked template as
clean.  Direct library callers can still use ``template_inspector`` when they
control the input and process boundary themselves.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKER_TIMEOUT_S = 10.0
WORKER_MEMORY_BYTES = 512 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 4 * 1024 * 1024


def _empty_report(path: str | Path, note: str) -> dict[str, Any]:
    return {
        "kind": "chat_template",
        "path": str(path),
        "template_origin": "",
        "findings": [],
        "notes": [note],
        "kwargs_read": [],
    }


def _apply_limits() -> None:
    """Apply child-process limits before importing Jinja or reading a template."""
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (WORKER_MEMORY_BYTES, WORKER_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (6, 7))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (MAX_WORKER_OUTPUT_BYTES, MAX_WORKER_OUTPUT_BYTES),
    )
    if hasattr(resource, "RLIMIT_NOFILE"):
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        cap = min(64, hard if hard != resource.RLIM_INFINITY else 64)
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(soft, cap), cap))


def inspect_template_isolated(path: str | Path) -> dict[str, Any]:
    """Inspect one template/model folder in a bounded child process.

    This is the entry point used by ``minefield scan`` and the MCP ``scan_files``
    tool.  It returns the same report shape as ``inspect_template``.  A worker
    timeout, memory-limit death, malformed worker response, or unsupported
    platform is a visible note and never an empty "clean" result.
    """
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"symlink input is refused: {path}")
    if os.name != "posix":
        return _empty_report(
            path,
            "chat-template render checks were skipped because this platform does not "
            "provide the hard process memory limit required for untrusted recursive scans; "
            "that is not a clean result",
        )

    package_parent = str(Path(__file__).resolve().parents[1])
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": package_parent,
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "minefield.safe_template", "--worker", str(target)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=WORKER_TIMEOUT_S,
            check=False,
            env=env,
            cwd=package_parent,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        return _empty_report(
            path,
            f"isolated chat-template worker exceeded {WORKER_TIMEOUT_S:g}s and was stopped; "
            "the template was not checked and that is not a clean result",
        )
    except OSError as exc:
        return _empty_report(
            path,
            f"isolated chat-template worker could not start ({type(exc).__name__}); "
            "the template was not checked and that is not a clean result",
        )

    if completed.returncode != 0:
        reason = (
            f"signal {-completed.returncode}"
            if completed.returncode < 0
            else f"exit code {completed.returncode}"
        )
        return _empty_report(
            path,
            f"isolated chat-template worker stopped with {reason}, usually a CPU or memory "
            "limit; the template was not checked and that is not a clean result",
        )
    if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
        return _empty_report(
            path,
            "isolated chat-template worker returned an oversized report; the template was "
            "not checked and that is not a clean result",
        )
    try:
        value = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _empty_report(
            path,
            "isolated chat-template worker returned an invalid report; the template was not "
            "checked and that is not a clean result",
        )
    if not isinstance(value, dict) or not isinstance(value.get("findings"), list) \
            or not isinstance(value.get("notes"), list):
        return _empty_report(
            path,
            "isolated chat-template worker returned the wrong report shape; the template was "
            "not checked and that is not a clean result",
        )
    return value


def _worker(path: str) -> int:
    _apply_limits()
    try:
        from .template_inspector import inspect_template

        report = inspect_template(path)
    except BaseException as exc:  # child boundary: return a bounded failure report
        report = _empty_report(
            path,
            f"isolated chat-template worker failed with {type(exc).__name__}; the template "
            "was not checked and that is not a clean result",
        )
    payload = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_WORKER_OUTPUT_BYTES:
        payload = json.dumps(
            _empty_report(path, "isolated chat-template report exceeded its output limit; "
                                "that is not a clean result"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    sys.stdout.write(payload)
    sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "--worker":
        sys.stderr.write("safe_template is an internal worker\n")
        return 2
    if os.name != "posix":
        sys.stdout.write(json.dumps(_empty_report(
            argv[1],
            "chat-template worker has no hard memory isolation on this platform; "
            "the template was not checked and that is not a clean result",
        ), separators=(",", ":")))
        return 0
    return _worker(argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
