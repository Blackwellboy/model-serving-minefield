#!/usr/bin/env python3
"""A mock vLLM lane that renders prompts the way DeepSeek-V4.1-Flash does.

Follows the checkpoint's own Python encoder (encoding/README.md on
deepseek-ai/DeepSeek-V4.1-Flash), because three Doctor verdicts misread it:

  - every non-thinking assistant turn opens with a bare close tag,
    `<｜Assistant｜></think>answer`, which is the format, not an orphan (trap 02)
  - prior-turn reasoning is dropped from tool-less renders but KEPT once any
    tool is defined (drop_thinking is disabled with tools) (trap 04)
  - effort is a numeric budget written into the prompt as
    `Reasoning Effort: N`; 25, 50 and 100 are each one token, so prompt-token
    counts cannot see a change (traps 58 / 07)

Modes:
  `served`    the ladder measured on a live EXL3 vLLM build (2026-10-15):
              default 50, low 25, high 50, xhigh 75, max 100
  `reference` the encoder's ladder: default 75, low 50, high 75, max 100

No real endpoint is contacted.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL = "mock-deepseek-v4.1"
BOS, EOS = "<｜begin▁of▁sentence｜>", "<｜end▁of▁sentence｜>"
LADDERS = {
    "served": {None: 50, "low": 25, "high": 50, "xhigh": 75, "max": 100},
    "reference": {None: 75, "low": 50, "high": 75, "max": 100},
}


def effort_budget(mode, value):
    if isinstance(value, int):
        return value
    ladder = LADDERS[mode]
    if value not in ladder:
        raise ValueError(f"invalid reasoning effort {value!r}")
    return ladder[value]


def render_prompt(mode, messages, kwargs, tools=None):
    kwargs = kwargs or {}
    thinking = kwargs.get("enable_thinking", True)
    drop_thinking = not tools
    out = [BOS]
    if thinking:
        budget = effort_budget(mode, kwargs.get("reasoning_effort"))
        out.append(f"<｜System｜>Reasoning Effort: {budget} (range 1-100, the higher "
                   "the value, the more thorough the reasoning)\n\n")
    if tools:
        out.append("## Tools\n" + json.dumps(tools) + "\n")
    last_user = max((i for i, m in enumerate(messages) if m.get("role") == "user"),
                    default=-1)
    for i, m in enumerate(messages):
        role, content = m.get("role"), m.get("content") or ""
        if role == "system":
            out.append(content)
        elif role == "user":
            out.append(f"<｜User｜>{content}")
        elif role == "assistant":
            trace = m.get("reasoning_content") or m.get("reasoning") or ""
            keep = thinking and trace and (not drop_thinking or i > last_user)
            if keep:
                out.append(f"<｜Assistant｜><think>{trace}</think>{content}{EOS}")
            else:
                out.append(f"<｜Assistant｜></think>{content}{EOS}")
    out.append("<｜Assistant｜>" + ("<think>" if thinking else "</think>"))
    return "".join(out)


def make_handler(mode):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/v1/models":
                return self._send(200, {"data": [{"id": MODEL}]})
            if self.path == "/version":
                return self._send(200, {"version": "0.20.0"})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                body = {}
            msgs = body.get("messages") or []
            kw = dict(body.get("chat_template_kwargs") or {})
            if "reasoning_effort" in body and "reasoning_effort" not in kw:
                kw["reasoning_effort"] = body["reasoning_effort"]
            try:
                prompt = render_prompt(mode, msgs, kw, body.get("tools"))
            except ValueError as e:
                return self._send(400, {"error": {"message": str(e)}})
            if self.path == "/tokenize":
                return self._send(200, {"count": len(prompt), "token_strs": list(prompt)})
            if self.path == "/v1/chat/completions":
                thinking = kw.get("enable_thinking", True)
                msg = {"role": "assistant", "content": "OK", "tool_calls": [],
                       "reasoning": "brief trace" if thinking else None}
                # a budget number is one token whatever its value
                usage = {"prompt_tokens": 35, "completion_tokens": 2, "total_tokens": 37}
                return self._send(200, {
                    "id": "chatcmpl-mock", "model": MODEL, "usage": usage,
                    "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}]})
            return self._send(404, {"error": "not found"})

    return H


class MockLane:
    def __init__(self, mode="served"):
        self.httpd = HTTPServer(("127.0.0.1", 0), make_handler(mode))
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
