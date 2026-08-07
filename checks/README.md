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

Exit codes: 0 forensics complete and nothing blocking, 1 lane unreachable,
2 completed with a blocking finding (stripped reasoning, or an undocumented
kwarg that changes assembly), **3 ran but inspected nothing** (no render path
was available, so no assembly could be examined).

Exit 3 is new. This previously exited `0` when no render path was available,
so a CI gate keyed on the exit code read "I could not look at anything" as
"nothing is wrong". That is a pass over an empty comparison set, and it is
the defect described in
[the check contract](../CONTRIBUTING.md#contributed-checks-must-be-able-to-fail).
If you gate on this check, treat anything other than `0` as not-clean.

Jinja2 is used for the local render path if importable, but it is optional.

## The contract every check here must satisfy

```bash
python3 checks/tests/test_check_contract.py
```

A check that cannot report a problem is worse than no check, because it emits
a clean verdict a reader will act on. Every check in this directory declares
two controls at module level, and the harness runs them:

- `NEGATIVE_CONTROLS`: inputs that **must** make the check fail. Writing one
  is how you find out your assertion was unfalsifiable.
- `EMPTY_SET_CONTROL`: the check run with nothing to compare, which must
  **not** report success.

Both run in-process against synthetic fixtures: no lane, no network, no
weights. The rule and the two defect shapes it catches (an assertion whose
sentinel is also in its own input, and a PASS over an empty comparison set)
are in
[CONTRIBUTING](../CONTRIBUTING.md#contributed-checks-must-be-able-to-fail).
If you add a check here, add its controls in the same PR.

Optionally a check may also declare `REGRESSION_ASSERTS`, a list of
`(name, callable)` where the callable returns `True` if a specific past defect
is still dead. That is a different thing from a negative control, which feeds
an input to the check and reads the check's own verdict, and it has its own
slot so that a guard does not have to be written inverted and make
`NEGATIVE_CONTROLS` misleading.

**Shell checks are covered too.** A non-Python check declares its controls in
a sidecar at `checks/tests/controls_<stem>.py`, and a non-Python check with no
sidecar fails the build. Discovery used to glob `*.py` only, so
`util_vs_power_tell.sh` escaped the contract entirely while the harness
reported `ALL PASS (8 checks conform)`: the right count over the wrong set.

The harness is itself mutation-proven: reintroducing the vacuous pass, making
a negative control unfailable, deleting either declaration, deleting a shell
check's controls sidecar, or a regression assert coming back false each fail
the build. A harness that cannot fail would be the very defect it tests for,
which is also why it refuses to pass over zero discovered checks.

## tool_args_dialect_probe.py (trap 43)

Does the chat template survive tool-call `arguments` arriving as a **string**? The OpenAI spec
says it is a string; templates that gate parameter expansion on `arguments is mapping` with no
`else` render an empty call when a framework replays a prior call with pre-serialized JSON.

Offline mode renders the template both ways and asserts the argument VALUE appears. The sentinel
is a city the conversation never mentions, deliberately: the first version of this check asserted
`"Paris" in rendered` while the user turn read "What is the weather in Paris?", so it could not
fail on the bug it exists to catch. That is the unfailable-assertion shape, and
`_control_sentinel_not_in_prompt` now guards against it returning.

Offline mode needs `jinja2`; live mode is stdlib.

## reasoning_budget_probe.py (traps 12, 16, 22)

The distribution half of trap 12 step 4. Sends the same prompt N times at a fixed ceiling and
reports the truncation rate and completion-token distribution; a pileup at exactly the cap is the
signature. Run at your real eval temperature, since the tail that bites at 0.6 is invisible at 0.

## dequant_fidelity.py (traps 44, 27)

Per-row cosine in float64 plus generation probes. Two assertions, because a flat cosine over a
billion-element `lm_head` overflows in float32 and can return > 1, and because the
capital-of-France probe passes on a wrong-layout dequant where a decimal comparison does not.

Exits 3, not 0, when zero tensors were compared. The first version started `worst` at 1.0 and
skipped tensors on shape mismatch, so a wrong-layout dequant whose shapes did not line up printed
`p01 1.0000 [None]` and passed: the vacuous-PASS shape, over the empty set.

Weight mode needs `torch` and `safetensors`; generation mode is stdlib.

## util_vs_power_tell.sh (traps 46, 10)

Run while a decode benchmark is in flight. High utilization at low power draw means busy compute
units that are not saturating tensor cores. Boards that report `[N/A]` power (Jetson and
GB10-class) now exit 3 rather than being coerced to 0 W, which previously reported SUSPECT
FALLBACK on every healthy lane on those boards.

## cache_hit_probe.py (trap 47)

Sends a growing conversation with a large stable prefix and reports TTFT per turn plus the
server-reported cached fraction. Requests `stream_options.include_usage`, without which the
`cached_tokens` corroboration never arrives on vLLM-dialect servers.

Flat TTFT with no server-side accounting is reported as **inconclusive (exit 3), not a finding**:
TTFT is a noisy proxy and a short prefix or a fast box hides a working cache. It is blocking only
when the server itself reports a cached fraction near zero.

## latency_reconciliation.py (trap 48)

Compares client-observed latency against the server's own figure and reports the unexplained gap.
The server total must include **prefill**: a decode-only field is declined rather than used, since
using it books prompt-processing time into the client gap and manufactures a false finding on long
prefills. Also runs the dual-stack resolution check that identifies the usual cause.

## tokenized_length_assert.py (trap 49)

Asserts the server's own prompt-token count against your target. Every probe carries a fresh salt,
including the growth probes, so no measurement is served from a prefix the check itself just
warmed. Pass `--repeat` to reproduce a known-bad harness.

## hidden_state_align.py (trap 50)

Before filing a "layer N exploded" bug against your own implementation, prove the two dumps mean
the same thing. Asserts dump counts, tries both index alignments, and checks whether a reported
collapse simply lands on `||norm_f.weight||`, which is what RMSNorm does to any input by
construction. Layers are compared in **index** order, and the excluded pair is the highest index,
the one that is supposed to disagree. Needs `numpy`.

## evidence_packet_preflight.py

Offline Evidence Packet v1 gate (research / measurement integrity). No network.

```bash
python3 checks/evidence_packet_preflight.py --packet docs/evidence-packet.examples/pass.example.json
python3 -m minefield evidence-preflight --packet path/to/packet.json
```

Exit 0 PASS, 2 FAIL, 3 HOLD/UNKNOWN (not a pass). Schema:
[`docs/evidence-packet.schema.json`](../docs/evidence-packet.schema.json).
Playbook: [`playbooks/agentic-research-integrity.md`](../playbooks/agentic-research-integrity.md).

## upstream_change_triage.py

Offline path→risk-surface prioritisation for mining. Never emits
`NEW_TRAP_FOUND` from diffs alone. Empty change list exits 3.

```bash
git diff --name-only BASE...HEAD | python3 checks/upstream_change_triage.py
```

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
