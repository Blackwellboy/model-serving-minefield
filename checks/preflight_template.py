#!/usr/bin/env python3
"""preflight_template.py: Template Forensics.

Answers the question every request-shaped check misses: **what does the model
actually see at turn N?**

Four independent testers characterized the same model and all four missed that
prior assistant turns were rendering as empty `<think></think>` blocks in the
assembled history, because every check anyone ran inspected the REQUEST. The
model was reading its own thinking-free history as a suppression signal, which
is why single-turn firing was 60-72% and a 12h multi-turn soak measured ~0.1%.
The control was an undocumented `preserve_thinking` kwarg the template reads and
the model card never mentions. See traps/04-history-reasoning-stripping.md in this registry.

This module runs BEFORE any multi-turn phase and reports:

  A. ASSEMBLY DIFF  : render the actual prompt for a 3-turn conversation and
                       diff it against what the client sent. Is the prior
                       assistant turn's reasoning PRESERVED or STRIPPED?
  B. INJECTION/COERCION: does the template inject content, merge messages, or
                       rewrite roles (system merged into user, etc.)?
  C. KWARG SURFACE  : enumerate every chat_template_kwarg the Jinja actually
                       reads, and diff against what the model card documents.
                       Anything read-but-undocumented is an UNTESTED VARIABLE.

Stdlib only. Jinja2 is used if importable (local render path) but is optional.

Usage:
    python3 preflight_template.py --base-url http://HOST:PORT/v1 \\
        [--model NAME] [--api-key KEY] \\
        [--template-file path/to/chat_template.jinja] \\
        [--documented-kwargs enable_thinking,thinking_mode] \\
        [--kwargs-on '{"enable_thinking": true}'] \\
        --json results/template_forensics_<lane>.json

Exit codes: 0 = forensics complete (read the verdicts), 1 = lane unreachable,
2 = completed but a BLOCKING finding was raised (stripped reasoning, or an
undocumented kwarg that changes assembly).
"""
import argparse, json, re, sys, urllib.request, urllib.error

# ---------------------------------------------------------------- transport

def _req(url, key=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data,
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

def post(url, body, key=None, timeout=60):
    return _req(url, key, json.dumps(body).encode(), timeout)

# ------------------------------------------------------- template acquisition

def fetch_template(root, base, key, template_file):
    """Return (template_source, provenance). Order: explicit file > llama.cpp
    /props > vLLM /tokenize is no help here, so fall back to none."""
    if template_file:
        try:
            with open(template_file, encoding="utf-8") as f:
                return f.read(), f"--template-file {template_file}"
        except Exception as e:
            return None, f"template-file unreadable: {e}"
    st, body = get(root + "/props", key)
    if st == 200:
        try:
            d = json.loads(body)
            tpl = d.get("chat_template") or (d.get("default_generation_settings") or {}).get("chat_template")
            if tpl:
                return tpl, "llama.cpp /props chat_template"
        except Exception:
            pass
    return None, ("not retrievable from the serving path; pass --template-file "
                  "(HF checkpoint chat_template.jinja or tokenizer_config.json)")

# ------------------------------------------------------------ kwarg surfacing

# names that appear in every chat template and are not user-supplied kwargs
_BUILTIN = {
    "messages", "message", "content", "role", "loop", "ns", "namespace", "tools",
    "tool", "tool_calls", "tool_call", "add_generation_prompt", "bos_token",
    "eos_token", "pad_token", "unk_token", "raise_exception", "none", "true",
    "false", "strftime_now", "date_string", "system_message", "reasoning_content",
    "thinking", "index", "item", "key", "value", "text", "arguments", "name",
    "type", "function", "id", "images", "audio", "video", "documents",
}

_JINJA_IDENT = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")

# Jinja keywords. Not kwargs.
_JINJA_KEYWORD = {
    "if", "else", "elif", "endif", "for", "endfor", "set", "endset", "in",
    "is", "not", "and", "or", "with", "without", "endwith", "macro",
    "endmacro", "call", "endcall", "filter", "endfilter", "block", "endblock",
    "extends", "include", "import", "from", "as", "do", "raw", "endraw",
    "generation", "endgeneration", "recursive", "scoped", "context",
    # Jinja globals: callable in any template, never caller-supplied
    "range", "dict", "lipsum", "cycler", "joiner", "namespace",
}

# Jinja TESTS: the identifier after `is` or `is not`. `tools is iterable` does
# not mean the caller supplies `iterable`. Positional detection below catches
# custom tests too; this list is the backstop for the built-in ones.
_JINJA_TEST = {
    "defined", "undefined", "none", "boolean", "false", "true", "integer",
    "float", "number", "string", "sequence", "mapping", "iterable", "callable",
    "sameas", "escaped", "in", "divisibleby", "odd", "even", "lower", "upper",
    "filter", "test", "eq", "ne", "lt", "le", "gt", "ge", "equalto",
}

# Jinja FILTERS: the identifier after `|`. `x | tojson | safe` does not mean the
# caller supplies `safe`.
_JINJA_FILTER = {
    "abs", "attr", "batch", "capitalize", "center", "default", "d",
    "dictsort", "escape", "e", "filesizeformat", "first", "float",
    "forceescape", "format", "groupby", "indent", "int", "join", "last",
    "length", "list", "lower", "map", "max", "min", "pprint", "random",
    "reject", "rejectattr", "replace", "reverse", "round", "safe", "select",
    "selectattr", "slice", "sort", "string", "striptags", "sum", "title",
    "tojson", "trim", "truncate", "unique", "upper", "urlencode", "urlize",
    "wordcount", "wordwrap", "xmlattr", "items", "split", "startswith",
    "endswith", "rstrip", "lstrip", "strip", "count", "keys", "values",
}

# `x if x is defined else DEFAULT` and `x | default(...)` are the two idioms a
# template uses to READ a caller-supplied kwarg while giving it a fallback. The
# first idiom assigns to the same name, so a naive "locally assigned" filter
# hides exactly the kwargs we are looking for.
_SELF_DEFAULTING_SET = re.compile(
    r"{%-?\s*set\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\1\s+if\s+\1\s+is\s+defined", re.S)


def enumerate_kwargs(tpl):
    """Find identifiers the template READS that are not builtins, not Jinja
    syntax, and not locally assigned. These are the chat_template_kwargs
    surface.

    Three classes of false positive were reported against the previous version
    and are handled explicitly here, because each one produced a BLOCKING
    finding on a real vendor template:

      - Jinja tests (`tools is iterable`, `x is mapping`, `x is sequence`)
      - Jinja filters (`x | tojson | safe`)
      - macro parameters and `namespace(...)` keyword arguments
        (`{% macro m(json_dict, handled_keys) %}`,
         `{% set ns = namespace(last_user_idx = -1) %}`)

    A fourth defect went the other way: the real kwargs were being SUPPRESSED,
    because the canonical kwarg idiom
    `{% set enable_thinking = enable_thinking if enable_thinking is defined else True %}`
    looks like a local assignment. Those names are now recovered explicitly.
    """
    if not tpl:
        return [], {}, []
    self_defaulting = set(_SELF_DEFAULTING_SET.findall(tpl))
    assigned = set(re.findall(r"{%-?\s*set\s+([a-zA-Z_][a-zA-Z0-9_]*)", tpl)) - self_defaulting
    forvars = set()
    for m in re.finditer(r"{%-?\s*for\s+([a-zA-Z_0-9_,\s]+?)\s+in\s", tpl):
        for v in m.group(1).split(","):
            forvars.add(v.strip())
    macros = set(re.findall(r"{%-?\s*macro\s+([a-zA-Z_][a-zA-Z0-9_]*)", tpl))
    # macro PARAMETERS are locals, not caller kwargs
    macro_params = set()
    for m in re.finditer(r"{%-?\s*macro\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(([^)]*)\)", tpl):
        for p in m.group(1).split(","):
            p = p.split("=")[0].strip()
            if p:
                macro_params.add(p)

    candidates = {}
    # only look inside jinja delimiters, not the literal text of the template
    for block in re.findall(r"{[{%](.*?)[%}]}", tpl, re.S):
        # drop string literals first: `message.role == "assistant"` must not
        # report `assistant` as a kwarg (caught by the module's own self-test)
        block = re.sub(r"'[^']*'|\"[^\"]*\"", " ", block)
        # drop attribute access: `message.content` must not report `content`
        block = re.sub(r"\.\s*[a-zA-Z_][a-zA-Z0-9_]*", " ", block)
        # drop keyword-argument names in calls: `namespace(last_user_idx = -1)`
        # binds a local, it does not read a caller kwarg
        block = re.sub(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=(?!=)", " ", block)
        # drop test positions: everything directly after `is` or `is not`
        block = re.sub(r"\bis\s+(?:not\s+)?[a-zA-Z_][a-zA-Z0-9_]*", " is ", block)
        # drop filter positions: everything directly after a pipe
        block = re.sub(r"\|\s*[a-zA-Z_][a-zA-Z0-9_]*", " ", block)
        for ident in _JINJA_IDENT.findall(block):
            low = ident.lower()
            if (low in _BUILTIN or low in _JINJA_KEYWORD or low in _JINJA_TEST
                    or low in _JINJA_FILTER):
                continue
            if (ident in assigned or ident in forvars or ident in macros
                    or ident in macro_params):
                continue
            candidates.setdefault(ident, 0)
            candidates[ident] += 1

    # defaults, so we can report what happens when the kwarg is absent
    defaults = {}
    for m in re.finditer(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*default\(\s*([^)]*?)\s*\)", tpl):
        defaults[m.group(1)] = m.group(2).strip()
    for m in re.finditer(r"([a-zA-Z_][a-zA-Z0-9_]*)\s+is\s+defined", tpl):
        defaults.setdefault(m.group(1), "(guarded by `is defined`)")
    # the self-defaulting idiom carries its fallback on the same line; surface it
    for m in re.finditer(
            r"{%-?\s*set\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\1\s+if\s+\1\s+is\s+defined"
            r"\s+else\s+([^%}]+?)\s*-?%}", tpl, re.S):
        defaults[m.group(1)] = m.group(2).strip()

    # a kwarg the template reads through the self-defaulting idiom is a kwarg
    # even if it never appears anywhere else
    for name in self_defaulting:
        candidates.setdefault(name, 0)
        candidates[name] += 1

    # which of these gate a think/reasoning branch? those are the dangerous ones
    thinky = []
    for name in candidates:
        for m in re.finditer(re.escape(name), tpl):
            window = tpl[max(0, m.start() - 260): m.end() + 260]
            if "think" in window.lower() or "reason" in window.lower():
                thinky.append(name)
                break
    return sorted(candidates), defaults, sorted(set(thinky))

# ------------------------------------------------------- assembly inspection

REASONING_MARK = "SENTINEL_PRIOR_REASONING_9F3A2C"
CONTENT_MARK = "SENTINEL_PRIOR_CONTENT_5B1D7E"
USER1_MARK = "SENTINEL_USER_ONE_2A8C4F"

def probe_messages(reasoning_field):
    """A 3-turn history whose turn-1 assistant carries BOTH content and reasoning,
    each uniquely marked so we can grep the assembled prompt for them."""
    assistant = {"role": "assistant", "content": CONTENT_MARK}
    assistant[reasoning_field] = REASONING_MARK
    return [
        {"role": "system", "content": "You are a test harness probe."},
        {"role": "user", "content": USER1_MARK},
        assistant,
        {"role": "user", "content": "Second user turn."},
    ]

def render_llamacpp(root, key, messages, kwargs):
    body = {"messages": messages}
    if kwargs:
        body["chat_template_kwargs"] = kwargs
    st, b = post(root + "/apply-template", body, key)
    if st == 200:
        try:
            return json.loads(b).get("prompt"), "llama.cpp /apply-template"
        except Exception:
            return None, f"/apply-template unparsable: {b[:200]}"
    return None, f"/apply-template HTTP {st}"

def render_vllm_tokenize(base, key, model, messages, kwargs):
    """vLLM /tokenize accepts chat messages and can return the rendered string."""
    body = {"model": model, "messages": messages, "add_generation_prompt": True}
    if kwargs:
        body["chat_template_kwargs"] = kwargs
    for path in ("/tokenize",):
        st, b = post(base + path, body, key)
        if st == 200:
            try:
                d = json.loads(b)
            except Exception:
                continue
            for field in ("prompt", "rendered_prompt", "text"):
                if isinstance(d.get(field), str) and d[field]:
                    return d[field], f"vLLM {path} ({field})"
            toks = d.get("tokens") or d.get("token_strs")
            if isinstance(toks, list) and toks and isinstance(toks[0], str):
                return "".join(toks), f"vLLM {path} (token_strs joined)"
            return None, (f"vLLM {path} returned ids only (no detokenized text); "
                          f"re-run with --template-file for the local render path")
    return None, "vLLM /tokenize unavailable"

def render_local(tpl, messages, kwargs):
    try:
        from jinja2 import Environment, BaseLoader
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        env = ImmutableSandboxedEnvironment(loader=BaseLoader(), trim_blocks=False, lstrip_blocks=False)
        env.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(RuntimeError(m))
        env.globals["strftime_now"] = lambda fmt: ""
        t = env.from_string(tpl)
        return t.render(messages=messages, add_generation_prompt=True,
                        bos_token="", eos_token="", **(kwargs or {})), "local jinja2 render"
    except ImportError:
        return None, "jinja2 not installed (pip install jinja2): local render unavailable"
    except Exception as e:
        return None, f"local render failed: {type(e).__name__}: {e}"

def analyse_assembly(prompt, sent_messages):
    """Grep the assembled prompt for our sentinels and structural tells."""
    if prompt is None:
        return {"available": False}
    empty_think = len(re.findall(r"<think>\s*</think>", prompt))
    return {
        "available": True,
        "chars": len(prompt),
        "prior_reasoning_preserved": REASONING_MARK in prompt,
        "prior_content_preserved": CONTENT_MARK in prompt,
        "first_user_preserved": USER1_MARK in prompt,
        "empty_think_blocks": empty_think,
        "think_open_tags": prompt.count("<think>"),
        "think_close_tags": prompt.count("</think>"),
        "roles_seen": sorted(set(re.findall(r"<\|im_start\|>(\w+)|<\|(\w+)\|>", prompt)) and
                             set(re.findall(r"<\|im_start\|>(\w+)", prompt))) or None,
        "sent_message_count": len(sent_messages),
        "prompt_head": prompt[:400],
        "prompt_tail": prompt[-400:],
    }

# ------------------------------------------------------------------- verdicts

def build_verdicts(asm_default, asm_preserve, kwargs_read, thinky, documented, defaults):
    v, blocking = [], False

    if not asm_default.get("available"):
        v.append({"level": "UNKNOWN", "code": "NO_RENDER_PATH",
                  "detail": "Could not obtain the assembled prompt on this serving path. "
                            "Pass --template-file to use the local render path, or run the "
                            "behavioural history-integrity control cell instead (PREFLIGHT.md)."})
        return v, blocking

    if asm_default.get("prior_reasoning_preserved"):
        v.append({"level": "OK", "code": "REASONING_PRESERVED",
                  "detail": "Prior assistant reasoning survives history assembly by default."})
    else:
        blocking = True
        d = ("Prior assistant reasoning is STRIPPED during history assembly. "
             "Any multi-turn measurement on this lane is measuring a model that "
             "cannot see its own prior thinking.")
        if asm_default.get("empty_think_blocks"):
            d += (f" {asm_default['empty_think_blocks']} EMPTY <think></think> block(s) are "
                  "rendered into the history, which is the exact shape that reads as a "
                  "'I never think' signal (registry trap 04).")
        v.append({"level": "BLOCKING", "code": "REASONING_STRIPPED", "detail": d})

    if asm_preserve is not None:
        if asm_preserve.get("prior_reasoning_preserved") and not asm_default.get("prior_reasoning_preserved"):
            v.append({"level": "ACTION", "code": "PRESERVE_KWARG_WORKS",
                      "detail": "A preservation kwarg flips assembly from stripped to preserved. "
                                "Set it for every multi-turn phase and record it beside the results."})
        elif not asm_preserve.get("prior_reasoning_preserved"):
            v.append({"level": "WARN", "code": "PRESERVE_KWARG_INEFFECTIVE",
                      "detail": "The preservation kwarg did not change assembly on this path."})

    if not asm_default.get("first_user_preserved") or not asm_default.get("prior_content_preserved"):
        blocking = True
        v.append({"level": "BLOCKING", "code": "HISTORY_DROPPED",
                  "detail": "A prior turn's content did not appear in the assembled prompt at all. "
                            "History is being dropped or merged."})

    # A generation prompt legitimately ends with ONE unclosed <think> for the
    # model to complete, so opens == closes + 1 is the healthy shape. Only an
    # excess of CLOSES (orphans, trap #2) or more than one dangling open is odd.
    o, c = asm_default.get("think_open_tags", 0), asm_default.get("think_close_tags", 0)
    if c > o:
        v.append({"level": "WARN", "code": "ORPHANED_CLOSE_THINK",
                  "detail": f"{c} </think> against {o} <think> in the assembled prompt. "
                            "Orphaned close tags are registry trap 02 and corrupt "
                            "downstream parsing."})
    elif o - c > 1:
        v.append({"level": "WARN", "code": "UNBALANCED_THINK_TAGS",
                  "detail": f"{o} <think> vs {c} </think>. One dangling open is the normal "
                            "generation-prompt shape; more than one suggests prior turns are "
                            "left unclosed in the history."})

    undocumented = [k for k in kwargs_read if documented is not None and k not in documented]
    for k in undocumented:
        lvl = "BLOCKING" if k in thinky else "UNTESTED_VARIABLE"
        if k in thinky:
            blocking = True
        v.append({"level": lvl, "code": "UNDOCUMENTED_KWARG",
                  "detail": f"`{k}` is read by the template (default: {defaults.get(k, 'none found')}) "
                            f"but is not in the documented kwarg list"
                            + (" AND it gates a thinking/reasoning branch. This is the "
                               "preserve_thinking shape: an undocumented switch that changes "
                               "what the model sees." if k in thinky else
                               ". Flag as UNTESTED VARIABLE in the run writeup.")})
    return v, blocking

# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--template-file", default=None,
                    help="chat_template.jinja from the checkpoint (enables the local render path)")
    ap.add_argument("--documented-kwargs", default=None,
                    help="comma list the MODEL CARD documents, e.g. enable_thinking")
    ap.add_argument("--kwargs-on", default=None, help='JSON, e.g. {"enable_thinking": true}')
    ap.add_argument("--preserve-kwargs", default=None,
                    help='JSON candidate preservation kwarg, e.g. {"preserve_thinking": true}')
    ap.add_argument("--reasoning-field", default="reasoning_content",
                    choices=["reasoning_content", "reasoning"],
                    help="field name this stack uses (from preflight.py)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    root = base[:-3].rstrip("/") if base.endswith("/v1") else base
    kwargs_on = json.loads(args.kwargs_on) if args.kwargs_on else None
    preserve = json.loads(args.preserve_kwargs) if args.preserve_kwargs else None
    documented = ([s.strip() for s in args.documented_kwargs.split(",") if s.strip()]
                  if args.documented_kwargs is not None else None)

    out = {"base_url": base, "module": "preflight_template", "version": 1,
           "reachable": False, "render_path": None, "template_provenance": None}

    st, body = get(base + "/models", args.api_key)
    if st is None:
        out["error"] = body
        print(json.dumps(out, indent=2)); sys.exit(1)
    out["reachable"] = True
    model = args.model
    if not model:
        try:
            model = json.loads(body)["data"][0]["id"]
        except Exception:
            pass
    out["model"] = model

    tpl, prov = fetch_template(root, base, args.api_key, args.template_file)
    out["template_provenance"] = prov
    out["template_retrieved"] = bool(tpl)

    kwargs_read, defaults, thinky = enumerate_kwargs(tpl)
    out["kwargs_read_by_template"] = kwargs_read
    out["kwargs_defaults"] = defaults
    out["kwargs_gating_thinking"] = thinky
    out["kwargs_documented"] = documented
    out["kwargs_undocumented"] = ([k for k in kwargs_read if k not in documented]
                                  if documented is not None else None)

    msgs = probe_messages(args.reasoning_field)
    out["probe_messages_sent"] = msgs

    def render(kw):
        p, how = render_llamacpp(root, args.api_key, msgs, kw)
        if p is None and model:
            p, how2 = render_vllm_tokenize(base, args.api_key, model, msgs, kw)
            how = how if p is None else how2
        if p is None and tpl:
            p, how3 = render_local(tpl, msgs, kw)
            how = how if p is None else how3
        return p, how

    prompt_default, how = render(kwargs_on)
    out["render_path"] = how
    out["assembly_default"] = analyse_assembly(prompt_default, msgs)

    asm_preserve = None
    if preserve:
        merged = dict(kwargs_on or {}); merged.update(preserve)
        prompt_pres, how_p = render(merged)
        asm_preserve = analyse_assembly(prompt_pres, msgs)
        out["assembly_with_preserve_kwargs"] = asm_preserve
        out["preserve_kwargs_tried"] = preserve
        out["render_path_preserve"] = how_p

    verdicts, blocking = build_verdicts(out["assembly_default"], asm_preserve,
                                        kwargs_read, thinky, documented, defaults)
    out["verdicts"] = verdicts
    out["blocking"] = blocking
    out["multi_turn_safe"] = (not blocking) and out["assembly_default"].get("prior_reasoning_preserved", False)

    print(json.dumps(out, indent=2))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=2)
    sys.exit(2 if blocking else 0)

if __name__ == "__main__":
    main()
