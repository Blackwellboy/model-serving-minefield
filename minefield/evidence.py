"""Small public-safe helpers used by Minefield evidence tooling/tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def verify_git_checkout(root: Path, expected_revision: str) -> None:
    """Require a supplied source tree to be the clean immutable revision."""
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("source root must be a readable Git checkout") from exc
    if revision != expected_revision:
        raise ValueError(
            f"revision mismatch: expected {expected_revision}, got {revision}"
        )
    if status:
        raise ValueError("Git checkout has tracked local modifications")
