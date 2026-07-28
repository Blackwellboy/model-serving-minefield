# Q1: raising a MoE's inference top-k costs accuracy on a quantised build too

**Verdict: CONFIRM.** This promotes trap
[33](../traps/routing/33-moe-inference-topk-expansion-tax.md) to **reported by
others and reproduced here**. [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
keeps the **Found by** line; what this adds is a first-party run on different
weights, a different quantisation and a different stack.

**Status: reproduced here.** The evidence a stranger can act on is
`scripts/`, which ships beside this note: the item builder (which prints the
sha256 so a mismatch is loud), the arm-directory builder with its four proofs,
both runners, both analysers and the launch scripts. MMLU and the checkpoint
are both public, so the whole study re-runs on the reader's own lane without
asking us for anything.

**The answer sheets are deliberately not shipped in this repo.**
[MAINTAINING](../MAINTAINING.md#shipping-raw-data-in-the-repo) restricts
in-repo raw to calibration constants that other entries cite as a threshold,
floor or baseline, and Q1 is not one of those: it is a one-off measurement,
however good. The agreement floor it is quoted against **is** such a constant
and its raw does ship. Following our own rule here rather than making an
exception for our own result is the point.

Measured 2026-07-28. Plan of record: [the verification queue](2026-07-28-qwen36-a6b-verification-queue.md), item Q1. Criteria were pre-registered in that file before any arm ran and are not
restated here in altered form.

**Verdict: CONFIRM.**

Trap 33 was landed as reported-by-others from a research log whose every number is
bf16 under HF transformers. We hold the same base model family in an NVFP4 build.
Under our own rule that a different quant is a different unit under test, whether
the effect survives quantisation of the expert weights was open. It survives, at
roughly the reported magnitude, monotone across four values of k, in two
independent scoring protocols, on two independent passes each.

## The numbers

Generation-scored, MMLU n=600, the item set our published agreement floor was
measured on. Every arm is a separate server start; nothing is interleaved.

| k | pass 1 | pass 2 | vs k=8, pass 1 | vs k=8, pass 2 |
|---|---|---|---|---|
| **8** (shipped) | **518/600 = 86.33%** | **513/600 = 85.50%** | -- | -- |
| 16 | 501/600 = 83.50% | 500/600 = 83.33% | -2.83 pt | -2.17 pt |
| 24 | 494/600 = 82.33% | 495/600 = 82.50% | -4.00 pt | -3.00 pt |
| **32** | **491/600 = 81.83%** | **489/600 = 81.50%** | **-4.50 pt** | **-4.00 pt** |

Monotone in both passes, in the reported direction, with no exception.

**The pre-registered primary contrast**, k=8 versus k=32 at n=600 paired, pass 1:

| | |
|---|---|
| Delta | **-4.50 points** |
| Discordant pairs | 37 right-at-k8-wrong-at-k32, 10 the other way |
| Exact McNemar, two-sided | **p = 9.8e-05** |
| Against our published band | **3.46x** |

The independent pass-2 replicate: -4.00 points, 37/13 discordant, p = 0.000936,
3.08x the band.

### Effect size against our own floor, which is the point

A published paired delta on this stack is only meaningful against a measured
noise floor, and ours is **plus or minus 1.3 points at n=600** for MMLU-style
paired comparisons
([our agreement floor](2026-07-28-our-agreement-floor-greedy-not-reproducible.md)).
That floor is what licenses a non-interleaved design here: it found separate
server starts to be no worse than two passes of one process (restart pairs 97.50%
and 97.33% item agreement against a within-process 97.33%), so the fact that these
arms cannot be interleaved does not by itself inflate the comparison.

This study also re-measures that floor in its own run. Each k was served twice,
from two separate server starts:

| Same-k restart pair | Delta | Inside the 1.3 pt band |
|---|---|---|
| k=8 pass 1 vs pass 2 | -0.83 pt | yes, 0.64x |
| k=16 pass 1 vs pass 2 | -0.17 pt | yes, 0.13x |
| k=24 pass 1 vs pass 2 | +0.17 pt | yes, 0.13x |
| k=32 pass 1 vs pass 2 | -0.33 pt | yes, 0.26x |

Every same-k restart lands inside the band; every k=8-versus-raised-k contrast
lands outside it. The largest noise delta observed in this run is 0.83 points, and
the smallest effect delta is 2.17 points.

## Both scoring protocols agree, including his

The original measurement used choice-logprob scoring, which cannot truncate by
construction. Trap
[15](../traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md) warns that an
OpenAI-compatible lane may not expose echo plus logprobs at all, which would force
a generation-scored fallback.

**On this lane it does expose them.** `/v1/completions` with `echo: true` and
`logprobs` returns per-token logprobs over the echoed prompt, so the preferred
path was available and both were run:

| Protocol | k=8 | k=32 | Delta | Exact McNemar |
|---|---|---|---|---|
| Generation-scored, pass 1 | 86.33% | 81.83% | -4.50 pt | p = 9.8e-05 |
| Generation-scored, pass 2 | 85.50% | 81.50% | -4.00 pt | p = 0.000936 |
| Choice-logprob, pass 1 | 83.67% | 80.50% | -3.17 pt | p = 0.0145 |
| Choice-logprob, pass 2 | 83.83% | 80.17% | -3.67 pt | p = 0.0071 |
| *Reported, bf16, choice-logprob* | *84.33%* | *80.67%* | *-3.66 pt* | *p = 0.0021* |

The protocol-matched arms land on the reported bf16 figures closely enough that
the closeness should not be over-read from four runs, but the direction, the
magnitude and the significance all reproduce.

The choice-logprob protocol carries its own restart replicates: k=8 across two
server starts differs by +0.17 points, k=32 by -0.33 points. The plus-or-minus 1.3
band is **not** cited for these rows -- it was measured on the generation-scored
protocol and does not transfer -- but this protocol's own restart noise is
measured here and is far below the effect.

## Truncation, errors, unparsable

Trap [36](../traps/evaluation/36-token-cap-is-an-arm-level-handicap.md) requires
that truncation be under 2% on **both** arms or the comparison is abandoned.

| | Generation-scored | Choice-logprob |
|---|---|---|
| Truncated | 1 item across all 4,800 (0.02%); worst single arm 1/600 = 0.17% | 0 by construction |
| Errors | 0 | 0 |
| Unparsable | 0 | 0 |
| Mean completion tokens | 2.00 to 2.02 | not applicable |

The single truncated item is in the k=8 pass-1 arm, that is, in the arm that
scores **highest**. Truncation is therefore not carrying the effect: if anything
it costs the winning arm a fraction of a point.

## What differed between arms: one integer

vLLM reads the active-expert count from `config.json` at load, so each arm is a
separate server start against a separate model directory. Those directories were
built so that only one thing could differ:

- every file except `config.json` is a **hard link** to the same pinned snapshot,
  so the weight files in the k=32 directory are the same inodes as in the k=8
  directory -- byte-identical, not merely equal;
- `config.json` is a real file, and `diff` of the normalised JSON between the k=8
  arm and each raised arm is **exactly one line**, `num_experts_per_tok`;
- the k=8 arm's `config.json` is semantically identical to the pinned snapshot's,
  so the baseline arm is the shipped configuration reached through the same
  mechanism as the treatment arms rather than through a different one;
- the launch line is otherwise byte-identical across all arms, and the loaded
  value was read back out of the running container for every arm.

Proofs for all four statements are in `raw/`.

## Method, including where it is weaker than the original

**It is not interleaved, and it cannot be.** There is no runtime flag; the count
is a load-time property. This is a genuinely weaker design than a within-process
A/B and it is stated here as a limitation rather than buried. What makes it usable
is that the cost of non-interleaving was measured before this study ran and is at
the floor, and that this study reproduced that floor internally with four same-k
restart pairs.

**Execution order was alternated, not blocked.** Pass 1 ran the ladder upward and
pass 2 ran it downward, so no arm occupies a fixed position in the sequence:

```
k8_p1  k16_p1  k24_p1  k32_p1  k32_p2  k24_p2  k16_p2  k8_p2
lp_k8_p1  lp_k32_p1  lp_k8_p2  lp_k32_p2
```

The two highest-scoring arms are the first and the last generation-scored arm, so
a monotone drift over the session would not produce this pattern.

**Single node, single tenant.** All twelve arms ran on one machine, one at a time,
with nothing else resident. Trap
[35](../traps/evaluation/35-identical-weights-do-not-score-identically.md) asks
for arms to be serial on one machine; they were.

**Item set.** MMLU `all`/`test`, shuffled with seed 0, first 600, sha256
`c074b59b...`, verified on the node before the first arm and identical across
every arm because every arm reads the same file. This is the same set the
agreement floor was measured on, which is why the deltas can be quoted against
that floor at all.

## What this does not show

- **Not a mechanism test.** Renormalisation diluting the original top-8 while
  selection stays intact is the proposed explanation, and nothing here
  distinguishes it from other explanations. The gate weights were not
  instrumented.
- **Not a claim about NVFP4 versus bf16.** The two sets of numbers come from
  different stacks as well as different quantisations, so the small gap between
  our -3.17/-3.67 and the reported -3.66 is not attributable to quantisation.
  What is shown is that quantising the expert weights does **not** remove the
  effect.
- **Not a claim about the fix.** The alpha dial was not ported. Whether the
  correction transfers to a quantised serving stack is the obvious next question
  and is scoped separately.
- **One benchmark.** MMLU only. The original also reports the same direction on
  GSM8K; that was not run here.

## Reproducing

`scripts/` contains the item builder (which prints the sha256 so a mismatch is
loud), the arm-directory builder with its four proofs, both runners, both
analysers and the launch scripts. `raw/` contains all twelve answer sheets.

One trap worth carrying out of this run: with `echo: true`, asking for
`max_tokens: 1` appends the generated token to the echoed `tokens` list, so a
choice-logprob scorer that slices the continuation off the end of the base prompt
length silently scores the *generated* token instead of the choice. That scorer
returned 3/20 on a smoke set where chance is 5/20 and a correct scorer returns 17.
Use `max_tokens: 0`, assert that the choice request's token list starts with the
base request's, and put a floor under the smoke pass. The runner here does all
three.

## Independent re-derivation before publication

Every figure above was re-derived from the answer sheets by a checker written
separately from `scripts/analyse.py`, because a verifier that shares code with
whatever produced the numbers reproduces its bugs rather than catching them.
The independent checker re-derives the choice-logprob picks by argmax over the
raw per-choice logprobs instead of trusting the `pred` field the runner wrote,
and it asserts every published count, delta, discordant pair, p-value and
band-multiple in this document.

Result: all of them, plus the truncation accounting (1 truncated item in 4,800,
in the highest-scoring arm), 0 errors and 0 unparsable. Zero disagreements
between the re-derived argmax and the stored prediction on any of the 2,400
choice-logprob items.
