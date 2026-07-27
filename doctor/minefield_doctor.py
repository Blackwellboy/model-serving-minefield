#!/usr/bin/env python3
"""minefield_doctor.py: point it at your OpenAI-compatible endpoint, get a
diagnosis against the model-serving-minefield registry.

    python3 minefield_doctor.py --base-url http://localhost:8000/v1

Safety, up front:
  - READ-ONLY. Never restarts anything, never changes server state, never
    writes to your server. GET probes plus a small, fixed set of chat
    completions (at most 8 generation requests, each capped at 512 output
    tokens; one uses 512, the rest 64 to 256).
  - Sends nothing anywhere except your endpoint (and huggingface.co, only
    if you pass --hf-repo, to read two public config files).
  - Everything it finds cites the registry trap it comes from.

Output: PROBLEMS / CHECKED AND CLEAN / COULD NOT CHECK. Add --report for a
markdown block you can paste into an "I hit a trap" issue.

Stdlib only. jinja2 is used for one extra render path if installed; never
required. Exit codes: 0 ran (read the sections), 1 endpoint unreachable.
"""
import argparse, json, re, sys, urllib.request, urllib.error, zlib

REG = "https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps"
TRAP_PATHS = {
    "01": "reasoning/01-reasoning-field-two-names.md",
    "02": "template/02-orphaned-think-close-tag.md",
    "03": "reasoning/03-enable-thinking-default-drift.md",
    "04": "template/04-history-reasoning-stripping.md",
    "07": "reasoning/07-reasoning-effort-silently-ignored.md",
    "10": "quantization/10-quant-label-is-not-the-kernel-path.md",
    "12": "evaluation/12-empty-content-at-token-ceiling.md",
    "16": "evaluation/16-finish-reason-is-not-a-failure-signal.md",
    "17": "evaluation/17-per-arm-recommended-sampling-confound.md",
    "19": "tools/19-missing-jinja-breaks-tool-parsing.md",
    "20": "reasoning/20-reasoning-write-field-name-diverges.md",
    "21": "versioning/21-no-generation-config-server-defaults-win.md",
    "22": "evaluation/22-family-card-budget-floors-differ-by-size.md",
    "23": "reasoning/23-streaming-answer-lands-in-reasoning-channel.md",
    "25": "template/25-empty-think-blocks-poison-prefix-cache.md",
    "26": "tools/26-tool-call-inside-unclosed-think.md",
    "29": "reasoning/29-server-reasoning-off-is-not-an-off-switch.md",
}
def trap(n): return f"{REG}/{TRAP_PATHS[n]}"

RMARK = "ZQXMARK_REASONING_7734"
TOOLS = [{"type": "function", "function": {
    "name": "get_time", "description": "Get current time in a timezone",
    "parameters": {"type": "object",
                   "properties": {"timezone": {"type": "string"}},
                   "required": ["timezone"]}}}]

# ------------------------------------------------------------- transport

def _req(url, key=None, data=None, timeout=60):
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)

def get(url, key=None, timeout=15):
    return _req(url, key, None, timeout)

def post(url, body, key=None, timeout=180):
    return _req(url, key, json.dumps(body).encode(), timeout)

# ------------------------------------------------------------ diagnosis state

class Doc:
    def __init__(self):
        self.problems, self.clean, self.blocked = [], [], []
        self.requests_made = 0
        self.stack, self.model, self.build = "unknown", None, None
        self.evidence = {}
    def problem(self, traps, title, fix):
        self.problems.append((traps, title, fix))
    def ok(self, traps, title):
        self.clean.append((traps, title))
    def skip(self, traps, title, why):
        self.blocked.append((traps, title, why))

def chat(doc, base, key, model, messages, **kw):
    body = {"model": model or "default", "messages": messages,
            "temperature": 0, "max_tokens": kw.pop("max_tokens", 128)}
    body.update(kw)
    doc.requests_made += 1
    st, txt = post(base + "/chat/completions", body, key)
    if st != 200:
        return st, None, txt
    try:
        d = json.loads(txt)
        return st, d["choices"][0], d
    except Exception as e:
        return st, None, f"unparseable: {e}"

def msg_fields(choice):
    m = choice["message"]
    return (m.get("content") or "", m.get("reasoning_content") or "",
            m.get("reasoning") or "", m.get("tool_calls") or [], m)

# ------------------------------------------------------------------ checks

def detect_stack(doc, base, root, key):
    st, txt = get(base + "/models", key)
    if st != 200:
        return False
    try:
        doc.model = json.loads(txt)["data"][0]["id"]
    except Exception:
        pass
    st, txt = get(root + "/props", key, timeout=8)
    if st == 200:
        doc.stack = "llama.cpp"
        try:
            props = json.loads(txt)
            doc.evidence["props"] = props
            doc.build = (props.get("build_info") or "")[:40]
        except Exception:
            pass
    else:
        # mlx server and vLLM both lack /props; tell them apart cheaply
        st2, _ = get(root + "/version", key, timeout=8)
        doc.stack = "vllm" if st2 == 200 else "openai-compatible (vLLM/MLX/other)"
    return True

def check_reasoning_fields(doc, base, key):
    """Traps 01 (read side), 02 (orphan close), 03 (toggle map), 29 (override)."""
    arms = {}
    for name, kwargs in (("on", {"enable_thinking": True}),
                         ("off", {"enable_thinking": False}),
                         ("absent", None)):
        body_kw = {"chat_template_kwargs": kwargs} if kwargs is not None else {}
        st, choice, raw = chat(doc, base, key, doc.model,
                               [{"role": "user", "content":
                                 "Which is larger, 17*24 or 400? Answer briefly."}],
                               max_tokens=256, **body_kw)
        if st != 200 or choice is None:
            arms[name] = {"error": f"http {st}"}
            continue
        c, rc, rr, _tc, m = msg_fields(choice)
        arms[name] = {
            "content_len": len(c),
            "reasoning_content": len(rc), "reasoning": len(rr),
            "think_in_content": "<think>" in c or "</think>" in c,
            "stray_close": c.lstrip().startswith("</think>"),
            "keys": sorted(m.keys()), "finish": choice.get("finish_reason")}
    doc.evidence["toggle_arms"] = arms
    if all("error" in a for a in arms.values()):
        doc.skip(["01", "03"], "reasoning field and thinking-toggle checks",
                 f"all probe requests failed ({arms['on'].get('error')})")
        return

    on = arms.get("on", {})
    fields = [k for k in ("reasoning_content", "reasoning") if on.get(k)]
    if fields:
        doc.ok(["01"], f"reasoning exposed under {' and '.join(fields)} "
               f"(read that exact name; the other name may not exist here)")
    elif on.get("think_in_content"):
        doc.problem(["01"], "reasoning arrives as <think> tags inside content, "
                    "not as a separate field: any harness reading only a "
                    "reasoning field scores this lane as never thinking",
                    "parse think tags from content on this lane, or enable the "
                    "server's reasoning parser")
    elif "error" not in on:
        doc.ok(["01"], "no reasoning field or think tags with thinking on "
               "(either a non-thinking model or thinking fully disabled server-side)")

    for name, a in arms.items():
        if a.get("stray_close"):
            doc.problem(["02"], f"response content starts with a stray </think> "
                        f"({name} arm): parser strips the open tag but not the close",
                        "fix the reasoning-parser pairing; strip the orphan before "
                        "scoring anything")
            break
    else:
        doc.ok(["02"], "no orphaned </think> at the start of any probe response")

    def fired(a): return bool(a.get("reasoning_content") or a.get("reasoning")
                              or a.get("think_in_content"))
    if "error" not in arms.get("absent", {"error": 1}) and \
       "error" not in on and "error" not in arms.get("off", {"error": 1}):
        landing = "on-like" if fired(arms["absent"]) == fired(on) and fired(on) else \
                  ("off-like" if fired(arms["absent"]) == fired(arms["off"]) else "distinct")
        doc.ok(["03"], f"thinking toggle map: explicit-on fired={fired(on)}, "
               f"explicit-off fired={fired(arms['off'])}, absent lands {landing}. "
               f"Send the kwarg explicitly; absent is revision- and server-dependent")
        if fired(on) and not fired(arms["absent"]):
            doc.problem(["29"], "server-side default has thinking off, but a "
                        "client kwarg re-enables it per request: the flag is a "
                        "default, not a gate, and thinking requests can blow "
                        "non-thinking token budgets",
                        "strip or deny thinking kwargs at your gateway, or size "
                        "max_tokens for the thinking distribution")

def check_streaming(doc, base, key):
    """Trap 23: streamed answer must land in content."""
    body = {"model": doc.model or "default",
            "messages": [{"role": "user", "content": "Capital of Norway? One word."}],
            "stream": True, "max_tokens": 64, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}}
    doc.requests_made += 1
    try:
        req = urllib.request.Request(base + "/chat/completions",
                                     json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        keys = {}
        with urllib.request.urlopen(req, timeout=120) as r:
            for line in r:
                line = line.decode("utf-8", "replace").strip()
                if not line.startswith("data: {"):
                    continue
                delta = json.loads(line[6:])["choices"][0].get("delta", {})
                for k, v in delta.items():
                    if v:
                        keys[k] = keys.get(k, 0) + 1
        doc.evidence["stream_delta_keys"] = keys
        if keys.get("content"):
            doc.ok(["23"], f"streamed answer arrives in content deltas ({keys})")
        elif keys.get("reasoning") or keys.get("reasoning_content"):
            doc.problem(["23"], f"streamed answer arrives ONLY in reasoning deltas "
                        f"with thinking off ({keys}): clients that concatenate "
                        f"content see blank replies",
                        "upgrade the engine (vLLM: past PR #40820) or read "
                        "reasoning deltas as a fallback channel")
        else:
            doc.skip(["23"], "streaming delta placement", "no non-empty deltas seen")
    except Exception as e:
        doc.skip(["23"], "streaming delta placement", f"stream failed: {e}")

def render_paths(doc, root, key, messages, kwargs):
    """Return (prompt, how) via llama.cpp /apply-template, else local jinja2."""
    if doc.stack == "llama.cpp":
        body = {"messages": messages}
        if kwargs:
            body["chat_template_kwargs"] = kwargs
        st, txt = post(root + "/apply-template", body, key, timeout=30)
        if st == 200:
            try:
                return json.loads(txt).get("prompt", ""), "server /apply-template"
            except Exception:
                pass
    tpl = (doc.evidence.get("props") or {}).get("chat_template")
    if tpl:
        try:
            from jinja2 import Environment, BaseLoader
            env = Environment(loader=BaseLoader())
            env.globals["raise_exception"] = lambda m: ""
            env.globals["strftime_now"] = lambda fmt: ""
            return env.from_string(tpl).render(
                messages=messages, add_generation_prompt=True,
                bos_token="", eos_token="", **(kwargs or {})), "local jinja2"
        except Exception:
            pass
    return None, None

def check_history_assembly(doc, root, key):
    """Traps 04 (stripping), 25 (empty shells), 20 (write field), 02 (tag balance)."""
    def msgs(field):
        turns = [{"role": "system", "content": "You are a coding agent."}]
        for i in (1, 2):
            turns.append({"role": "user", "content": f"Step {i}: what next?"})
            a = {"role": "assistant", "content": f"Doing step {i}."}
            if field:
                a[field] = f"{RMARK} thinking about step {i}."
            turns.append(a)
        turns.append({"role": "user", "content": "Step 3: what next?"})
        return turns

    base_render, how = render_paths(doc, root, key, msgs(None), {"enable_thinking": True})
    if base_render is None:
        doc.skip(["04", "25", "20"], "assembled-prompt inspection at turn 3",
                 "no render path on this stack (needs llama.cpp /apply-template "
                 "or a readable template plus jinja2); run the registry's "
                 "checks/preflight_template.py with --template-file instead")
        return
    empty_pairs = len(re.findall(r"<think>\s*</think>", base_render))
    if empty_pairs:
        doc.problem(["04", "25"], f"history renders {empty_pairs} empty think "
                    f"block(s) for prior turns (via {how}): multi-turn thinking "
                    f"collapse reads as a model property, and equivalent "
                    f"histories cache-miss",
                    "resend prior reasoning under the field this runtime reads, "
                    "or use a template that skips empty wrappers")
    else:
        doc.ok(["04", "25"], f"no empty think shells in the turn-3 render (via {how})")

    hits = {}
    for field in ("reasoning_content", "reasoning"):
        r, _ = render_paths(doc, root, key, msgs(field), {"enable_thinking": True})
        hits[field] = (r is not None and RMARK in r)
    doc.evidence["write_field_hits"] = hits
    live = [f for f, h in hits.items() if h]
    if live:
        doc.ok(["20", "04"], f"prior-turn reasoning survives history when resent "
               f"as {' and '.join(live)}; dead write name(s): "
               f"{[f for f, h in hits.items() if not h] or 'none'}. Use the live name")
        if len(live) == 1:
            doc.ok(["20"], f"write field on this runtime is {live[0]} only: "
                   f"porting a fix that resends the other name silently does nothing")
    else:
        r, _ = render_paths(doc, root, key, msgs("reasoning_content"),
                            {"enable_thinking": True, "preserve_thinking": True})
        if r is not None and RMARK in r:
            doc.problem(["04"], "history reasoning is stripped by DEFAULT; the "
                        "preserve_thinking kwarg flips it to preserved. Every "
                        "client that does not set it runs the stripped arm",
                        "set preserve_thinking (and resend reasoning_content) on "
                        "every multi-turn call; record it beside your numbers")
        else:
            doc.problem(["04", "20"], "resent prior reasoning under BOTH field "
                        "names (and with preserve_thinking) never reaches the "
                        "assembled prompt: this lane strips history reasoning "
                        "with no working preservation path found",
                        "multi-turn thinking measurements on this lane describe "
                        "a model that cannot see its own prior reasoning; fix "
                        "the template before trusting them")

    o, c = base_render.count("<think>"), base_render.count("</think>")
    if c > o:
        doc.problem(["02"], f"assembled prompt has {c} </think> vs {o} <think>: "
                    "orphaned close tags in history", "fix template or history assembly")

def check_kwarg_deadness(doc, base, root, key):
    """Trap 07: accepted-but-unread kwargs."""
    st, choice, _ = chat(doc, base, key, doc.model,
                         [{"role": "user", "content": "Say OK."}],
                         max_tokens=16,
                         chat_template_kwargs={"bogus_kwarg_zzq": True,
                                               "reasoning_effort": "high"})
    if st == 200:
        tpl = (doc.evidence.get("props") or {}).get("chat_template") or ""
        reads_effort = "reasoning_effort" in tpl
        detail = ("server accepted chat_template_kwargs including an invented "
                  "name without error: acceptance proves nothing about effect")
        if tpl:
            detail += (f"; this template {'READS' if reads_effort else 'never reads'} "
                       f"reasoning_effort, so that knob is "
                       f"{'live' if reads_effort else 'dead here'}")
        if tpl and not reads_effort:
            doc.problem(["07"], detail,
                        "before trusting any kwarg, grep the template for it; "
                        "diff accepted-vs-read in both directions")
        else:
            doc.ok(["07"], detail)
    elif st is None:
        doc.skip(["07"], "kwarg acceptance probe", "request failed")
    else:
        doc.ok(["07"], f"server rejects unknown chat_template_kwargs (http {st}): "
               "at least dead knobs are loud here")

def check_tools(doc, base, key):
    """Traps 19 (structured vs prose), 26 (tool markup swallowed by reasoning)."""
    st, choice, raw = chat(doc, base, key, doc.model,
                           [{"role": "user", "content":
                             "What time is it in Tokyo? Use the tool."}],
                           max_tokens=512, tools=TOOLS,
                           chat_template_kwargs={"enable_thinking": True})
    if st != 200 or choice is None:
        doc.skip(["19", "26"], "tool-calling probe",
                 f"tools request failed (http {st}); if your server needs parser "
                 f"flags for tools, that absence is itself trap 19")
        return
    c, rc, rr, tcs, _ = msg_fields(choice)
    reason_text = rc or rr
    if tcs:
        doc.ok(["19"], f"one tool defined, structured tool_calls returned "
               f"(name={tcs[0].get('function', {}).get('name')})")
    elif "<tool_call>" in reason_text or "<tool_call>" in c:
        doc.problem(["26"], "tool markup produced but not parsed into tool_calls "
                    "(found inside the reasoning/content text): the parser is "
                    "eating your tool calls",
                    "on vLLM run a build past PR #35687; on llama.cpp use a "
                    "template that closes think before tool_call")
    else:
        doc.problem(["19"], "model described or skipped the call in prose; no "
                    "structured tool_calls with a tool defined",
                    "check serve flags: --jinja and the model's native template "
                    "on llama.cpp, the model-specific tool parser on vLLM")

def check_ceiling(doc, base, key):
    """Traps 12/16/22: empty content at cap, degeneration vs truncation."""
    st, choice, _ = chat(doc, base, key, doc.model,
                         [{"role": "user", "content":
                           "Write a python function that validates RFC3339 "
                           "timestamps without external libraries, with tests."}],
                         max_tokens=512,
                         chat_template_kwargs={"enable_thinking": True})
    if st != 200 or choice is None:
        doc.skip(["12"], "ceiling probe", f"request failed (http {st})")
        return
    c, rc, rr, _t, _ = msg_fields(choice)
    fr = choice.get("finish_reason")
    reason = rc or rr
    if fr == "length" and not c.strip():
        lines = [l for l in reason.splitlines() if l.strip()]
        uniq = len(set(lines)) / max(1, len(lines))
        z = len(zlib.compress(reason.encode())) / max(1, len(reason))
        kind = "honest truncation" if (uniq > 0.5 and z > 0.2) else \
               "possible degeneration loop"
        doc.problem(["12", "22", "16"],
                    f"hard task at max_tokens=512: HTTP 200, finish=length, "
                    f"EMPTY content, {len(reason)} chars of reasoning "
                    f"({kind}: unique-line {uniq:.2f}, zlib {z:.2f}). If your "
                    f"harness scores this zero, it is measuring your budget",
                    "bucket cap-hits before scoring; find THIS model's "
                    "conversion floor (family advice does not transfer)")
    else:
        doc.ok(["12"], f"hard task at 512 tokens: finish={fr}, "
               f"content {'present' if c.strip() else 'empty'} "
               f"(no empty-at-cap signature this probe)")

def check_configs(doc, hf_repo):
    """Traps 21 (generation_config missing), 17 (defaults vs card), 10 (quant)."""
    props = doc.evidence.get("props")
    if props:
        p = (props.get("default_generation_settings") or {}).get("params", {})
        eff = {k: round(v, 3) if isinstance(v, float) else v
               for k, v in p.items()
               if k in ("temperature", "top_k", "top_p", "min_p", "presence_penalty")}
        doc.evidence["server_defaults"] = eff
    else:
        eff = None
    if not hf_repo:
        doc.skip(["21", "17", "10"], "generation_config / card-sampling / quant "
                 "scheme checks",
                 "pass --hf-repo org/name to compare against the checkpoint's "
                 "shipped configs")
        return
    st, txt = get(f"https://huggingface.co/{hf_repo}/resolve/main/generation_config.json")
    if st == 200:
        try:
            gc = json.loads(txt)
            doc.ok(["21"], f"generation_config.json exists on {hf_repo} "
                   f"(keys: {sorted(gc.keys())[:6]})")
            if eff:
                diffs = {k: (eff.get(k), gc.get(k)) for k in eff
                         if k in gc and not _close(eff.get(k), gc.get(k))}
                if diffs:
                    doc.problem(["17"], f"server defaults differ from the shipped "
                                f"generation_config: {diffs} (server, card)",
                                "set sampling explicitly per request; never "
                                "describe a run as 'model defaults' across stacks")
                else:
                    doc.ok(["17"], "server defaults match the shipped generation_config")
        except Exception:
            doc.skip(["21"], "generation_config parse", "unparseable JSON")
    elif st == 404:
        detail = (f"{hf_repo} ships NO generation_config.json: there is no such "
                  f"thing as 'model defaults' on this checkpoint")
        if eff:
            detail += f"; you are silently running your server's built-ins: {eff}"
        doc.problem(["21"], detail,
                    "take sampling from the card's prose, per mode, and set it "
                    "explicitly on every request")
    else:
        doc.skip(["21"], "generation_config fetch", f"http {st} from huggingface.co")
    st, txt = get(f"https://huggingface.co/{hf_repo}/resolve/main/config.json")
    if st == 200:
        try:
            cfg = json.loads(txt)
            qc = cfg.get("quantization_config")
            if qc:
                doc.ok(["10"], f"quantization_config present: method="
                       f"{qc.get('quant_method')}, ignore list "
                       f"{'present' if qc.get('ignore') else 'ABSENT'}; the label "
                       f"is not the kernel path, read this before downloading")
            else:
                doc.ok(["10"], "no quantization_config in config.json "
                       "(unquantized checkpoint or quant recorded elsewhere)")
        except Exception:
            doc.skip(["10"], "config.json parse", "unparseable JSON")
    else:
        doc.skip(["10"], "config.json fetch", f"http {st}")

def _close(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-3
    except Exception:
        return a == b

# ------------------------------------------------------------------ output

def emit(doc, args):
    T = lambda ns: " ".join(f"[trap {n}]({trap(n)})" for n in ns)
    print(f"\nminefield-doctor: {args.base_url}")
    print(f"stack={doc.stack} model={doc.model} build={doc.build or 'n/a'} "
          f"requests_made={doc.requests_made}\n")
    print(f"== PROBLEMS ({len(doc.problems)}) ==")
    for ns, title, fix in doc.problems or []:
        print(f"  ! {title}\n    fix: {fix}\n    see: {T(ns)}")
    if not doc.problems:
        print("  none found by the checks that ran")
    print(f"\n== CHECKED AND CLEAN ({len(doc.clean)}) ==")
    for ns, title in doc.clean:
        print(f"  + {title}\n    see: {T(ns)}")
    print(f"\n== COULD NOT CHECK ({len(doc.blocked)}) ==")
    for ns, title, why in doc.blocked or []:
        print(f"  ? {title}\n    why: {why}\n    see: {T(ns)}")
    if not doc.blocked:
        print("  everything applicable was checked")
    if args.report:
        print("\n== PASTE-READY REPORT (for an 'I hit a trap' issue) ==\n")
        print("```markdown")
        print("**What were you serving**")
        print(f"- stack: {doc.stack} ({doc.build or 'build unknown'})")
        print(f"- model: {doc.model}")
        print("- endpoint: (host redacted by doctor; add server flags yourself)")
        print(f"- doctor findings ({len(doc.problems)} problem(s)):")
        for ns, title, _ in doc.problems:
            print(f"  - {title} (traps {', '.join(ns)})")
        print("\n**What broke / what you saw**\n<your words here>")
        print("\n**What fixed it**\n<if anything>")
        print("```")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True,
                    help="OpenAI-compatible base, e.g. http://localhost:8000/v1")
    ap.add_argument("--model", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--hf-repo", default=None,
                    help="org/name of the checkpoint, enables config checks")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    root = base[:-3].rstrip("/")
    doc = Doc()
    if not detect_stack(doc, base, root, args.api_key):
        print(f"unreachable: {base}/models did not answer", file=sys.stderr)
        sys.exit(1)
    if args.model:
        doc.model = args.model
    check_reasoning_fields(doc, base, args.api_key)
    check_streaming(doc, base, args.api_key)
    check_history_assembly(doc, root, args.api_key)
    check_kwarg_deadness(doc, base, root, args.api_key)
    check_tools(doc, base, args.api_key)
    check_ceiling(doc, base, args.api_key)
    check_configs(doc, args.hf_repo)
    emit(doc, args)
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"stack": doc.stack, "model": doc.model,
                       "problems": doc.problems, "clean": doc.clean,
                       "could_not_check": doc.blocked,
                       "evidence": doc.evidence}, f, indent=1, default=str)

if __name__ == "__main__":
    main()
