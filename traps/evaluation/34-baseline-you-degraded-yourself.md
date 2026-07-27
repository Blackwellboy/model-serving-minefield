# Trap 34: winning against a baseline you degraded yourself

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([reports/DATA_QUALITY_STRATEGY_20260711.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/reports/DATA_QUALITY_STRATEGY_20260711.md),
section 3).**

**Status: reported by others.** The flip was recomputed here from the
finder's published per-item JSON and reproduces his p-values exactly.

**Symptom.** Your change wins. The paired test is significant, the CI
excludes zero, the protocol is clean, both arms ran on identical items with
identical sampling. Then someone asks what the baseline was, and it turns
out the baseline is a configuration **you** created and that nobody ships:
a top-k you raised, a quant you picked, a template you patched, a token cap
you set. You did not beat the model. You beat your own handicap.

This one does not announce itself, because every methodological box is
genuinely ticked. Trap 17 catches arms that differ in more than the variable
under test; this one bites when the arms are perfectly controlled and the
**reference point** is wrong.

**Mechanism.** Arithmetic. If your config change costs the model 3 points
before you start, then a change that recovers 2 of them measures as a
significant 2-point win against that degraded reference and as nothing at all
against the shipped model. Same arm, same items, same test, two different
conclusions, and only one of them is a claim about capability.

The finder's case, recomputed here from his published per-item JSON (`n=164`
HumanEval, identical items, exact paired McNemar). One arm, an
agentic-trained expert patch at k=32:

| Compared against | Delta | Discordant | Exact p | Reads as |
|---|---|---|---|---|
| base@k32 (the degraded reference) | **+6.10 pt** | 5/15 | **0.041** | significant win |
| base@k8 (what actually ships) | +3.66 pt | 9/15 | 0.308 | no effect |

The degraded reference was the finder's own k=32 setting, which costs this
model roughly 3 points before any training (trap
[33](../routing/33-moe-inference-topk-expansion-tax.md)). Against it he had
"significant wins" on two benchmarks. Against the shipped k=8 model his
honest summary was two draws and two losses, and he wrote it that way.

**Stacks and builds bitten.** Qwen3.6-35B-A3B revision
`995ad96eacd98c81ed38be0c5b274b04031597b0`, bf16 on HF transformers,
HumanEval/MBPP by generation and MMLU/GSM8K by choice-logprob, n=600/500/164,
shuffle seed 0, paired on identical items. The class is stack-independent:
any A/B whose reference arm is a non-default configuration is exposed,
including quantized-vs-quantized comparisons where nobody measured the
unquantized model, and thinking-on-vs-off comparisons at a token budget that
starves one arm.

**The check.** Write down the configuration of your reference arm and ask one
question: **would anyone serve this?** If the answer is no, it is not a
floor, it is a handicap. Then report both numbers. The finder's standing
rule, which is the cheapest possible fix:

> Every verdict reports against base@k8 **and** against base@k32.

Concretely, before publishing any delta:

1. Name the shipped default for every knob you touched (top-k, quant,
   template, sampling, budget).
2. If your reference differs from that default on any knob, add a third arm
   at the default and report against it too.
3. If you cannot run the third arm, say "measured against <config>, not
   against the shipped default" in the same sentence as the number.

**The fix.** Make the shipped configuration the reference arm. Keep the
degraded arm if it is informative, but as a third column, never as the
denominator of the headline. A win that exists only against your own
handicap should be reported as what it is: recovery of a cost you introduced.

**Found.** 2026-07-07 (the measurement that showed the flip) and 2026-07-11
(codified as an explicit eval-gate rule after an adversarial review flagged
the floor as too low).

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who caught this in his own campaign, corrected the floor, and re-reported
every prior verdict against both references rather than deleting the old
ones. Recomputation from his per-item JSON by Blackwellboy. Related:
trap [17](17-per-arm-recommended-sampling-confound.md) (arms differing in
more than the variable) and trap
[33](../routing/33-moe-inference-topk-expansion-tax.md) (the config change
that created the handicap here).
