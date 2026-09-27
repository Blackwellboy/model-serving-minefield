"""Offline chat-template analysis: render the template, read what the model sees.

Most template traps are invisible in the request and obvious in the rendered
prompt. This module renders a supplied chat template against a fixed set of
probe conversations and checks the rendered text for the failure shapes the
registry documents.

Safety: templates are rendered in Jinja2's ImmutableSandboxedEnvironment, the
environment designed for untrusted templates (no attribute access to Python
internals, no mutation of passed objects, bounded ranges). Nothing is sent to
any server, and trap markdown is never executed. The render mirrors
Hugging Face ``apply_chat_template`` (trim_blocks, lstrip_blocks, loopcontrols,
tojson, raise_exception, strftime_now); a serving engine with its own Jinja
implementation can still render differently, which is trap 24's point.

Every finding is a possible match. A render proves what this template text
does, not what your server does with it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

MAX_TEMPLATE_BYTES = 512 * 1024
MAX_TOKENIZER_CONFIG_BYTES = 8 * 1024 * 1024

# Probe markers: plain words that no real template contains.
USER1, USER2 = "PROBEUSERONE", "PROBEUSERTWO"
ASST1 = "PROBEASSISTANTONE"
SYS = "PROBESYSTEMMARK"
LATE_SYS = "PROBELATESYSTEM"
REASON = "PROBEREASONINGMARK"
ARG = "PROBEARGCITY"
ALPHA, OMEGA = "PROBEALPHA", "PROBEOMEGA"
PATH = "PROBEPATH"

THINKING_KWARGS = ("enable_thinking", "thinking", "enable_reasoning", "reasoning")
_STANDARD_VARS = {
    "messages", "tools", "add_generation_prompt", "bos_token", "eos_token",
    "pad_token", "unk_token", "raise_exception", "strftime_now", "range",
    "namespace", "documents", "tools_in_user_message", "date_string",
    "custom_tools", "builtin_tools", "loop", "true", "false", "none",
}


class TemplateNotFound(ValueError):
    pass


def _jinja_available() -> bool:
    try:
        import jinja2  # noqa: F401
    except ImportError:
        return False
    return True


def _tojson(value: Any, ensure_ascii: bool = False, indent: Any = None,
            separators: Any = None, sort_keys: bool = False) -> str:
    return json.dumps(value, ensure_ascii=ensure_ascii, indent=indent,
                      separators=separators, sort_keys=sort_keys)


def _environment():
    from jinja2 import TemplateError
    from jinja2.ext import loopcontrols
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    def raise_exception(message: str) -> None:
        raise TemplateError(message)

    def strftime_now(fmt: str) -> str:
        return datetime(2026, 1, 1).strftime(fmt)  # fixed: renders stay reproducible

    env = ImmutableSandboxedEnvironment(
        trim_blocks=True, lstrip_blocks=True, extensions=[loopcontrols]
    )
    env.filters["tojson"] = _tojson
    env.globals["raise_exception"] = raise_exception
    env.globals["strftime_now"] = strftime_now
    return env


def _token_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("content") or "")
    return str(value or "")


def load_template(path: str | Path) -> dict[str, Any]:
    """Find the chat template for a file or model folder.

    Returns {"source": str|None, "origin": str, "bos_token", "eos_token",
    "python_encoder": bool}. ``source`` is None when the checkpoint ships no
    Jinja template (trap 56).
    """
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"symlink input is refused: {path}")
    folder = target if target.is_dir() else target.parent
    tok_cfg: dict[str, Any] = {}
    cfg_path = folder / "tokenizer_config.json"
    if cfg_path.is_file() and not cfg_path.is_symlink() and cfg_path.stat().st_size <= MAX_TOKENIZER_CONFIG_BYTES:
        try:
            tok_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            tok_cfg = {}
    result = {
        "source": None,
        "origin": "",
        "bos_token": _token_text(tok_cfg.get("bos_token")),
        "eos_token": _token_text(tok_cfg.get("eos_token")),
        "python_encoder": False,
    }

    def read_jinja(file: Path) -> str:
        if file.stat().st_size > MAX_TEMPLATE_BYTES:
            raise ValueError(f"template exceeds {MAX_TEMPLATE_BYTES} bytes: {file}")
        return file.read_text(encoding="utf-8")

    if target.is_file() and target.suffix == ".jinja":
        result.update(source=read_jinja(target), origin=target.name)
        return result
    if target.is_dir():
        jinja = target / "chat_template.jinja"
        if jinja.is_file() and not jinja.is_symlink():
            result.update(source=read_jinja(jinja), origin=jinja.name)
            return result
    template = tok_cfg.get("chat_template")
    if isinstance(template, list):
        named = {item.get("name"): item.get("template") for item in template if isinstance(item, dict)}
        template = named.get("default") or next(iter(named.values()), None)
    if isinstance(template, str) and template.strip():
        result.update(source=template, origin="tokenizer_config.json:chat_template")
        return result
    result["python_encoder"] = any(
        p.suffix == ".py" and "encod" in p.name.lower() for p in folder.iterdir() if p.is_file()
    )
    return result


class _Renderer:
    def __init__(self, source: str, bos: str, eos: str) -> None:
        self.template = _environment().from_string(source)
        self.bos, self.eos = bos, eos

    def __call__(self, messages: list[dict[str, Any]], *, gen: bool = True,
                 tools: list[dict[str, Any]] | None = None, **kwargs: Any) -> str:
        return self.template.render(
            messages=messages, tools=tools, add_generation_prompt=gen,
            bos_token=self.bos, eos_token=self.eos, **kwargs,
        )


def _u(text: str) -> dict[str, Any]:
    return {"role": "user", "content": text}


def _a(text: str, **extra: Any) -> dict[str, Any]:
    return {"role": "assistant", "content": text, **extra}


_TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Weather for a city",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    },
}]


def _tool_history(arguments: Any) -> list[dict[str, Any]]:
    return [
        _u(USER1),
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "get_weather", "arguments": arguments},
        }]},
        {"role": "tool", "tool_call_id": "call_1", "name": "get_weather", "content": "sunny"},
    ]


def _finding(trap: str, message: str, evidence: str = "", certainty: str = "possible") -> dict[str, Any]:
    return {"trap_id": trap, "certainty": certainty, "message": message, "evidence": evidence[:300]}


_ROLE_MARKER = re.compile(r"<\|?[A-Za-z_]{2,20}\|?>|\[/?[A-Z_]{2,12}\]|\b(?:system|user|assistant)\b", re.I)


def _prose_before(text: str, marker: str) -> str:
    head = text[: text.find(marker)] if marker in text else text
    head = re.sub(r"<[^>\n]{0,40}>|\[/?[A-Z_]{1,20}\]", " ", head)
    head = re.sub(r"\b(?:system|user|assistant)\b", " ", head, flags=re.I)
    return " ".join(head.split())


def _checks(render: _Renderer, source: str) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    notes: list[str] = []

    def attempt(name: str, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:  # a probe the template cannot render is a note, not a finding
            notes.append(f"{name}: not checked ({type(exc).__name__}: {str(exc)[:120]})")

    # 83 / 30: a default system prompt that is injected, then replaced wholesale.
    def default_system() -> None:
        bare = render([_u(USER1)])
        prose = _prose_before(bare, USER1)
        if sum(ch.isalpha() for ch in prose) < 40:
            return
        findings.append(_finding(
            "83", "The template writes its own system prompt when the request sends none, so a "
            "'no system prompt' run is not one.", prose[:160]))
        with_sys = render([{"role": "system", "content": SYS}, _u(USER1)])
        sample = prose[:40]
        if sample and sample not in " ".join(with_sys.split()):
            findings.append(_finding(
                "30", "Sending any system prompt removes that built-in default entirely, so every "
                "system-prompt condition also changes the model's default identity.", sample))

    # 38: the generation prompt already opens the think block.
    def think_prefill() -> None:
        tail = render([_u(USER1)], gen=True).rstrip()
        if tail.endswith("<think>"):
            findings.append(_finding(
                "38", "The generation prompt ends with <think>, so the model never writes the opening "
                "tag. Offline pipelines that build their own prompt must add it.", tail[-60:]))

    # 43 / 84: tool-call argument dialect and the agent-loop shape.
    def tool_args() -> None:
        as_dict = render(_tool_history({"city": ARG}), tools=_TOOLS)
        try:
            as_str = render(_tool_history(json.dumps({"city": ARG})), tools=_TOOLS)
        except Exception as exc:
            findings.append(_finding(
                "43", "Tool-call arguments sent as a JSON string (the OpenAI format) fail to render.", str(exc)))
            return
        if ARG in as_dict and ARG not in as_str:
            findings.append(_finding(
                "43", "Tool-call arguments render only when they are an object. Replayed calls with "
                "string arguments (the OpenAI format) become empty calls, and agents loop."))

    def tool_then_user() -> None:
        # The round trip on its own must render; only the added user turn is under test.
        render(_tool_history({"city": ARG}), tools=_TOOLS)
        try:
            render(_tool_history({"city": ARG}) + [_u(USER2)], tools=_TOOLS)
        except Exception as exc:
            findings.append(_finding(
                "84", "A completed tool round trip followed by a user message cannot be rendered, so "
                "the agent loop dies after one tool call.", str(exc)))

    # 66: the template scans user text for /think or /no_think and edits it.
    def toggle_scan() -> None:
        if "/no_think" not in source and "/think" not in source:
            return
        sent = f"copy /no_think/{PATH} and /think/{PATH}"
        rendered = render([_u(sent)])
        if PATH in rendered and sent not in rendered:
            findings.append(_finding(
                "66", "The template looks for /think or /no_think inside user text, obeys it, and "
                "deletes it, which corrupts ordinary paths such as /srv/no_think/data."))

    # 67: list-form content rendered as a Python object.
    def list_content() -> None:
        part = lambda text: [{"type": "text", "text": text}]  # noqa: E731
        rendered = render([
            {"role": "user", "content": part(USER1)},
            {"role": "assistant", "content": part(ASST1)},
            {"role": "user", "content": part(USER2)},
        ])
        if re.search(r"\[\{'type'|'text':", rendered):
            findings.append(_finding(
                "67", "Message content sent as a list of parts is printed into the prompt as Python "
                "syntax ([{'type': 'text', ...}]).", rendered[rendered.find("[{"):][:120]))

    # 68: media/text order discarded, adjacent text parts glued.
    def part_order() -> None:
        text_a = {"type": "text", "text": ALPHA}
        text_b = {"type": "text", "text": OMEGA}
        image = {"type": "image"}
        interleaved = render([{"role": "user", "content": [text_a, image, text_b]}])
        image_first = render([{"role": "user", "content": [image, text_a, text_b]}])
        text_only = render([{"role": "user", "content": [text_a, text_b]}])
        if ALPHA + OMEGA in text_only or ALPHA + OMEGA in interleaved:
            findings.append(_finding(
                "68", "Adjacent text parts are joined with no separator, so the end of one part "
                "runs into the start of the next.", ALPHA + OMEGA))
        if interleaved != text_only and interleaved == image_first:
            findings.append(_finding(
                "68", "The position of an image relative to the text is discarded: [text, image, text] "
                "and [image, text, text] render identically."))

    # 69: unbalanced ChatML tags and a leading-whitespace prompt.
    def minor_defects() -> None:
        full = render([
            {"role": "system", "content": SYS}, _u(USER1), _a(ASST1), _u(USER2), _a("PROBEASSISTANTTWO"),
        ], gen=False)
        opens, closes = full.count("<|im_start|>"), full.count("<|im_end|>")
        if opens and opens != closes:
            findings.append(_finding(
                "69", f"<|im_start|> and <|im_end|> are unbalanced ({opens} vs {closes}) in a complete "
                "conversation.", certainty="low"))
        bare = render([_u(USER1)])
        if bare[:1].isspace():
            findings.append(_finding(
                "69", "The rendered prompt starts with whitespace, which breaks exact-match "
                "assertions and wastes a token.", repr(bare[:20]), certainty="low"))

    # 82 / 93: the system prompt migrates to the latest user turn.
    def system_relocation() -> None:
        rendered = render([{"role": "system", "content": SYS}, _u(USER1), _a(ASST1), _u(USER2)])
        if SYS in rendered and ASST1 in rendered and rendered.find(SYS) > rendered.find(ASST1):
            findings.append(_finding(
                "82", "The system prompt is moved to the most recent user turn, so the prompt prefix "
                "changes every turn and the prefix cache cannot reuse it."))
            findings.append(_finding(
                "93", "Because the system text moves every turn, 'move the clock out of the system "
                "prompt' advice does not apply to this template, and can make caching worse."))

    # 113: a system message after a user turn.
    def inline_system() -> None:
        render([_u(USER1), _a(ASST1), _u(USER2)])  # the same turns without the late system must render
        try:
            rendered = render([_u(USER1), {"role": "system", "content": LATE_SYS}, _u(USER2)])
        except Exception as exc:
            findings.append(_finding(
                "113", "A system message placed after a user turn is rejected by the template.", str(exc)))
            return
        if LATE_SYS not in rendered:
            findings.append(_finding(
                "113", "A system message placed after a user turn is silently dropped."))
            return
        between = rendered[rendered.find(USER1) + len(USER1): rendered.find(LATE_SYS)]
        if USER1 in rendered and not _ROLE_MARKER.search(between):
            findings.append(_finding(
                "113", "A system message placed after a user turn is welded into the user text with "
                "no system boundary.", between[:60]))

    # 57: a thinking switch evaluated for truthiness.
    def truthiness() -> None:
        read = [name for name in THINKING_KWARGS if re.search(rf"\b{name}\b", source)]
        for name in read:
            off = render([_u(USER1)], **{name: False})
            as_string = render([_u(USER1)], **{name: "false"})
            if off != as_string:
                findings.append(_finding(
                    "57", f'Sending {name} as the string "false" renders differently from the boolean '
                    'false, because the template tests truthiness. Clients that build kwargs from '
                    "env vars or YAML send strings.", name))
                return

    # 04 / 20 / 25: prior-turn reasoning handling.
    def history_reasoning() -> None:
        def hist(**field: Any) -> list[dict[str, Any]]:
            return [_u(USER1), _a(ASST1, **field), _u(USER2)]
        under_rc = REASON in render(hist(reasoning_content=REASON))
        under_r = REASON in render(hist(reasoning=REASON))
        if "think" not in source and "reason" not in source:
            return
        if not under_rc and not under_r:
            findings.append(_finding(
                "04", "Prior-turn reasoning is removed from the history at default settings, so in "
                "multi-turn chats the model sees its own past turns without reasoning."))
        elif under_rc != under_r:
            kept = "reasoning_content" if under_rc else "reasoning"
            dropped = "reasoning" if under_rc else "reasoning_content"
            findings.append(_finding(
                "20", f"Only the '{kept}' field reaches the template; reasoning resent under "
                f"'{dropped}' is silently dropped."))
        plain = render(hist())
        if re.search(r"<think>\s*</think>", plain[: plain.find(USER2)] if USER2 in plain else plain):
            findings.append(_finding(
                "25", "Assistant turns without reasoning are rendered with an empty <think></think> "
                "pair, which changes the prompt and defeats prefix caching."))

    # 24: constructs that C++ Jinja engines (llama.cpp, LM Studio) handle differently.
    if re.search(r"\|\s*items\b", source):
        findings.append(_finding(
            "24", "The template uses the |items filter, a Python-Jinja construct that C++ Jinja "
            "engines (llama.cpp, LM Studio) have mis-rendered. Compare a render from your engine.",
            certainty="configuration-only"))

    try:
        render([_u(USER1)])
    except Exception as exc:
        notes.append("the template does not render a one-message conversation, so no probe could run "
                     f"({type(exc).__name__}: {str(exc)[:120]})")
        return findings, notes

    for name, fn in (
        ("default system prompt", default_system), ("generation prompt", think_prefill),
        ("tool arguments", tool_args), ("tool then user", tool_then_user),
        ("in-text toggles", toggle_scan), ("list content", list_content),
        ("part order", part_order), ("minor defects", minor_defects),
        ("system relocation", system_relocation), ("inline system", inline_system),
        ("thinking truthiness", truthiness), ("history reasoning", history_reasoning),
    ):
        attempt(name, fn)
    return findings, notes


def _kwargs_read(source: str) -> list[str]:
    from jinja2 import meta

    try:
        names = meta.find_undeclared_variables(_environment().parse(source))
    except Exception:
        return []
    # meta reports names first assigned inside a block scope as undeclared;
    # anything the template itself sets is not a request switch.
    assigned = set(re.findall(r"\{%-?\s*set\s+(\w+)", source))
    return sorted(name for name in names if name not in _STANDARD_VARS and name not in assigned)


IMPLEMENTED_TRAPS = frozenset({
    "04", "20", "24", "25", "30", "38", "43", "56", "57", "66", "67", "68", "69",
    "82", "83", "84", "93", "113",
})


def inspect_template(path: str | Path) -> dict[str, Any]:
    info = load_template(path)
    report: dict[str, Any] = {
        "kind": "chat_template",
        "path": str(path),
        "template_origin": info["origin"],
        "findings": [],
        "notes": [],
        "kwargs_read": [],
    }
    if info["source"] is None:
        report["findings"].append(_finding(
            "56", "No Jinja chat template was found (no chat_template.jinja and no chat_template in "
            "tokenizer_config.json)."
            + (" A Python encoder ships instead, so the prompt is built by code: ask the server what it "
               "renders." if info["python_encoder"] else " The server will use its own fallback template."),
            certainty="configuration-only"))
        return report
    if not _jinja_available():
        # Say so plainly: an empty findings list here would read as a clean template.
        report["notes"].append("jinja2 is not installed, so the template could not be rendered and no "
                               "render checks ran (pip install 'jinja2>=3.1').")
        if re.search(r"\|\s*items\b", info["source"]):
            report["findings"].append(_finding(
                "24", "The template uses the |items filter, a Python-Jinja construct that C++ Jinja "
                "engines (llama.cpp, LM Studio) have mis-rendered. Compare a render from your engine.",
                certainty="configuration-only"))
        return report
    try:
        render = _Renderer(info["source"], info["bos_token"], info["eos_token"])
    except Exception as exc:
        report["notes"].append(f"template does not parse: {type(exc).__name__}: {str(exc)[:160]}")
        return report
    findings, notes = _checks(render, info["source"])
    report["findings"] = findings
    report["notes"] = notes
    report["kwargs_read"] = _kwargs_read(info["source"])
    if report["kwargs_read"]:
        report["notes"].append(
            "The template reads these request switches: " + ", ".join(report["kwargs_read"])
            + ". Check each is documented on the model card; an undocumented switch is an untested variable."
        )
    return report
