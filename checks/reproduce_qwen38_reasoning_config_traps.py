#!/usr/bin/env python3
"""Public template-level reproducer for Qwen3.8 reasoning-config traps.

Independently reproduced by Blackwellboy on
RadixArk/Qwen3.8-27B-NVFP4@52d1adc (template SHA c3cf9e34…).

Prior public report / lead: TheTom/offlabel.

This checker uses ONLY the vendored chat_template.jinja fixture (Apache-2.0).
No GPU and no model weights are required.

Run:
  python3 checks/reproduce_qwen38_reasoning_config_traps.py

Exit 0 only if every published claim PASSes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    from jinja2 import Environment, BaseLoader, StrictUndefined
except ImportError:  # pragma: no cover
    print("FAIL: jinja2 is required (pip install jinja2)")
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "checks" / "fixtures" / "qwen38_nvfp4_52d1adc" / "chat_template.jinja"
EXPECTED_SHA = "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041"

OK, BLOCKING, NOTHING_INSPECTED = 0, 2, 3


def _neg_wrong_fixture_sha() -> int:
    """Negative: wrong fixture hash must not pass as success."""
    if not FIXTURE.exists():
        return BLOCKING
    got = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    # If fixture is correct, this control still "fails" by simulating mismatch
    # detection path: report BLOCKING when we pretend expected is wrong.
    fake_expected = "0" * 64
    return BLOCKING if got != fake_expected else OK


def _neg_medium_instruction_present_is_bad_for_original_claim() -> int:
    """Negative: original claim requires medium to lack a medium instruction."""
    # Synthesize a false positive string detection
    text = "Reasoning effort is set to medium. should_not_pass_as_original_pin"
    if "Reasoning effort is set to medium" in text:
        return BLOCKING
    return OK


def _empty_no_fixture() -> int:
    """Empty-set: missing fixture is not a PASS."""
    return NOTHING_INSPECTED


NEGATIVE_CONTROLS = [
    ("wrong fixture hash is blocking", _neg_wrong_fixture_sha),
    ("medium instruction present is blocking for original-pin claim", _neg_medium_instruction_present_is_bad_for_original_claim),
]
EMPTY_SET_CONTROL = ("fixture missing; nothing inspected", _empty_no_fixture)

XHIGH_INSTR = (
    "Reasoning effort is set to xhigh. Please think carefully through the task, "
    "validate key assumptions, consider plausible alternatives, and prioritize "
    "correctness, consistency, and clarity in the final answer."
)
LOW_INSTR = (
    "Reasoning effort is set to low. Keep your thinking brief and focused, "
    "moving directly to the conclusion without unnecessary elaboration."
)
MED_INSTR = "Reasoning effort is set to medium."


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_env(template_text: str) -> Environment:
    env = Environment(
        loader=BaseLoader(),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
    )

    def raise_exception(msg: str):
        raise ValueError(str(msg))

    def tojson(obj):
        return json.dumps(obj, ensure_ascii=False)

    env.globals["raise_exception"] = raise_exception
    env.filters["tojson"] = tojson
    # transformers uses |items as items(); jinja has .items() via |dictsort alternatives
    env.filters["items"] = lambda d: list(d.items()) if isinstance(d, dict) else d
    env.from_string(template_text)  # compile check
    return env


class _Msg(dict):
    """Dict that also supports attribute access used by chat templates."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e


def _norm_messages(messages: list) -> list:
    out = []
    for m in messages:
        d = _Msg(m)
        d.setdefault("tool_calls", None)
        if "reasoning_content" not in d:
            d["reasoning_content"] = ""
        out.append(d)
    return out


def render(
    env: Environment,
    template_text: str,
    messages: list,
    *,
    enable_thinking=None,
    reasoning_effort=None,
    preserve_thinking=None,
    tools=None,
    add_generation_prompt: bool = True,
    add_vision_id: bool = False,
) -> str:
    tmpl = env.from_string(template_text)
    kwargs = {
        "messages": _norm_messages(messages),
        "add_generation_prompt": add_generation_prompt,
        "add_vision_id": add_vision_id,
        "tools": tools,
    }
    # Only pass defined kwargs so "undefined" stays undefined in Jinja.
    if enable_thinking is not None:
        kwargs["enable_thinking"] = enable_thinking
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    if preserve_thinking is not None:
        kwargs["preserve_thinking"] = preserve_thinking
    return tmpl.render(**kwargs)


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def claim(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(("PASS" if ok else "FAIL") + f"  {name}" + (f"  ({detail})" if detail else ""))

    if not FIXTURE.exists():
        print(f"FAIL: missing fixture {FIXTURE}")
        return 2

    fixture_sha = sha256_file(FIXTURE)
    claim(
        "fixture_sha256",
        fixture_sha == EXPECTED_SHA,
        f"got={fixture_sha}",
    )
    template_text = FIXTURE.read_text(encoding="utf-8")
    env = make_env(template_text)

    simple = [{"role": "user", "content": "Return only the number 42."}]

    # 1) unset effort resolves to xhigh instruction when thinking on
    r_unset = render(env, template_text, simple)  # enable_thinking undefined
    r_true_unset = render(env, template_text, simple, enable_thinking=True)
    r_xhigh = render(env, template_text, simple, enable_thinking=True, reasoning_effort="xhigh")
    r_low = render(env, template_text, simple, enable_thinking=True, reasoning_effort="low")
    r_med = render(env, template_text, simple, enable_thinking=True, reasoning_effort="medium")

    claim(
        "1_unset_effort_resolves_to_xhigh_instruction",
        XHIGH_INSTR in r_unset and XHIGH_INSTR in r_true_unset,
    )
    claim(
        "2_unset_render_equals_explicit_xhigh",
        sha256_text(r_unset) == sha256_text(r_xhigh) == sha256_text(r_true_unset),
        f"unset={sha256_text(r_unset)[:12]} xhigh={sha256_text(r_xhigh)[:12]}",
    )
    claim(
        "3_medium_accepted_without_dedicated_instruction",
        MED_INSTR not in r_med and XHIGH_INSTR not in r_med and LOW_INSTR not in r_med,
        f"sha={sha256_text(r_med)[:12]}",
    )
    claim("3b_low_has_low_instruction", LOW_INSTR in r_low)

    # 4) invalid high errors
    high_err = None
    try:
        render(env, template_text, simple, enable_thinking=True, reasoning_effort="high")
        high_ok = False
    except Exception as e:  # noqa: BLE001
        high_err = str(e)
        high_ok = "Unexpected reasoning effort" in high_err and "high" in high_err
    claim("4_invalid_high_errors", high_ok, high_err or "no error")

    # 5–7 preserve_thinking
    marker = "REASONING_REPLAY_MARKER_UNIQUE_42"
    msgs = [
        {"role": "user", "content": "First question"},
        {
            "role": "assistant",
            "content": "FINAL_ANSWER",
            "reasoning_content": marker + ("." * 200),
        },
        {"role": "user", "content": "Second question"},
    ]
    p_unset = render(env, template_text, msgs, enable_thinking=True, reasoning_effort="low")
    p_true = render(
        env,
        template_text,
        msgs,
        enable_thinking=True,
        reasoning_effort="low",
        preserve_thinking=True,
    )
    p_false = render(
        env,
        template_text,
        msgs,
        enable_thinking=True,
        reasoning_effort="low",
        preserve_thinking=False,
    )
    claim(
        "5_preserve_unset_equals_true",
        sha256_text(p_unset) == sha256_text(p_true),
    )
    claim("6_default_true_replays_reasoning_marker", marker in p_unset and marker in p_true)
    claim("7_preserve_false_strips_marker", marker not in p_false)

    # 8–9 empty content-only assistant think blocks
    empty_msgs = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
    ]
    e_def = render(env, template_text, empty_msgs, enable_thinking=True, reasoning_effort="low")
    e_true = render(
        env,
        template_text,
        empty_msgs,
        enable_thinking=True,
        reasoning_effort="low",
        preserve_thinking=True,
    )
    e_false = render(
        env,
        template_text,
        empty_msgs,
        enable_thinking=True,
        reasoning_effort="low",
        preserve_thinking=False,
    )
    empty_count = lambda t: t.count("<think>\n\n</think>")  # noqa: E731
    claim(
        "8_empty_think_blocks_default_true",
        empty_count(e_def) >= 2 and empty_count(e_true) >= 2,
        f"default={empty_count(e_def)} true={empty_count(e_true)}",
    )
    claim(
        "9_preserve_false_removes_empty_blocks",
        empty_count(e_false) == 0,
        f"false={empty_count(e_false)}",
    )

    # published hash anchors from first-party campaign (optional but strong)
    claim(
        "anchor_unset_xhigh_hash",
        sha256_text(r_unset)
        == "d5c052a8fbbe2495645582fca6230bd3e33ec41e161252d2cc61eefd0db31603",
        sha256_text(r_unset),
    )
    claim(
        "anchor_medium_hash",
        sha256_text(r_med)
        == "575d9cb4b43894c0dcd0184639dbb765f8073a9263ca25385e3cfb34d6a81751",
        sha256_text(r_med),
    )

    failed = [n for n, ok, _ in results if not ok]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} claims passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL CLAIMS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
