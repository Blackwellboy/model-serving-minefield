# Checks

Runnable checks that catch registry entries. Stdlib-only where possible so
they run anywhere the lane is reachable.

## preflight_template.py

Template forensics. Answers the question every request-shaped check misses:
what does the model actually see at turn N?

Reports three things:

- **Assembly diff.** Renders the actual prompt for a marked three-turn
  conversation and reports whether the prior assistant turn's reasoning is
  **preserved or stripped** (Trap 04). Refuses to certify a lane whose
  assembled history drops the marker.
- **Injection and coercion.** Whether the template injects content, merges
  messages, or rewrites roles (system merged into user, and so on).
- **Kwarg surface.** Enumerates every chat template kwarg the Jinja actually
  reads and diffs it against what the model card documents (Trap 04
  corollary, Trap 07). Anything read-but-undocumented is an untested
  variable.

Usage:

```bash
python3 checks/preflight_template.py --base-url http://HOST:PORT/v1 \
    [--model NAME] [--api-key KEY] \
    [--template-file path/to/chat_template.jinja] \
    [--documented-kwargs enable_thinking,thinking_mode] \
    [--kwargs-on '{"enable_thinking": true}'] \
    --json results/template_forensics.json
```

Exit codes: 0 forensics complete (read the verdicts), 1 lane unreachable,
2 completed with a blocking finding (stripped reasoning, or an undocumented
kwarg that changes assembly).

Jinja2 is used for the local render path if importable, but it is optional.

## tool_args_dialect_probe.py (trap 43)

Does the chat template survive tool-call `arguments` arriving as a **string**? The OpenAI spec says
it is a string; templates that gate parameter expansion on `arguments is mapping` with no `else`
render an empty call when a framework replays a prior call with pre-serialized JSON.

Offline mode renders the Jinja both ways and diffs the parameter body (needs `jinja2`). Live mode
sends a real `tools` array, asserts structured `tool_calls` come back, then replays with
string-valued arguments (stdlib only).

Usage: `python3 checks/tool_args_dialect_probe.py --template ./chat_template.jinja`
or `--base-url http://127.0.0.1:8080/v1 --model NAME`.

## reasoning_budget_probe.py (trap 44, supports 12 / 16 / 22)

Sends the same prompt N times at a fixed ceiling and reports truncation rate plus the
completion-token distribution. A pileup at exactly the cap is the signature. Run at your real eval
temperature, at temp 0 you will not see the tail that bites you at 0.6.

Usage: `python3 checks/reasoning_budget_probe.py --base-url URL --model NAME --max-tokens 2560 -n 20 --temp 0.6`

## dequant_fidelity.py (trap 45, supports 27)

Per-row cosine in float64 plus generation probes. Two assertions because either alone passes on a
subtly-broken model: a flat cosine over a billion-element `lm_head` overflows in float32 and can
return > 1, and the capital-of-France probe passes on a wrong-layout dequant where a decimal
comparison does not.

Usage: `python3 checks/dequant_fidelity.py --base PATH --dequant PATH` (needs torch + safetensors)
or `--base-url URL --model NAME` for the generation probes alone (stdlib).

## util_vs_power_tell.sh (trap 47, supports 10)

Run while a decode benchmark is in flight. High GPU utilization at low power draw (98% util at 47%
TDP) means busy compute units that are not saturating tensor cores, i.e. a fallback kernel. Prints
the follow-up ancestry check.

Usage: `bash checks/util_vs_power_tell.sh 30`

## cache_hit_probe.py (trap 48)

Sends a growing conversation with a large stable prefix and reports time-to-first-token per turn
plus any server-reported cache ratio. Flat TTFT across turns means the prefix cache is not
engaging, either auto-disabled for the architecture, or something in your prefix changes per
message.

Usage: `python3 checks/cache_hit_probe.py --base-url URL --model NAME --turns 3`

## latency_reconciliation.py (trap 49)

Compares client-observed latency against what the server says the request took, and reports the
unexplained gap. A large, roughly constant, client-only gap is not a model problem. Also runs the
dual-stack resolution check that identifies the cause.

Usage: `python3 checks/latency_reconciliation.py --base-url URL --model NAME [--server-total 9.8]`

## tokenized_length_assert.py (trap 50)

Asserts the server's own prompt-token count against your target, cold (it salts the prompt to defeat
the cache, because a warm request's prompt count may be the delta from the cached prefix). Pass
`--repeat` to reproduce a bad harness; omit it to grow the filler until the target is met.

Usage: `python3 checks/tokenized_length_assert.py --base-url URL --model NAME --target 4096`

## hidden_state_align.py (trap 51)

Before filing a "layer N exploded" bug against your own implementation, prove the two dumps mean the
same thing. Asserts dump counts match, tries both index alignments, and checks whether a reported
collapse simply lands on `||norm_f.weight||`: which is what RMSNorm does to any input by
construction.

Usage: `python3 checks/hidden_state_align.py --ours DIR --ref DIR --norm-weight FILE` (needs numpy)

## Tests

```bash
python3 checks/tests/test_preflight_kwargs.py
```

Regression coverage for `enumerate_kwargs`, the part that decides which
identifiers are caller-supplied `chat_template_kwargs`. It got that wrong in
both directions at once: Jinja tests, filters, macro parameters and
`namespace(...)` keyword arguments were reported as kwargs (four of them
raising BLOCKING findings on a real vendor template), while the canonical
idiom `{% set x = x if x is defined else D %}` made the genuine kwargs look
like local assignments and suppressed them. The fixtures are written in the
test file rather than vendored, so it carries no third-party template text.
Set `MINEFIELD_TEMPLATE_DIR` to a directory of `*.jinja` files to also run it
over real templates on your own disk; that arm skips when the variable is
unset.
