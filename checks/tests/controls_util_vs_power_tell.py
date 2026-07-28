#!/usr/bin/env python3
"""Contract controls for `checks/util_vs_power_tell.sh`.

A shell check cannot declare Python callables, so its controls live here and
drive the script out-of-process. Before this file existed, discovery globbed
`*.py` only: the script was never contract-tested, and the harness still
printed "ALL PASS (8 checks conform)" over a set that silently excluded it.

Each control puts a stub `nvidia-smi` first on PATH, so the script reads a
chosen sample stream with no GPU, no driver and no network, then returns the
script's exit code for the harness to judge exactly as it judges a Python
check.

Exit codes: 0 ran, nothing blocking. 1 unreachable. 2 blocking. 3 inspected
nothing.
"""
import os
import subprocess
import tempfile
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "util_vs_power_tell.sh"

STUB = """#!/usr/bin/env bash
# Stub nvidia-smi. Emits a fixed sample stream; ignores every argument.
cat <<'ROWS'
{rows}
ROWS
"""


def _run_with_samples(rows):
    """Run the check with a stub nvidia-smi emitting `rows`. Return exit code."""
    with tempfile.TemporaryDirectory() as d:
        stub = Path(d) / "nvidia-smi"
        stub.write_text(STUB.format(rows=rows), encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{d}{os.pathsep}" + env.get("PATH", "")
        return subprocess.run(
            ["bash", str(CHECK), "3", "0"],
            env=env, capture_output=True, text=True, timeout=60,
        ).returncode


def _control_high_util_low_power():
    """The measured case: ~98% utilization at ~47% TDP. MUST report BLOCKING.

    This is the tell the check exists to catch: busy compute units that are
    not saturating tensor cores, which is what a fallback kernel looks like.
    """
    return _run_with_samples("98, 130.0, 275.0\n97, 128.0, 275.0\n99, 131.0, 275.0")


def _control_util_high_power_healthy_is_not_blocking():
    """Inverse guard: a genuinely healthy lane must NOT report the finding.

    Without this, a check that returned BLOCKING unconditionally would satisfy
    the control above and be indistinguishable from a working one.
    """
    code = _run_with_samples("95, 220.0, 275.0\n96, 224.0, 275.0\n95, 221.0, 275.0")
    # Deliberately inverted, like any guard whose PASS condition is the
    # absence of a finding: the harness requires a non-zero code, so we map
    # "correctly clean" to BLOCKING and "wrongly blocking" to OK.
    return 2 if code == 0 else 0


def _control_na_power_is_not_a_pass():
    """Jetson and GB10-class boards report [N/A] power.

    An earlier version let awk coerce that to 0 W, which reported SUSPECT
    FALLBACK on every healthy lane on those boards. Unreadable power must be
    "inspected nothing" (3), never a finding and never a pass.
    """
    return _run_with_samples("98, [N/A], [N/A]\n97, [N/A], [N/A]")


NEGATIVE_CONTROLS = [
    ("high utilization at low power draw is blocking", _control_high_util_low_power),
    ("a healthy lane is not reported as a fallback", _control_util_high_power_healthy_is_not_blocking),
]
EMPTY_SET_CONTROL = ("power unreadable, so nothing was inspected", _control_na_power_is_not_a_pass)
