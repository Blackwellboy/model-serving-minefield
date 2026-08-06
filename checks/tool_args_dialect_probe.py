#!/usr/bin/env python3
"""Trap 43 check: does the chat template survive tool-call `arguments` arriving as a STRING?

The OpenAI spec says `arguments` is a string. Templates that gate parameter expansion on
`arguments is mapping` with no `else` render an EMPTY tool call when a framework replays a
prior call with pre-serialized JSON. The model then loops on its own malformed call.

Offline mode renders the template both ways and asserts the argument VALUE appears.
Live mode sends a real `tools` array, asserts structured tool_calls, then replays with
string-valued arguments.

Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
3 ran, but inspected nothing.

Usage:
  python3 tool_args_dialect_probe.py --template ./chat_template.jinja
  python3 tool_args_dialect_probe.py --base-url http://127.0.0.1:8080/v1 --model NAME
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3

# The sentinel MUST NOT appear anywhere else in the rendered conversation, or the
# assertion cannot fail on the bug it exists to catch. The user turn deliberately
# names a DIFFERENT city; only the tool-call arguments carry the sentinel.
SENTINEL = "Reykjavik"
USER_CITY = "Paris"

TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}
ARGS_OBJ = {"city": SENTINEL}
ARGS_STR = json.dumps(ARGS_OBJ)


def replay_messages(arguments):
    """A conversation that REPLAYS an assistant tool call: the shape that triggers the bug."""
    return [
        {"role": "user", "content": f"What is the weather in {USER_CITY}?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": arguments},
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "18C, clear"},
        {"role": "user", "content": "And the one after that?"},
    ]


def evaluate_renders(renders):
    """Pure core. `renders` maps a label to rendered text, or to None if rendering raised.

    Returns (code, lines). Empty input is NOTHING_INSPECTED, never OK.
    """
    lines = []
    if not renders:
        return NOTHING_INSPECTED, ["nothing rendered; no template was inspected"]

    blocking = False
    for label, rendered in renders.items():
        if rendered is None:
            lines.append(f"  {label:12s}: RENDER ERROR (a render-time failure is itself a finding)")
            blocking = True
            continue
        has_body = SENTINEL in rendered
        lines.append(f"  {label:12s}: {'ok' if has_body else 'BLOCKING'} "
                     f"({'argument value present' if has_body else 'EMPTY call, args dropped'})")
        blocking |= not has_body

    if blocking:
        lines.append("")
        lines.append("  -> add an `elif tool_call.arguments is string` branch after the mapping")
        lines.append("     branch; leave the mapping branch byte-identical. Avoid `fromjson`.")
    return (BLOCKING if blocking else OK), lines


def render_with(template_src, arguments):
    from jinja2 import Environment
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    tmpl = env.from_string(template_src)
    return tmpl.render(messages=replay_messages(arguments), tools=[TOOL],
                       add_generation_prompt=True)


def check_template(path):
    try:
        import jinja2  # noqa: F401
    except ImportError:
        print("need jinja2:  python3 -m pip install jinja2", file=sys.stderr)
        return UNREACHABLE
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as exc:
        print(f"cannot read template: {exc}", file=sys.stderr)
        return UNREACHABLE

    renders = {}
    for label, args in (("object args", ARGS_OBJ), ("string args", ARGS_STR)):
        try:
            renders[label] = render_with(src, args)
        except Exception:
            renders[label] = None

    code, lines = evaluate_renders(renders)
    print("\n".join(lines))
    return code


def _post(base_url, body, timeout):
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def check_live(base_url, model, timeout):
    inspected = 0
    blocking = False

    body = {"model": model,
            "messages": [{"role": "user", "content": f"What is the weather in {USER_CITY}?"}],
            "tools": [TOOL], "tool_choice": "auto", "max_tokens": 4096, "temperature": 0}
    try:
        d = _post(base_url, body, timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  endpoint unreachable: {exc}", file=sys.stderr)
        return UNREACHABLE

    inspected += 1
    msg = d["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    if calls:
        args = calls[0]["function"].get("arguments")
        empty = args in (None, "", "{}")
        print(f"  cold call   : {'BLOCKING' if empty else 'ok'} arguments={args!r}")
        blocking |= empty
    else:
        finish = d["choices"][0].get("finish_reason")
        print(f"  cold call   : BLOCKING no tool_calls; finish={finish!r}")
        print("                (prose describing a call is a finding, and so is")
        print("                 finish_reason=stop with no call: a dropped </think>)")
        blocking = True

    for label, args in (("replay obj ", ARGS_OBJ), ("replay str ", ARGS_STR)):
        body = {"model": model, "messages": replay_messages(args), "tools": [TOOL],
                "tool_choice": "auto", "max_tokens": 4096, "temperature": 0}
        try:
            d = _post(base_url, body, timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  {label}: endpoint unreachable: {exc}", file=sys.stderr)
            return UNREACHABLE
        inspected += 1
        ch = d["choices"][0]
        m = ch["message"]
        calls = m.get("tool_calls") or []
        content = (m.get("content") or "").strip()
        good = bool(calls) or bool(content)
        print(f"  {label}: {'ok' if good else 'BLOCKING'} tool_calls={len(calls)} "
              f"content_len={len(content)} finish={ch.get('finish_reason')!r}")
        blocking |= not good

    if not inspected:
        return NOTHING_INSPECTED
    if blocking:
        print("\n  -> if 'replay str' fails while 'replay obj' passes, it is the template")
        print("     dialect bug (trap 43), not the model.")
        return BLOCKING
    return OK


# ---------------------------------------------------------------- contract controls

_GOOD_TEMPLATE = """
{% for m in messages %}
{{ m.role }}: {{ m.content }}
{% if m.tool_calls %}{% for tc in m.tool_calls %}
<function={{ tc.function.name }}>
{% if tc.function.arguments is mapping %}
{% for k, v in tc.function.arguments.items() %}<parameter={{ k }}>{{ v }}</parameter>
{% endfor %}
{% elif tc.function.arguments is string and tc.function.arguments|trim %}
<parameter=arguments>{{ tc.function.arguments }}</parameter>
{% endif %}
</function>
{% endfor %}{% endif %}
{% endfor %}
"""

# The bug this check exists to catch: mapping branch only, no else.
_BUGGY_TEMPLATE = """
{% for m in messages %}
{{ m.role }}: {{ m.content }}
{% if m.tool_calls %}{% for tc in m.tool_calls %}
<function={{ tc.function.name }}>
{% if tc.function.arguments is mapping %}
{% for k, v in tc.function.arguments.items() %}<parameter={{ k }}>{{ v }}</parameter>
{% endfor %}
{% endif %}
</function>
{% endfor %}{% endif %}
{% endfor %}
"""


def _render_fixture(template_src):
    """Render both arms of a fixture template, mirroring check_template()."""
    out = {}
    for label, args in (("object args", ARGS_OBJ), ("string args", ARGS_STR)):
        try:
            out[label] = render_with(template_src, args)
        except Exception:
            out[label] = None
    return out


def _control_string_args_dropped():
    """The real bug: mapping-only guard drops string args. MUST report BLOCKING."""
    return evaluate_renders(_render_fixture(_BUGGY_TEMPLATE))[0]


def _control_renders_nothing():
    """A template that emits no tool call at all. MUST report BLOCKING."""
    return evaluate_renders({"object args": "user: hi", "string args": "user: hi"})[0]


def _control_sentinel_not_in_prompt():
    """Guards the unfalsifiable-assertion defect this check itself shipped with.

    If the sentinel ever appears in the conversation outside the tool arguments, the
    buggy template would pass. Render the buggy template and assert the sentinel is
    genuinely absent, i.e. that the assertion is still able to fail.
    """
    rendered = _render_fixture(_BUGGY_TEMPLATE)["string args"]
    if rendered is None:
        return BLOCKING
    return BLOCKING if SENTINEL not in rendered else OK


def _control_empty():
    """No template inspected. MUST NOT be a pass."""
    return evaluate_renders({})[0]


NEGATIVE_CONTROLS = [
    ("string args dropped by mapping-only guard", _control_string_args_dropped),
    ("template renders no tool call", _control_renders_nothing),
    ("sentinel absent from prompt, so the assertion can fail", _control_sentinel_not_in_prompt),
]
EMPTY_SET_CONTROL = ("no template rendered", _control_empty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", help="path to a Jinja chat template (offline mode)")
    ap.add_argument("--base-url", help="OpenAI-compatible base url ending in /v1 (live mode)")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()

    if a.template:
        return check_template(a.template)
    if a.base_url:
        if not a.model:
            ap.error("--model is required with --base-url")
        return check_live(a.base_url, a.model, a.timeout)
    ap.error("pass --template or --base-url")


if __name__ == "__main__":
    sys.exit(main())
