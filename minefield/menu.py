"""One menu of everything Minefield can do, for people and for harnesses.

The catalogue is data. `minefield menu` renders it for a terminal (and walks a
person through one choice), `minefield menu --json` hands it to any harness,
the MCP server lists it, and a harness plugin maps each item to a slash
command. Every item states what it touches before it runs: nothing, files you
name, or a number of requests to an endpoint you name.
"""

from __future__ import annotations

import shlex
import sys
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional, Sequence, TextIO

MENU_SCHEMA_VERSION = "minefield.menu.v1"


@dataclass(frozen=True)
class MenuInput:
    name: str
    prompt: str
    required: bool = True
    repeatable: bool = False


@dataclass(frozen=True)
class MenuItem:
    key: str                      # what the person types: "1", "2", ...
    id: str                       # stable id for harnesses
    title: str                    # one line, plain words
    detail: str                   # what it does and what it never does
    touches: str                  # "nothing" | "files you name" | "endpoint: up to N requests"
    argv: tuple[str, ...]         # `minefield` argv; {name} placeholders are filled from inputs
    inputs: tuple[MenuInput, ...] = ()
    slash: Optional[str] = None   # the matching chat slash command, when a harness plugin has one
    confirm: bool = False         # ask before running (live traffic beyond a lite check)
    tags: tuple[str, ...] = field(default_factory=tuple)


MENU: tuple[MenuItem, ...] = (
    MenuItem(
        "1", "symptom", "I'm seeing something odd: find matching traps",
        "Matches a plain-words symptom against every trap. Offline. A miss means "
        "'not documented here', never 'safe'.",
        "nothing",
        ("guide", "--text", "{symptom}"),
        (MenuInput("symptom", "What are you seeing? (one sentence)"),),
        slash="/minefield guide <what you see>", tags=("offline",)),
    MenuItem(
        "2", "scan", "Check my config, launch script, logs or eval results",
        "Reads only the files you name and reports possible traps with the line. "
        "Never edits them.",
        "files you name",
        ("scan", "--text", "{paths...}"),
        (MenuInput("paths", "File or folder paths (space separated)", repeatable=True),),
        slash="/minefield scan [path ...]", tags=("offline",)),
    MenuItem(
        "3", "lite", "Quick live check of my endpoint",
        "A bounded preflight of an OpenAI-compatible endpoint. Sends at most 5 short "
        "chat requests.",
        "endpoint: up to 5 requests",
        ("diagnose", "--text", "--mode", "lite", "--base-url", "{base_url}"),
        (MenuInput("base_url", "Endpoint base URL (e.g. http://localhost:8000/v1)"),),
        slash="/minefield check", tags=("live",)),
    MenuItem(
        "4", "plan", "Preview a full Doctor run (no network)",
        "Lists every probe a full Doctor would run and its request budget. Sends nothing.",
        "nothing",
        ("doctor-plan", "--mode", "doctor", "--text"),
        slash="/minefield doctor", tags=("offline",)),
    MenuItem(
        "5", "doctor", "Full Doctor on my endpoint",
        "Runs every applicable live probe (dozens of requests; see option 4 for the "
        "exact budget). Results apply only to the checks that ran.",
        "endpoint: up to 48 requests",
        ("quick", "--base-url", "{base_url}"),
        (MenuInput("base_url", "Endpoint base URL (e.g. http://localhost:8000/v1)"),
         MenuInput("model", "Model id to test (blank = the server's first)", required=False)),
        slash="/minefield doctor --yes", confirm=True, tags=("live",)),
    MenuItem(
        "6", "coverage", "What can be checked automatically",
        "How many traps have endpoint, file and log checks, and which do not.",
        "nothing",
        ("coverage",),
        tags=("offline",)),
    MenuItem(
        "7", "bundle", "Prepare a support bundle to share (preview only)",
        "Shows what a redacted bundle of the files you name would contain. Writes "
        "nothing and uploads nothing.",
        "files you name",
        ("bundle", "--no-write", "{configs...@--config}", "{logs...@--log}"),
        (MenuInput("configs", "Config / launch-script paths (space separated, blank for none)",
                   required=False, repeatable=True),
         MenuInput("logs", "Log paths (space separated, blank for none)",
                   required=False, repeatable=True)),
        slash="/minefield contribute", tags=("offline",)),
)


def items() -> tuple[MenuItem, ...]:
    return MENU


def find(choice: str) -> Optional[MenuItem]:
    """Accept the number, the id, or the id's first letters ('doc' -> doctor)."""
    c = (choice or "").strip().lower()
    if not c:
        return None
    for item in MENU:
        if c in (item.key, item.id):
            return item
    starts = [item for item in MENU if item.id.startswith(c)]
    return starts[0] if len(starts) == 1 else None


def build_argv(item: MenuItem, values: dict[str, object]) -> list[str]:
    """Fill placeholders.

    `{name}` one value; `{name...}` a list spliced in; `{name...@--flag}` the flag
    before every value (nothing at all for an empty list).
    """
    def listed(key: str) -> list[str]:
        raw = values.get(key) or []
        return [str(v) for v in raw] if isinstance(raw, list) else shlex.split(str(raw))

    out: list[str] = []
    for part in item.argv:
        if part.startswith("{") and "...@" in part and part.endswith("}"):
            key, flag = part[1:-1].split("...@", 1)
            for value in listed(key):
                out += [flag, value]
        elif part.startswith("{") and part.endswith("...}"):
            out.extend(listed(part[1:-4]))
        elif part.startswith("{") and part.endswith("}"):
            out.append(str(values.get(part[1:-1]) or ""))
        else:
            out.append(part)
    model = values.get("model")
    if item.id == "doctor" and model:
        out += ["--model", str(model)]
    return out


def as_dict() -> dict[str, object]:
    return {"schema": MENU_SCHEMA_VERSION,
            "items": [asdict(item) for item in MENU]}


def render(style: str = "text") -> str:
    """The menu as plain text (terminal / chat) or Markdown."""
    md = style == "markdown"
    lines = ["**Model Serving Minefield**" if md else "Model Serving Minefield", ""]
    for item in MENU:
        if md:
            lines.append(f"{item.key}. **{item.title}**  _(touches: {item.touches})_")
        else:
            lines.append(f"  {item.key}  {item.title}")
            lines.append(f"     {item.detail}  [touches: {item.touches}]")
    lines += ["", "Pick a number (or q to quit)." if not md else
              "Run with `minefield menu` (terminal) or the item's command."]
    return "\n".join(lines)


def _ask(prompt: str, stdin: TextIO, stdout: TextIO) -> str:
    stdout.write(prompt)
    stdout.flush()
    line = stdin.readline()
    if not line:
        raise EOFError
    return line.strip()


def interactive(run: Callable[[Sequence[str]], int], *, stdin: TextIO = sys.stdin,
                stdout: TextIO = sys.stdout) -> int:
    """Show the menu, take one choice, collect its inputs, confirm if needed, run it."""
    stdout.write(render() + "\n")
    try:
        while True:
            choice = _ask("> ", stdin, stdout)
            if choice.lower() in {"q", "quit", "exit"}:
                return 0
            item = find(choice)
            if item is None:
                stdout.write("Not an option. Type a number from the list, or q.\n")
                continue
            values: dict[str, object] = {}
            for inp in item.inputs:
                answer = _ask(f"{inp.prompt}: ", stdin, stdout)
                if not answer and inp.required:
                    stdout.write(f"{inp.name} is needed for this option.\n")
                    return 2
                values[inp.name] = shlex.split(answer) if inp.repeatable else answer
            argv = build_argv(item, values)
            stdout.write(f"\nRunning: minefield {' '.join(shlex.quote(a) for a in argv)}\n")
            stdout.write(f"Touches: {item.touches}\n")
            if item.confirm:
                if _ask("Go ahead? [y/N] ", stdin, stdout).lower() not in {"y", "yes"}:
                    stdout.write("Cancelled. Nothing was sent.\n")
                    return 0
            stdout.write("\n")
            stdout.flush()
            return run(argv)
    except (EOFError, KeyboardInterrupt):
        stdout.write("\n")
        return 0
