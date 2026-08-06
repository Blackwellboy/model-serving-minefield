# Verification queue: the qwen36-a6b traps (33 to 41)

Nine traps landed 2026-07-28 as **reported by others**, mined from
[@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s public research
log. Every measurement behind them is bf16 under HF transformers on RTX PRO
6000 class hardware. This file records what it would take to move any of
them to **reproduced here**, what lane it needs, and what result would
confirm versus refute.

Recorded before running anything, so the criteria cannot drift to fit the
result.

## Q1 (priority): trap 33 on NVFP4

**Claim under test.** Raising a MoE's inference top-k from its trained value
costs accuracy, silently, before any training. His measurement: MMLU 84.33%
at k=8 to 80.67% at k=32 (n=600, paired, exact p=0.0021), monotone through
k=16 and k=24, and the same direction on GSM8K (89.33% to 86.50%, p=0.016).

**Why it is worth running here.** Every one of his numbers is bf16. We have
the same base model in a **different build** (NVFP4), which the registry's own
preamble rule 2 says to treat as a different unit under test. NVFP4 quantizes
the expert weights, and the trap's mechanism is about how much mixture weight
the tail experts receive, so a quantized tail is a genuinely open question
rather than a formality. A confirmation makes this the registry's first
cross-build MoE-routing entry; a refutation scopes the trap to unquantized
serving, which is equally useful.

**Lane.** Our Qwen 3.6 35B-A3B NVFP4 lane. Lane state must be verified live
before anything: it was parked 2026-07-27 and the test lanes were left
mid-study. **Unparking or restarting a lane is an owner decision, not the
runner's.**

**The check.** MMLU, n=600, shuffle seed 0, the same 600 items in both arms,
paired, arms run serially on one machine (trap
[35](../traps/evaluation/35-identical-weights-do-not-score-identically.md)).
Two arms: `num_experts_per_tok = 8` (shipped) and `= 32`.

**Known obstacle, stated up front.** There is no runtime API flag for this.
vLLM reads the active-expert count from the checkpoint's `config.json` at
load, so each arm is a **separate server start** against a separate model
directory (or an edited copy), not two requests. That also means the two arms
cannot be interleaved, which is a weaker design than his and should be noted
in any result.

**DESIGN UNBLOCKED 2026-07-28 by Q2, which measured what that obstacle costs:
nothing detectable.** Restart pairs agreed at 97.50% and 97.33% against a
within-process pair at 97.33%, and cross-machine pairs straddled it. Separate
server starts, on one node or across two, sit at the same floor as two passes
of a single process. The weaker-design caveat still belongs in the write-up as
a statement of method, but it is no longer a reason to discount the result.

Two further consequences for Q1:

- The reported effect is 3.67 points, roughly **2.7x** the measured 1.3 point
  band at n=600, so it is detectable at the planned n.
- The **Confirm** clause below allows "a significant but much smaller effect"
  as a directional confirmation. That clause now has a floor under it: an
  effect near 1 point at n=600 is inside the noise and must not be reported as
  a confirmation without raising n.

Both nodes now hold the identical checkpoint (revision `491c2f1e`) and the
identical image (`a720df3e84a8`), so the two arms can be split across nodes if
that is convenient, or kept serial on one. **Not yet run.**

**Second obstacle.** He scored MMLU by choice-logprob, which has no
truncation by construction. Our lane is an OpenAI-compatible endpoint, and
per trap [15](../traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md) it
may not expose echo+logprobs at all. Two viable paths, in order of
preference:

1. Score locally against the NVFP4 weights with a transformers-side
   logprob scorer, matching his protocol. Cleanest, most work.
2. Generation-scored with thinking **off**, a single-letter answer
   instruction, and a small cap; then enforce trap
   [36](../traps/evaluation/36-token-cap-is-an-arm-level-handicap.md)'s
   assertion that truncation is under 2% on **both** arms, and abandon the
   run if it is not.

Do not run generation-scored MMLU with thinking on. Trap 36 exists because
that produced 81% truncation and an unusable number.

**Confirm.** k=32 scores significantly below k=8 on the same items, paired,
same sign as his result. Magnitude within roughly a point of his 2.8 to 3.7
pt range would be a clean cross-build replication; a significant but much
smaller effect is still a confirmation of direction and should be reported as
such.

**Refute.** The paired delta is null or positive at n=600. That would scope
trap 33 to unquantized serving and is a publishable negative; it would land
here in `mining/`, not as a silent deletion.

**Do not conclude either way if** truncation differs materially between arms,
the two arms ran on different hosts, or the item sets differ.

**Cost estimate.** Two server loads on a ~35B NVFP4 checkpoint plus 1,200
scored items. Roughly 2 to 4 GPU-hours of lane occupancy including weight
loads and a smoke pass, plus setup for whichever scoring path is chosen; path
1 is most of the work and is a day's job, path 2 is an afternoon. No new
weights to download.

**Stretch, only if Q1 confirms.** His alpha dial is a ~20-line gate forward
hook. Porting it to a vLLM MoE gate would let us test whether the *fix*
transfers to NVFP4, which is the part practitioners would actually use. This
is a code change inside a serving stack and should be scoped separately, not
bolted onto Q1.

## Q2: trap 35, our own cross-machine agreement floor

**Claim under test.** Identical weights on identical items agree on only
98.7% of items across two machines, so effects smaller than the resulting
score spread are noise.

**The check.** One model, one item set, two lanes, serial. Report per-item
agreement and the score delta, not just the score.

**Confirm / refute.** There is nothing to refute here; the output is *our*
number. The point of running it is that we currently publish paired deltas
without having measured our own floor. Whatever it is, it becomes the minimum
detectable effect we cite.

**Cost.** Under an hour on any two lanes already serving the same weights.
Cheapest item in this queue and the one with the broadest payoff, since it
calibrates every A/B we publish.

**ANSWERED 2026-07-28.** Result:
[Greedy is not reproducible on this stack](2026-07-28-our-agreement-floor-greedy-not-reproducible.md).
Pooled **3513/3600 = 97.58%** item agreement across six pairings of four
identical-configuration runs (MMLU n=600, greedy, concurrency 1, prefix caching
off, Qwen3.6-35B-A3B NVFP4 on two GB10 nodes). The cross-machine pairs (97.17%,
97.83%, 98.33%) straddle the within-process pair (97.33%), so machine identity
is not the variable. Speculative decoding ruled out. Trap 35 promoted to
reproduced-here. **Adopted calibration: plus or minus 1.3 points at n=600 for
MMLU-style paired comparisons**, an accuracy delta over four-way
multiple-choice items that does not transfer to binary-outcome results. Cost
came in near the estimate; the unplanned expense was copying the checkpoint and
image to the second node, which is now sunk and benefits Q1.

## Q3: first-N subsetting bias (candidate, not yet an entry)

**Why it is not an entry.** He records that taking the first N MMLU items
gives a subject-skewed subset because the source is ordered by subject, and
he fixed it with `shuffle seed 0`. He never published the magnitude, so per
CONTRIBUTING's evidence bar this is a mechanism without a measurement: an
issue, not an entry.

**The check.** Same model, same n, two item sets: first-N unshuffled versus
first-N after a seeded shuffle. Report the subject distribution of each and
the score delta.

**Confirm.** The subject distribution of the unshuffled subset is visibly
skewed **and** the score delta exceeds the agreement floor from Q2. Then it
becomes an entry.

**Refute.** The delta sits inside the Q2 noise floor, in which case it is a
tidiness rule and not a trap, and it stays here.

**Threshold now defined.** Q2 puts that floor at **1.3 points at n=600**. The
score half of this check confirms only if the delta exceeds it.

**Cost.** The subject-distribution half is free and needs no GPU: load the
benchmark and count. Run that first; only spend GPU on the score half if the
distribution is actually skewed.

## Zero-cost desk checks (no lane needed)

- **Trap 38 on our stacks.** Render one conversation through
  `apply_chat_template(..., add_generation_prompt=True)` for each model we
  serve and read the tail of the string. If it ends with an opening think
  tag, any offline pipeline we run against that model needs the prefill and
  the recombination. Minutes, no GPU.
- **Trap 40 against any contamination screen we run.** Print the top matching
  grams by frequency and the run-length distribution. If one gram explains
  most of the hits, the screen is measuring a serialization format.

## Not queued

Trap 34 (degraded baseline), 37 (uniform zero) and 41 (static batching) are
methodology traps whose mechanism is arithmetic or architectural rather than
hardware-dependent. There is nothing for our lanes to add; they are checks to
adopt, not claims to replicate. Trap 39 was observed on a multi-GPU
workstation with a reserved device; we could reproduce it, but deliberately
mis-placing a model to confirm that it returns garbage is not a good use of a
lane.

## Q1 answered 2026-07-28: CONFIRM

Q1 ran against the Qwen 3.6 35B-A3B NVFP4 lane under the criteria pre-registered above, which are not restated here in altered form. The verdict is CONFIRM and trap [33](../traps/routing/33-moe-inference-topk-expansion-tax.md) is now **reported by others + reproduced here**. Numbers, both protocols, the truncation accounting and the limits are in [the Q1 writeup](2026-07-28-trap-33-q1-nvfp4-confirmed.md).

The other items on this page are unchanged, including the first-N subsetting-bias candidate still held for want of a measured magnitude.
