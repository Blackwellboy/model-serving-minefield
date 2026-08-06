# Trap 36: the token cap is a per-arm handicap, not a constant

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-06 and 2026-07-07 entries).**

**Status: reported by others.** Truncation rates recomputed here from the
finder's published per-item JSON.

**Symptom.** Two things that look unrelated and are the same trap.

First: you score a **multiple-choice** benchmark on a reasoning model by
generation, and the result is garbage. Not subtly wrong, unusable: the model
spends its budget thinking and the answer letter never arrives. The finder
measured **81% of items truncated** on MMLU at `max_new=1536`. A number
built on that is measuring your cap.

Second, and much nastier because the run looks fine: on a **generative**
benchmark, the fraction of items that hit the cap is a property of the arm,
not of the harness. In the finder's published runs, on the same items and
the same cap, truncation ranged from 33.4% to 0.0% depending on which arm was
answering. Every arm is being scored under a different effective handicap and
nothing in the score reports it.

**Mechanism.** A cap is a constant in the config and a variable in the
measurement. How much of the budget a model spends before committing to an
answer is exactly the thing training changes, so any arm that reasons longer
gets truncated more, and any arm that stopped reasoning gets truncated less.
The finder hit this in its most misleading form: his coding-specialized arm
had learned to answer immediately (median 186 generated tokens, against 2,588
for the base model), which made it the only arm with **zero** truncation and
also the worst arm on every benchmark. Read through truncation counts alone,
the most damaged model looked like the healthiest run.

Recomputed here from his per-item JSON, identical items and cap per
benchmark:

| Arm | HumanEval truncated | MBPP truncated |
|---|---|---|
| base@k8 | 32/164 (19.5%) | 167/500 (33.4%) |
| base@k32 | 14/164 (8.5%) | 40/250 (16.0%) |
| agentic patch@k32 | 7/164 (4.3%) | 67/500 (13.4%) |
| coding patch@k32 | **0/164 (0.0%)** | **0/500 (0.0%)** |

His gpu-host runs show the same asymmetry from the other direction: on
HumanEval, one trained arm cut truncation from 42 items to 1 while its
correct count went **down**, 147 to 141. A separate checkpoint cut it from
49 to 0 with correct going 140 to 138. Truncation collapsed and accuracy did
not improve, which is the signature that the cap was never the binding
constraint for that arm.

For the multiple-choice half, the mechanism is simpler: with a reasoning
model, `<think>` overflows the budget and the answer token is never emitted.
The finder's fix was to stop generating at all and score by **choice
logprob** (apply the LM head to the hidden state and compare the option
tokens), which has no cap and therefore no truncation by construction. His
per-item JSON records `truncated_n: 0` on every choice-logprob benchmark and
non-zero counts on every generated one. A practical note from his
implementation: materializing full logits for this cost 64.5 GiB and OOM'd,
so he applied the head manually to the hidden states instead.

**Stacks and builds bitten.** Qwen3.6-35B-A3B revision
`995ad96eacd98c81ed38be0c5b274b04031597b0`, bf16 on HF transformers, and its
trained derivatives. MMLU/GSM8K/JMMLU by choice-logprob, HumanEval/MBPP by
generation, `max_new` 1024 to 1536, n=164/500/600. The class applies to any
reasoning model on any stack; it is the eval-harness face of trap
[12](12-empty-content-at-token-ceiling.md).

**The check.** Report the truncation count **per arm**, next to every
generated number, and refuse to compare arms whose truncation rates differ
materially. Two assertions catch both halves:

```python
# half 1: multiple choice should never be generation-scored on a reasoner
assert trunc_rate < 0.02, f"{trunc_rate:.0%} truncated: score by logprob, not generation"

# half 2: the cap must not be binding differently per arm
assert abs(trunc_rate_a - trunc_rate_b) < 0.05, \
    f"cap binds unequally: {trunc_rate_a:.0%} vs {trunc_rate_b:.0%}"
```

If the second assertion fires, raise the cap until both arms clear it and
re-run. If you cannot, publish the truncation table beside the scores so the
reader can see that two different measurements happened.

**The fix.** Score multiple-choice by logprob, never by generation, whenever
the model reasons. For generative benchmarks, set the cap from the
**longest-reasoning** arm's distribution rather than from a round number, and
verify after the run that it stopped binding. Note that this is not the same
advice as trap [16](16-finish-reason-is-not-a-failure-signal.md): that entry
says do not bucket cap-hits as failures, this one says do not let the cap
apply unequally in the first place.

**Found.** 2026-07-06 (MMLU generation scoring abandoned for choice-logprob
after think overflow destroyed the measurement) and 2026-07-07 (the
generation-length collapse that produced the zero-truncation arm).

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who recorded truncation counts on every arm of every run and published the
per-item JSON that makes the asymmetry checkable. Recomputation by
Blackwellboy.
