# Trap 37: a score that is zero for every arm is measuring your harness

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([reports/campaign_v3ja_v2/MT_SETA_POSTMORTEM_20260726.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/reports/campaign_v3ja_v2/MT_SETA_POSTMORTEM_20260726.md)
and [DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-07 and 2026-07-10 entries).**

**Status: reported by others.** Three independent instances in one campaign,
each with the cause isolated and recorded.

**Symptom.** A benchmark comes back at or near zero. Sometimes for every arm,
sometimes for one whole category across every arm. The run exited 0, the
error counter says zero, the artifacts are all present, and the obvious
reading is that the model cannot do the task. In all three of the finder's
cases that reading was wrong, and in one of them the harness reported
`infra_error_n=0` while being completely invalid.

His own one-line rule, from the postmortem:

> if all arms fail the same way, it is infrastructure until proven otherwise.
> Do not score it as ability.

**Mechanism.** Three different causes, one shape. A model-independent fault
applies equally to every arm, so it produces a clean, low, internally
consistent set of numbers, and the paired machinery keeps working on top of
it.

1. **The harness rejects valid output.** A multi-turn tool-calling gate
   hard-failed the final assistant turn as `parser_error:ValueError` whenever
   it contained no `<tool_call>` block. Models routinely emit their tool
   calls and then a final natural-language turn, so nearly every item died at
   the last step. Result: **~0/50 on all three arms**, with `infra_error_n=0`
   and exit 0. Offline re-parsing of the saved raw turns succeeded, and the
   execution logs already contained successful tool steps before the false
   stop. After the fix (missing or malformed tool markup means empty decode
   and advance the turn, not kill the item), the same protocol scored 16/50,
   17/50 and 15/50.

2. **The upstream scorer is broken for a subset.** A pinned official BFCL
   checker indexes a generic schema type `string` into a Java/JavaScript type
   map and raises `KeyError('string')`. **40 of 300 items scored a forced
   zero in both arms** (Java 0/26, JavaScript 0/14). The global paired result
   was still usable; any cross-language conclusion from it was not, and the
   finder said so rather than patching the checker locally to make the number
   look better.

3. **The run never happened.** A Terminal-Bench baseline sat at "0/24 solved,
   12 errors" and was read as model weakness. Dissection found five distinct
   faults and no measurement: the 12 "errors" were `SIGTERM` cancellations
   from a previous session that killed the run (`finished_at: null`); the
   harness was pointed at a dead SSH tunnel port; the model name in the
   request did not match `--served-model-name`; one failure was a transient
   Docker layer pull reset; and the remaining timeouts were the model being
   genuinely slow, not broken, with trajectory inspection showing it driving
   the task competently over 174 steps. Worth stating plainly: after repair,
   the honest baseline still measured **0/89**, with 55% of items timing out.
   The zero was real. It just had not been earned yet.

**Stacks and builds bitten.** Qwen3.6-35B-A3B and derivatives; a BFCL v4 AST
harness over pinned Gorilla `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` with
the `bfcl-eval` 2026.3.23 wheel; a Terminal-Bench 2.x run under Harbor with
terminus-2 against a local vLLM serve. The class is harness-level and applies
to any stack; agentic and tool-calling harnesses are the most exposed because
they have the most places to reject a valid turn.

**The check.** Score the **gold answers** through your own harness before you
score a model. If the reference solution does not come back at or near 100%,
your harness is what you are measuring. This one check catches all three
cases above, and it is cheap:

```python
# the single highest-value assertion in any eval harness
gold_score = harness.score(items, predictions=[it["gold"] for it in items])
assert gold_score > 0.98, f"harness scores gold at {gold_score:.0%}; fix the harness first"
```

The finder ran exactly this shape of control and it worked: a CPU fixture
sending BFCL's own gold call through his adapter, the pinned parser and the
pinned AST checker came back valid, which is what let him locate the
`KeyError` in the checker rather than in his model. He used the same
technique elsewhere as a positive control on a contamination matcher, to
prove a zero-hit result was genuinely clean and not a silently dead detector.

Two supporting checks: treat any all-arms-identical failure as infrastructure
until disproven, and never trust `infra_error_n == 0` as evidence of
validity, because a harness that mislabels a valid turn as a model error
reports zero infra errors while being entirely invalid.

**The fix.** Keep a gold-answer control in the harness and run it as a
preflight on every campaign, not once at build time. When a category or an
arm reads zero, dissect before you conclude: check exit status and
`finished_at`, check that requests reached the intended endpoint and model
name, re-parse saved raw output offline, and inspect a trajectory by hand.
Record invalid runs as negative controls rather than deleting them; the
finder retains his invalid run explicitly labelled "not a model verdict".

**Found.** 2026-07-07 (the Terminal-Bench baseline that was not a
measurement), 2026-07-10 (the upstream checker zeroing two languages) and
2026-07-26 (the multi-turn gate zeroing all arms at `infra_error_n=0`).

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who published the failure chronology in full, including the runs that
produced no usable number, rather than reporting only the run that worked.
Related: trap [16](16-finish-reason-is-not-a-failure-signal.md) and trap
[31](31-leftover-oracle-reranker.md), the same class in the opposite
direction (a harness fault that inflates rather than zeroes).
