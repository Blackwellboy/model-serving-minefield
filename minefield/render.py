"""Plain-text rendering of a diagnosis for people reading a terminal.

The JSON contract (``minefield guide --json``, the MCP server, the library
API) is unchanged and remains the machine surface. This module only decides
how that same result reads to a human: a short ranked list, how strong each
match is, the one check to run next, and where to read more.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from typing import Any, TextIO

REPO_URL = "https://github.com/Blackwellboy/model-serving-minefield/blob/main/"

# Calibrated on benchmarks/symptom_queries.json (tune split): among top-5
# results at or above STRONG, about 84% are the trap the user meant; at or
# above POSSIBLE, about half.
STRONG = 3.5
POSSIBLE = 2.5

_FENCE = re.compile(r"```[a-zA-Z]*")


def strength(match: dict[str, Any]) -> str:
    weight = float(match.get("evidence_weight") or 0.0)
    if weight >= STRONG:
        return "strong match"
    if weight >= POSSIBLE:
        return "possible match"
    return "weak match"


def _clip(text: str, limit: int) -> str:
    """Collapse whitespace, drop code fences, and cut on a sentence boundary."""
    text = " ".join(_FENCE.sub(" ", text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("? "))
    if stop > limit * 0.5:
        return cut[: stop + 1]
    return cut.rsplit(" ", 1)[0] + " ..."


def _check_text(text: str, limit: int) -> str:
    clipped = _clip(text, limit)
    # Checks often introduce a command with a colon; the command itself is in
    # the entry, so say so instead of ending mid-thought.
    if clipped.endswith(":"):
        clipped += " (commands in the linked entry)"
    return clipped


def _use_color(stream: TextIO) -> bool:
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


class _Style:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def strength(self, label: str) -> str:
        code = {"strong match": "32", "possible match": "33"}.get(label, "2")
        return self._wrap(code, label)


def render_diagnosis(result: dict[str, Any], *, limit: int = 5, stream: TextIO | None = None) -> str:
    stream = stream or sys.stdout
    style = _Style(_use_color(stream))
    width = max(60, min(100, shutil.get_terminal_size((88, 20)).columns))
    body = width - 7

    def wrap(label: str, text: str) -> list[str]:
        lines = textwrap.wrap(text, body - len(label)) or [""]
        pad = " " * (5 + len(label))
        return [f"     {style.dim(label)}{lines[0]}"] + [pad + line for line in lines[1:]]

    symptom = result.get("observed_symptom") or ""
    out = [style.bold(f'Traps that match: "{_clip(symptom, 70)}"')]
    matches = (result.get("matches") or [])[:limit]

    if not matches:
        out += [
            "",
            "No documented trap matches that description.",
            style.dim("That means nobody has written this one up yet, not that your setup is safe."),
            "",
            "Try:",
            "  - describe what you observe, e.g. \"empty content when streaming\" or \"decode slows at long context\"",
            "  - add the stack:  --stack vllm  (or llama.cpp, ollama, sglang, mlx)",
            "  - check a live endpoint:  minefield quick --base-url http://HOST:PORT/v1",
        ]
    else:
        out.append(style.dim("Ranked by how closely your description matches. A match is a lead to check, not a diagnosis."))
        shown = [m for m in matches if strength(m) != "weak match"] or matches[:1]
        weaker = [m for m in matches if m not in shown]
        for number, match in enumerate(shown, 1):
            trap = match["trap_ids"][0]
            out += ["", f" {number}. {style.bold('Trap ' + trap)}  {_clip(match.get('title', ''), body - 10)}"]
            out.append(
                f"     {style.strength(strength(match))}"
                + style.dim(f"  ·  evidence: {_clip(str(match.get('evidence_status') or 'unstated'), 50).rstrip('.')}")
            )
            out += wrap("check: ", _check_text(match.get("confirmation_check", ""), 260))
            if match.get("source_path"):
                # Never wrap a URL: a wrapped link is not clickable.
                out.append(f"     {style.dim('read:  ')}{REPO_URL + match['source_path']}")
        if weaker:
            out += ["", style.dim("Weaker matches: ") + ", ".join(
                f"{m['trap_ids'][0]} ({_clip(m.get('title', ''), 40)})" for m in weaker
            )]
        out += [
            "",
            style.bold("Next step: ") + f"run the check for trap {shown[0]['trap_ids'][0]} on your exact setup before changing anything.",
        ]

    # Leads are a strictly weaker tier; only surface them when the canonical
    # registry had nothing to offer at all.
    leads = result.get("possible_unverified_leads") or []
    if leads and not matches:
        out += ["", style.dim("Unverified leads (weaker, not yet reproduced):")]
        for lead in leads[:3]:
            out.append(style.dim(f"  {lead['lead_id']}  {_clip(lead.get('title', ''), body - 6)}"))

    out += ["", style.dim("Full detail for scripts and agents: add --json")]
    return "\n".join(out)
