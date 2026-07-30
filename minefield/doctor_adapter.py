"""Compatibility adapter for the existing standalone endpoint doctor."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .registry import ROOT


def run(args: list[str]) -> int:
    doctor = ROOT / "doctor" / "minefield_doctor.py"
    if not doctor.exists():
        doctor = Path(__file__).resolve().parent / "data" / "minefield_doctor.py"
    completed = subprocess.run([sys.executable, str(doctor), *args], check=False)
    return completed.returncode
