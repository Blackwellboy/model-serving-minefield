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
    # A pasted line carrying the trap's own signature is not a word-overlap
    # match, so the overlap scale does not describe it.
    if match.get("log_signature"):
        return "log line match"
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
        code = {"strong match": "32", "log line match": "32", "possible match": "33"}.get(label, "2")
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
            if match.get("log_signature"):
                out += wrap("why:   ", _clip(match["log_signature"], 260))
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


# How sure a scan rule is, in words a reader can act on. The keys are the
# certainty values the detectors already emit.
_CERTAINTY = {
    "suspicious": "warning",
    "possible": "possible",
    "requiring-runtime-confirmation": "confirm at runtime",
    "configuration-only": "heads-up",
    "low": "minor",
}
_CERTAINTY_COLOR = {"warning": "33", "possible": "33", "confirm at runtime": "36"}


def render_scan(report: dict[str, Any], titles: dict[str, dict[str, str]], *,
                stream: TextIO | None = None) -> str:
    """Findings grouped by file: trap, how sure, what to check, where to read."""
    stream = stream or sys.stdout
    style = _Style(_use_color(stream))
    width = max(60, min(100, shutil.get_terminal_size((88, 20)).columns))
    findings = report.get("findings") or []
    scanned = report.get("scanned") or []
    out = [style.bold(
        f"Scanned {len(scanned)} item{'s' if len(scanned) != 1 else ''}: "
        + (f"{len(findings)} possible trap{'s' if len(findings) != 1 else ''} "
           f"({len(report.get('traps') or [])} distinct)" if findings else "no checks fired")
    )]
    if not findings:
        out += ["", style.dim("That means none of the implemented checks matched, not that the setup is safe."),
                style.dim("Describe a symptom instead:  minefield <what you see>")]
    current = None
    for item in findings:
        if item["file"] != current:
            current = item["file"]
            kind = next((s["kind"] for s in scanned if s["path"] == current), "")
            out += ["", style.bold(f"{current}") + style.dim(f"  ({kind})" if kind else "")]
        trap = item["trap_id"]
        meta = titles.get(trap, {})
        label = _CERTAINTY.get(item.get("certainty") or "", "possible")
        where = f"line {item['line']}" if item.get("line") else ""
        repeat = f" x{item['count']}" if item.get("count", 1) > 1 else ""
        out.append(
            f"  {style.bold('Trap ' + trap)}  {_clip(meta.get('title', ''), width - 16)}"
        )
        out.append(
            "     " + style._wrap(_CERTAINTY_COLOR.get(label, "2"), label)
            + style.dim(f"  ·  {where}{repeat}" if where or repeat else "")
        )
        for line in textwrap.wrap(_clip(item.get("message") or "", 320), width - 7):
            out.append(f"     {line}")
        if meta.get("source_path"):
            out.append(f"     {style.dim('read:  ')}{REPO_URL + meta['source_path']}")
    notes = report.get("notes") or []
    if notes:
        out += ["", style.dim("Notes:")] + [style.dim(f"  - {_clip(n, width - 6)}") for n in notes[:12]]
    if findings:
        out += ["", style.bold("Next step: ") + "open each linked entry and run its check on your setup "
                "before changing anything."]
    out += ["", style.dim("Full detail for scripts and agents: add --json")]
    return "\n".join(out)
