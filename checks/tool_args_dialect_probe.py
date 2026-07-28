#!/usr/bin/env python3
"""Trap 43 check, does the chat template survive tool-call `arguments` arriving as a STRING?

The OpenAI spec says `arguments` is a string. Templates that gate parameter expansion on
`arguments is mapping` with no `else` render an EMPTY tool call when a framework replays a
prior call with pre-serialized JSON. The model then loops on its own malformed call.

Two modes:

  --template PATH   offline: render the Jinja template both ways, diff the parameter body.
                    Requires `jinja2`.
  --base-url URL    live: send a real `tools` array to an OpenAI-compatible endpoint and
                    assert structured tool_calls come back, then replay the call with
                    string-valued arguments and assert the model still behaves.

Exit code 0 = pass, 1 = fail, 2 = could not run the check.

Usage:
  python3 tool_args_dialect_probe.py --template ./chat_template.jinja
  python3 tool_args_dialect_probe.py --base-url http://127.0.0.1:8080/v1 --model my-model
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

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
ARGS_OBJ = {"city": "Paris"}
ARGS_STR = json.dumps(ARGS_OBJ)


def _msgs(arguments):
    """A conversation that REPLAYS an assistant tool call, the shape that triggers the bug."""
    return [
        {"role": "user", "content": "What is the weather in Paris?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": arguments},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "18C, clear"},
        {"role": "user", "content": "And in Berlin?"},
    ]


def check_template(path):
    try:
        from jinja2 import Environment
    except ImportError:
        print("need jinja2:  python3 -m pip install jinja2", file=sys.stderr)
        return 2

    src = open(path, encoding="utf-8").read()
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
    tmpl = env.from_string(src)

    out = {}
    for label, args in (("object args", ARGS_OBJ), ("string args", ARGS_STR)):
        try:
            out[label] = tmpl.render(
                messages=_msgs(args), tools=[TOOL], add_generation_prompt=True
            )
        except Exception as exc:  # a render-time failure is itself a finding
            print(f"  {label:12s}: RENDER ERROR {type(exc).__name__}: {exc}")
            out[label] = None

    ok = True
    for label in ("object args", "string args"):
        rendered = out[label]
        if rendered is None:
            ok = False
            continue
        # Heuristic that works across dialects: the serialized call must carry the value
        # "Paris" somewhere after the function name, not just the bare function name.
        has_body = "Paris" in rendered
        print(f"  {label:12s}: {'PASS' if has_body else 'FAIL'} "
              f"({'parameter body present' if has_body else 'EMPTY call, args dropped'})")
        ok &= has_body

    if not ok:
        print("\n  -> add an `elif tool_call.arguments is string` branch after the mapping "
              "branch; leave the mapping branch byte-identical. Avoid `fromjson`.")
    return 0 if ok else 1


def _post(base_url, body, timeout=180):
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def check_live(base_url, model, timeout):
    ok = True

    # 1. cold call: does a real tools array produce STRUCTURED tool_calls?
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "What is the weather in Paris?"}],
        "tools": [TOOL],
        "tool_choice": "auto",
        "max_tokens": 4096,
        "temperature": 0,
    }
    try:
        d = _post(base_url, body, timeout)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  cold call   : ERROR {exc}", file=sys.stderr)
        return 2

    msg = d["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    if calls:
        fn = calls[0]["function"]
        args = fn.get("arguments")
        empty = args in (None, "", "{}")
        print(f"  cold call   : {'FAIL' if empty else 'PASS'} "
              f"tool_calls=1 name={fn.get('name')!r} arguments={args!r}")
        ok &= not empty
    else:
        print(f"  cold call   : FAIL no tool_calls; finish={d['choices'][0].get('finish_reason')!r} "
              f"content={(msg.get('content') or '')[:80]!r}")
        print("                (prose describing a call is a FAIL, so is finish_reason=stop "
              "with no call, which can also mean a dropped </think>)")
        ok = False

    # 2. replay with STRING arguments, the actual trap
    for label, args in (("replay obj ", ARGS_OBJ), ("replay str ", ARGS_STR)):
        body = {
            "model": model,
            "messages": _msgs(args),
            "tools": [TOOL],
            "tool_choice": "auto",
            "max_tokens": 4096,
            "temperature": 0,
        }
        try:
            d = _post(base_url, body, timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  {label}: ERROR {exc}")
            ok = False
            continue
        ch = d["choices"][0]
        m = ch["message"]
        calls = m.get("tool_calls") or []
        content = (m.get("content") or "").strip()
        good = bool(calls) or bool(content)
        detail = f"tool_calls={len(calls)} content_len={len(content)} finish={ch.get('finish_reason')!r}"
        print(f"  {label}: {'PASS' if good else 'FAIL'} {detail}")
        ok &= good

    if not ok:
        print("\n  -> if 'replay str' fails while 'replay obj' passes, it is the template "
              "dialect bug (Trap 43), not the model.")
    return 0 if ok else 1


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
