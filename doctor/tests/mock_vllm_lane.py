#!/usr/bin/env python3
"""A mock OpenAI-compatible lane that behaves like the Nemotron 3 family on vLLM.

Written so the doctor's new code paths can be tested with no hardware and no
contact with any real lane. It deliberately reproduces the defects the family
actually has, so a passing test means the doctor detects them, not merely that
it runs.

Reproduced on purpose:
  - vLLM shape: no /props, /version answers, render route returns token ids
  - history reasoning stripped by default, gated by truncate_history_thinking
  - the write field is `reasoning`; `reasoning_content` is dropped
  - multimodal content-part ORDER is discarded, adjacent text parts glued
  - a missing local media path returns 500
  - prompt_tokens_details is null on every response

Modes (constructor flag): `broken` (all of the above) or `clean` (a lane that
preserves order, resolves media errors as 400, and populates usage details), so
the tests can assert both directions.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL = "mock-nemotron-3"


def render_prompt(messages, kwargs, discard_order=True):
    kwargs = kwargs or {}
    thinking = kwargs.get("enable_thinking", True)
    truncate = kwargs.get("truncate_history_thinking", True)
    # every prompt carries an empty system turn, like the real template
    out = ["<|im_start|>system\n<|im_end|>\n"]
    last_user = max((i for i, m in enumerate(messages)
                     if m.get("role") == "user"), default=-1)
    for i, m in enumerate(messages):
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, list):
            media = [p for p in content if p.get("type") != "text"]
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            if discard_order:
                # placeholders first, then every text part glued together
                content = ("<image>\n" * len(media)) + "".join(texts)
            else:
                content = "".join(
                    ("<image>\n" if p.get("type") != "text" else p.get("text", ""))
                    for p in content)
        content = content or ""
        if role == "assistant":
            # the template reads reasoning_content out of the rendered context;
            # the SERVER maps its own `reasoning` field into that slot and drops
            # an unrecognised `reasoning_content` from the request
            trace = m.get("reasoning") or ""
            if truncate and i < last_user:
                out.append(f"<|im_start|>assistant\n<think></think>\n{content}<|im_end|>\n")
            elif trace:
                out.append(f"<|im_start|>assistant\n<think>\n{trace}\n</think>\n{content}<|im_end|>\n")
            else:
                out.append(f"<|im_start|>assistant\n<think></think>\n{content}<|im_end|>\n")
        else:
            out.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    out.append("<|im_start|>assistant\n" + ("<think>\n" if thinking else "<think></think>"))
    return "".join(out)


def make_handler(mode):
    broken = (mode == "broken")

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
            path = self.path
            msgs = body.get("messages") or []
            kw = body.get("chat_template_kwargs") or {}

            if path == "/v1/chat/completions/render":
                p = render_prompt(msgs, kw, discard_order=broken)
                return self._send(200, {"token_ids": [ord(c) for c in p]})
            if path == "/detokenize":
                toks = body.get("tokens") or []
                return self._send(200, {"prompt": "".join(chr(t) for t in toks)})
            if path == "/tokenize":
                p = render_prompt(msgs, kw, discard_order=broken)
                return self._send(200, {"count": len(p), "token_strs": list(p)})

            if path == "/v1/chat/completions":
                # media handling
                for m in msgs:
                    c = m.get("content")
                    if isinstance(c, list):
                        for part in c:
                            url = (part.get("image_url") or {}).get("url", "")
                            if url.startswith("file://"):
                                if broken:
                                    return self._send(500, {"error": {
                                        "message": "[Errno 2] No such file or directory"}})
                                return self._send(400, {"error": {
                                    "message": "Failed to load image: no such file"}})
                thinking = kw.get("enable_thinking", True)
                msg = {"role": "assistant", "content": "OK",
                       "tool_calls": [], "reasoning": "brief trace" if thinking else None}
                usage = {"prompt_tokens": 40, "completion_tokens": 2, "total_tokens": 42,
                         "prompt_tokens_details": None if broken else {"image_tokens": 256}}
                return self._send(200, {
                    "id": "chatcmpl-mock", "model": MODEL, "usage": usage,
                    "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}]})
            return self._send(404, {"error": "not found"})

    return H


class MockLane:
    def __init__(self, mode="broken"):
        self.httpd = HTTPServer(("127.0.0.1", 0), make_handler(mode))
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    with MockLane("broken") as base:
        print("mock lane at", base)
        import time
        time.sleep(3600)
