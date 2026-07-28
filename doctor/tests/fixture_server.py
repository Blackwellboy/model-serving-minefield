#!/usr/bin/env python3
"""A configurable fixture lane, plus a fixture huggingface hub.

The doctor's job is to be honest about what it does and does not know, and the
only way to keep it honest is to assert on its verdicts against servers whose
behaviour we control exactly. Every scenario here exists because a real lane
behaved this way, or because the doctor once emitted a CLEAN for it that it had
not earned.

Nothing here contacts a network. Both servers bind 127.0.0.1 on an ephemeral
port and are torn down by the context manager.

Scenario flags (all default to the well-behaved value):

  props                 dict or None. A dict makes this a llama.cpp-shaped lane
                        that publishes /props including a chat template, which
                        is the ONLY way the doctor can turn kwarg acceptance
                        into a verdict.
  reasoning_field       "reasoning_content" | "reasoning" | None. None means
                        the lane never returns a reasoning trace at all: the
                        silence the doctor must not call clean.
  thinking_effective    bool. False reproduces an accepted-and-ignored
                        enable_thinking kwarg: every arm looks identical.
  tool_choice_supported bool. False returns 400 on tool_choice, removing the
                        deterministic control and forcing INCONCLUSIVE.
  tool_calls            "always" | "forced_only" | "never".
  tool_markup           bool. Emit raw <tool_call> text instead of a parsed
                        array.
  render                bool. Whether the vLLM render/detokenize routes answer.
  preserve_history      bool. Whether prior-turn reasoning survives assembly.
  kwarg_rejection       None | "unknown" | "known". "unknown" rejects any
                        unrecognised chat_template_kwarg (the loud, safe lane);
                        "known" rejects reasoning_effort while silently
                        accepting invented names, which is the case that must
                        NOT be credited as a strict server.
  accepts_images        bool.
  image_reject_names_modality  bool.
  ceiling               "content" | "empty_at_cap" | "empty_not_at_cap".
  stream_channel        "content" | "reasoning" | None.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "fixture-lane"

# A minimal chat template. Whether it mentions reasoning_effort is what decides
# the trap 07 verdict, so the two variants are spelled out rather than built.
TEMPLATE_WITHOUT_EFFORT = (
    "{% for message in messages %}<|im_start|>{{ message.role }}\n"
    "{{ message.content }}<|im_end|>\n{% endfor %}"
    "{% if enable_thinking %}<|im_start|>assistant\n<think>\n{% endif %}")
TEMPLATE_WITH_EFFORT = (
    "{% set reasoning_effort = reasoning_effort if reasoning_effort is defined "
    "else 'medium' %}" + TEMPLATE_WITHOUT_EFFORT)

DEFAULTS = {
    "props": None,
    "reasoning_field": "reasoning_content",
    "thinking_effective": True,
    "tool_choice_supported": True,
    "tool_calls": "always",
    "tool_markup": False,
    "render": True,
    "preserve_history": True,
    "kwarg_rejection": None,
    "accepts_images": True,
    "image_reject_names_modality": True,
    "bad_media_status": 400,
    "usage_details": {"image_tokens": 256},
    "ceiling": "content",
    "stream_channel": "content",
}


def llamacpp_props(template=TEMPLATE_WITHOUT_EFFORT, temperature=0.6, top_p=0.95):
    return {"build_info": "fixture-b0000",
            "chat_template": template,
            "default_generation_settings": {
                "params": {"temperature": temperature, "top_p": top_p}}}


def render_prompt(cfg, messages, kwargs):
    kwargs = kwargs or {}
    thinking = kwargs.get("enable_thinking", True)
    preserve = cfg["preserve_history"] or kwargs.get("preserve_thinking") is True
    out = []
    field = cfg["reasoning_field"] or "reasoning_content"
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if isinstance(content, list):
            content = "".join(
                (p.get("text", "") if p.get("type") == "text" else "<image>\n")
                for p in content)
        content = content or ""
        if role == "assistant":
            trace = m.get(field) or ""
            if not trace:
                # a well-behaved template emits no wrapper when there is
                # nothing to wrap; emitting one is trap 25
                out.append(f"<|im_start|>assistant\n{content}<|im_end|>\n")
            elif preserve:
                out.append(f"<|im_start|>assistant\n<think>\n{trace}\n</think>\n"
                           f"{content}<|im_end|>\n")
            else:
                out.append(f"<|im_start|>assistant\n<think></think>\n"
                           f"{content}<|im_end|>\n")
        else:
            out.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    out.append("<|im_start|>assistant\n" + ("<think>\n" if thinking else ""))
    return "".join(out)


def _make_lane_handler(cfg):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

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
            if self.path == "/props":
                if cfg["props"]:
                    return self._send(200, cfg["props"])
                return self._send(404, {"error": "not found"})
            if self.path == "/version":
                if cfg["props"]:
                    return self._send(404, {"error": "not found"})
                return self._send(200, {"version": "0.25.0"})
            return self._send(404, {"error": "not found"})

        # -- generation -----------------------------------------------------
        def _message(self, body):
            kw = body.get("chat_template_kwargs") or {}
            want_think = kw.get("enable_thinking", True)
            fires = cfg["thinking_effective"] and want_think and cfg["reasoning_field"]
            msg = {"role": "assistant", "content": "OK"}
            if fires:
                msg[cfg["reasoning_field"]] = "a brief trace"

            if body.get("tools"):
                forced = body.get("tool_choice") not in (None, "none", "auto")
                mode = cfg["tool_calls"]
                emit = (mode == "always") or (mode == "forced_only" and forced)
                if emit and not cfg["tool_markup"]:
                    msg["tool_calls"] = [{"id": "call_0", "type": "function",
                                          "function": {"name": "get_time",
                                                       "arguments": '{"timezone":"Asia/Tokyo"}'}}]
                    msg["content"] = None
                elif emit and cfg["tool_markup"]:
                    msg["content"] = ('<tool_call>{"name": "get_time", '
                                      '"arguments": {"timezone": "Asia/Tokyo"}}</tool_call>')
                else:
                    msg["content"] = "It is currently daytime in Tokyo."
            return msg

        def _ceiling_message(self):
            mode = cfg["ceiling"]
            if mode == "empty_at_cap":
                return ({"role": "assistant", "content": "",
                         cfg["reasoning_field"] or "reasoning_content":
                             "\n".join(f"step {i}: consider the grammar" for i in range(60))},
                        "length")
            if mode == "empty_not_at_cap":
                return ({"role": "assistant", "content": "",
                         cfg["reasoning_field"] or "reasoning_content": "short trace"},
                        "stop")
            return ({"role": "assistant", "content": "def parse(s):\n    ...\n"},
                    "stop")

        def _stream(self, body):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            ch = cfg["stream_channel"]
            if ch:
                for piece in ("Os", "lo"):
                    chunk = {"choices": [{"index": 0, "delta": {ch: piece}}]}
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                body = {}
            path, msgs = self.path, body.get("messages") or []
            kw = body.get("chat_template_kwargs") or {}

            if path in ("/v1/chat/completions/render", "/tokenize"):
                if not cfg["render"]:
                    return self._send(404, {"error": "not found"})
                p = render_prompt(cfg, msgs, kw)
                if path == "/tokenize":
                    return self._send(200, {"count": len(p), "token_strs": list(p)})
                return self._send(200, {"token_ids": [ord(c) for c in p]})
            if path == "/detokenize":
                if not cfg["render"]:
                    return self._send(404, {"error": "not found"})
                return self._send(200, {"prompt": "".join(
                    chr(t) for t in (body.get("tokens") or []))})
            if path == "/apply-template":
                if not (cfg["render"] and cfg["props"]):
                    return self._send(404, {"error": "not found"})
                return self._send(200, {"prompt": render_prompt(cfg, msgs, kw)})

            if path != "/v1/chat/completions":
                return self._send(404, {"error": "not found"})

            # kwarg strictness
            rej = cfg["kwarg_rejection"]
            known = {"enable_thinking", "preserve_thinking",
                     "truncate_history_thinking", "keep_thinking",
                     "include_reasoning"}
            if rej == "unknown" and any(k not in known for k in kw):
                return self._send(400, {"error": {
                    "message": "unrecognised chat template kwarg"}})
            if rej == "known" and "reasoning_effort" in kw:
                return self._send(400, {"error": {
                    "message": "reasoning_effort is not accepted on this model"}})

            if body.get("tool_choice") not in (None, "none", "auto") \
                    and not cfg["tool_choice_supported"]:
                return self._send(400, {"error": {
                    "message": "tool_choice is not supported by this server"}})

            # media handling
            has_image = False
            for m in msgs:
                c = m.get("content")
                if isinstance(c, list):
                    for part in c:
                        if part.get("type") == "text":
                            continue
                        has_image = True
                        url = (part.get("image_url") or {}).get("url", "")
                        if url.startswith("file://"):
                            return self._send(cfg["bad_media_status"], {"error": {
                                "message": "could not load media"}})
            if has_image and not cfg["accepts_images"]:
                msg = ("this model does not support image input"
                       if cfg["image_reject_names_modality"]
                       else "invalid request payload")
                return self._send(400, {"error": {"message": msg}})

            if body.get("stream"):
                return self._stream(body)

            if body.get("max_tokens") == 512 and not body.get("tools"):
                msg, finish = self._ceiling_message()
            else:
                msg, finish = self._message(body), "stop"

            usage = {"prompt_tokens": 40, "completion_tokens": 2,
                     "total_tokens": 42}
            if has_image:
                usage["prompt_tokens_details"] = cfg["usage_details"]
            return self._send(200, {"id": "chatcmpl-fixture", "model": MODEL,
                                    "usage": usage,
                                    "choices": [{"index": 0, "message": msg,
                                                 "finish_reason": finish}]})
    return H


class FixtureLane:
    """A lane whose every behaviour is declared, so a verdict can be asserted."""

    def __init__(self, **overrides):
        cfg = dict(DEFAULTS)
        unknown = set(overrides) - set(DEFAULTS)
        if unknown:
            raise TypeError(f"unknown fixture flags: {sorted(unknown)}")
        cfg.update(overrides)
        self.cfg = cfg
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_lane_handler(cfg))
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


# ------------------------------------------------------------ fixture hub

def _make_hub_handler(repos):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *a):
            pass

        def _send(self, code, payload, raw=False):
            body = payload.encode() if raw else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parts = [p for p in self.path.split("/") if p]
            # /api/models/<org>/<name>/revision/<rev>
            if parts[:2] == ["api", "models"] and "revision" in parts:
                i = parts.index("revision")
                repo = "/".join(parts[2:i])
                rev = "/".join(parts[i + 1:])
                spec = repos.get(repo)
                if not spec or rev not in spec["revisions"]:
                    return self._send(404, {"error": "revision not found"})
                return self._send(200, {"sha": spec["revisions"][rev]["sha"]})
            # /<org>/<name>/resolve/<ref>/<file>
            if "resolve" in parts:
                i = parts.index("resolve")
                repo = "/".join(parts[:i])
                ref = parts[i + 1]
                fname = "/".join(parts[i + 2:])
                spec = repos.get(repo)
                if not spec:
                    return self._send(404, {"error": "no repo"})
                by_sha = {r["sha"]: r for r in spec["revisions"].values()}
                rev = by_sha.get(ref) or spec["revisions"].get(ref)
                if rev is None or fname not in rev["files"]:
                    return self._send(404, {"error": "not found"})
                return self._send(200, rev["files"][fname])
            return self._send(404, {"error": "not found"})
    return H


class FixtureHub:
    """A stand-in for huggingface.co.

    `repos` maps "org/name" to {"revisions": {ref: {"sha": ..., "files": {...}}}}.
    The same sha may be reachable under several refs, which is exactly how a
    pinned revision and a moving `main` coexist.
    """

    def __init__(self, repos):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_hub_handler(repos))
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
