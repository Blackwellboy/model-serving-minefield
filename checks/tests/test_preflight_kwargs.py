#!/usr/bin/env python3
"""Regression test for preflight_template.enumerate_kwargs.

The defect: Jinja tests, Jinja filters, macro parameters and namespace keyword
arguments were reported as caller-supplied chat_template_kwargs, four of them
raising BLOCKING findings on a real vendor template. Meanwhile the actual
kwargs were suppressed, because the canonical idiom
`{% set x = x if x is defined else D %}` looks like a local assignment.

The fixtures below are written here rather than vendored, so this file is
self-contained and carries no third-party template text. Each one reproduces a
shape observed on a real checkpoint, named in its comment.

To also run against real templates on your own disk, point
MINEFIELD_TEMPLATE_DIR at a directory of `*.jinja` files. Every file found
there is asserted to yield no Jinja builtin as a kwarg. That arm is skipped
when the variable is unset, which is the normal case.

    python3 checks/tests/test_preflight_kwargs.py
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEW = HERE.parent / "preflight_template.py"

# Identifiers that must NEVER be reported as caller kwargs. Jinja tests,
# Jinja filters, macro parameters, namespace keyword arguments.
FORBIDDEN = {
    "iterable", "mapping", "sequence", "safe", "tojson", "string", "number",
    "boolean", "callable", "defined", "undefined", "json_dict", "handled_keys",
    "last_user_idx", "selectattr", "rejectattr", "groupby", "urlencode",
    "range", "dict", "cycler", "joiner", "namespace", "lipsum",
}

# Every false-positive class at once, plus the suppressed-real-kwarg class.
# Shapes taken from the Nemotron 3 and Qwen 3.x template families.
SYNTH_ALL_CLASSES = """
{% macro render_extra(json_dict, handled_keys) %}
  {%- if json_dict is mapping %}{{- json_dict | tojson | safe }}{%- endif %}
{% endmacro %}
{%- set my_kwarg = my_kwarg if my_kwarg is defined else True %}
{%- set ns = namespace(last_user_idx = -1) %}
{%- if tools is iterable and tools | length > 0 %}x{%- endif %}
{%- if my_kwarg %}<think>{%- endif %}
{{ other_kwarg | default('z') }}
"""

# The stripping switch written in each polarity: the pair that a pipeline
# standardised on one name silently no-ops against.
SYNTH_BOTH_POLARITIES = """
{%- set enable_thinking = enable_thinking if enable_thinking is defined else True %}
{%- set truncate_history_thinking = truncate_history_thinking
      if truncate_history_thinking is defined else True %}
{%- set preserve_thinking = preserve_thinking if preserve_thinking is defined else False %}
{%- for message in messages %}
  {%- if message.role == 'assistant' %}
    {%- if truncate_history_thinking and not preserve_thinking %}<think></think>
    {%- else %}<think>{{ message.reasoning_content }}</think>{%- endif %}
  {%- endif %}
{%- endfor %}
{%- if enable_thinking %}<think>{%- endif %}
"""

# A template that reads nothing at all: the kwarg surface must be empty, not
# populated with Jinja machinery.
SYNTH_NO_KWARGS = """
{%- for message in messages %}<|im_start|>{{ message.role }}
{{ message.content | trim }}<|im_end|>
{%- endfor %}
{%- if add_generation_prompt %}<|im_start|>assistant
{%- endif %}
"""

fails = []


def check(label, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        fails.append(label)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pf = load(NEW, "pf_new")

# -------------------------------------------------------- every class at once
cand, defaults, thinky = pf.enumerate_kwargs(SYNTH_ALL_CLASSES)
check("all-classes: no Jinja builtin reported as a kwarg",
      not (set(c.lower() for c in cand) & FORBIDDEN), f"got={sorted(cand)}")
check("all-classes: self-defaulting kwarg recovered", "my_kwarg" in cand,
      f"got={sorted(cand)}")
check("all-classes: self-defaulting default captured",
      defaults.get("my_kwarg") == "True", str(defaults.get("my_kwarg")))
check("all-classes: filter-default kwarg still found", "other_kwarg" in cand,
      f"got={sorted(cand)}")
check("all-classes: thinking-gating kwarg flagged", "my_kwarg" in thinky,
      f"thinky={sorted(thinky)}")
check("all-classes: macro parameters are not kwargs",
      not ({"json_dict", "handled_keys"} & set(cand)), f"got={sorted(cand)}")
check("all-classes: namespace keyword arguments are not kwargs",
      "last_user_idx" not in cand, f"got={sorted(cand)}")

# ------------------------------------------------------------ both polarities
cand2, defaults2, thinky2 = pf.enumerate_kwargs(SYNTH_BOTH_POLARITIES)
for name in ("enable_thinking", "truncate_history_thinking", "preserve_thinking"):
    check(f"polarities: {name} is surfaced", name in cand2, f"got={sorted(cand2)}")
    check(f"polarities: {name} is flagged as thinking-gating", name in thinky2,
          f"thinky={sorted(thinky2)}")
check("polarities: no Jinja builtin leaked",
      not (set(c.lower() for c in cand2) & FORBIDDEN), f"got={sorted(cand2)}")

# ------------------------------------------------------------------ no kwargs
cand3, _d3, thinky3 = pf.enumerate_kwargs(SYNTH_NO_KWARGS)
check("no-kwargs: a template that reads no kwarg reports none",
      not cand3, f"got={sorted(cand3)}")
check("no-kwargs: nothing is flagged as thinking-gating", not thinky3,
      f"thinky={sorted(thinky3)}")

# -------------------------------------------------------------- empty and odd
check("empty template yields an empty surface",
      pf.enumerate_kwargs("") == ([], {}, []))
check("literal text outside jinja delimiters is not scanned",
      not pf.enumerate_kwargs("just some prose about enable_thinking")[0])

# --------------------------------------------- optional: real local templates
tdir = os.environ.get("MINEFIELD_TEMPLATE_DIR")
if tdir and Path(tdir).is_dir():
    found = sorted(Path(tdir).glob("*.jinja"))
    if not found:
        print(f"SKIP  MINEFIELD_TEMPLATE_DIR={tdir} holds no *.jinja")
    for p in found:
        cand_r, _d, thinky_r = pf.enumerate_kwargs(p.read_text(encoding="utf-8"))
        bad = sorted(set(c.lower() for c in cand_r) & FORBIDDEN)
        check(f"{p.name}: no Jinja builtin reported as a kwarg", not bad,
              f"reported={bad}")
        bad_t = sorted(set(t.lower() for t in thinky_r) & FORBIDDEN)
        check(f"{p.name}: no Jinja builtin raised as thinking-gating", not bad_t,
              f"thinky={bad_t}")
        print(f"      {p.name}: kwargs={sorted(cand_r)}")
else:
    print("SKIP  real-template arm (set MINEFIELD_TEMPLATE_DIR to enable)")

print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)
print("ALL PASS")
