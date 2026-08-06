# Verification queue: the Hikari-knowledge corpus, and one hypothesis of our own

[@Hikari_07_jp](https://github.com/hikarioyama/Hikari-knowledge) published a
47-node English knowledge graph on 2026-07-28 (MIT). It is a different corpus
from the `qwen36-a6b` research log that supplied traps 33 to 41: only one of
those nine is restated in it. This file records what it would take to move
candidates from it into this registry, what lane each needs, and what result
would confirm versus refute.

**Criteria are recorded before running anything, so they cannot drift to fit the
result.** Nothing below has been drafted as an entry. Nothing below has been run.

Ordering is by value to a stranger, not by how interesting it is to us, with one
exception: **T0 is first because it costs no lane at all.**

---

## T0 (do first, zero lane cost): stratify the trap 33 answer sheets we already have

**Claim under test.** Our trap 33 NVFP4 confirmation is a pooled MMLU result at
n=600 with no strata. Whether the top-k expansion tax is uniform across subjects
or concentrated in a few is unknown, and we did not ask.

**Provenance.** [Hikari, `nodes/methodology/per-domain-eval-discipline`](https://github.com/hikarioyama/Hikari-knowledge).
His rule: an aggregate is a weighted average, and a pooled score can conceal a
regression in a smaller but important domain. Ours is pooled.

**Lane.** **None.** The twelve answer sheets are already on disk at
`~/staging/trap33-nvfp4-q1/raw/`, and MMLU items carry their subject. This is a
re-analysis, not a re-run.

**The check.** Re-score the existing k=8 and k=32 sheets stratified by MMLU
subject. Report the per-subject paired delta alongside the pooled -4.50.

**Confirm.** The effect is broadly distributed: most subjects move in the
reported direction and no single subject carries a disproportionate share of the
37 discordant pairs. This strengthens the existing entry and costs nothing.

**Refute.** The effect concentrates in a small number of subjects. That does not
overturn the result, but it changes the claim from "raising top-k costs accuracy"
to "raising top-k costs accuracy on these subjects", and the entry must say so.

**Either way**, the stratified table gets added to the writeup and the pooled
number stops standing alone. Cheapest item in this queue by a wide margin.

---

## T1 (priority, needs a lane): does TP>=2 change greedy accuracy with no error?

**Claim under test.** Tensor parallelism at TP>=2 changes the reduction order of
the MoE router logits across ranks. Where two experts sit close together at the
top-k boundary, a floating-point difference below any tolerance flips which
expert is selected, the forward pass takes a different path, and the output
changes. No warning, no error, no failed health check. If the flipped items are
not symmetric in difficulty, the result is a **paired accuracy delta produced by
a parallelism setting**, which nothing in this registry currently covers.

**Provenance, stated honestly.** This is **not** from Hikari's corpus. I searched
it at `3a67844` for tensor parallelism, nondeterminism, router noise and gate
noise: his `gpu-p2p-iommu-pt` is about peer-DMA correctness, and his
`step37-single-stream-ceiling` observes that "greedy divergence under MTP was too
nondeterministic for quality attribution", which is MTP depth rather than TP rank
count. The closest published work is **ours**: trap 35 (identical weights do not
score identically), trap 91 (concurrency nondeterminism has a prompt-length
floor) and trap 94 (temp-0 reproducibility is architecture-dependent). This
belongs in the queue because it is testable here and we run TP=2 pairs, not
because he reported it. **Do not credit him for it.**

**Why it matters if true.** It would mean every cross-configuration accuracy
comparison in this registry that differs in TP has an uncontrolled variable, and
that a TP=2 serving deployment can score differently from the TP=1 evaluation
that qualified it. It also gives the top-k expansion tax a second, independent
mechanism arriving at the same observable from the opposite direction: trap 33
changes *how many* experts are selected deliberately, this changes *which* ones
are selected accidentally.

**Lane.** A test node held under our standing test-node authorization, able to
hold the same weights at **both** TP=1 and TP=2, so the model must fit on a
single GPU. Claim the lane before, release it after, and verify the restore with
a live generation. **The production tensor-parallel lane is not available
for this and must not be considered for it:** it is request-level only and never
goes down.

**Rough cost.** Two server starts per arm, n=600 MMLU, temperature 0, plus two
restart replicates per arm for the floor. Call it six arms, a few hours of one
test node, no build work. Cheap.

**The check.** Same weights, same items, same sampler, temperature 0.
Arm A: TP=1. Arm B: TP=2. Both restarted twice for the within-arm floor.
Report **per-item agreement**, not just the score. Then, on the disagreeing
items, extract the router top-k margin and test whether disagreements concentrate
where the margin is smallest.

**Confirm** requires all three:
1. TP=1 vs TP=2 per-item disagreement materially exceeds the TP=1 restart-to-restart
   floor measured in the same run;
2. the accuracy delta exceeds our published plus-or-minus 1.3 point band at n=600;
3. disagreements concentrate on small-router-margin items rather than being
   uniformly distributed, which is what makes it a *mechanism* rather than a
   restatement of trap 35.

**Refute.** TP=1 vs TP=2 disagreement sits inside the restart floor. That is a
publishable negative and closes the question.

**Partial.** Disagreement exceeds the floor but the accuracy delta does not, or
the margin correlation is absent. Then it is nondeterminism without an accuracy
consequence, which is trap 35's existing scope and does not earn a new entry.

**Known obstacle.** Extracting router margins needs instrumentation the serving
stack does not expose by default. If that proves expensive, criteria 1 and 2 are
still a complete result and criterion 3 can be deferred, but the entry must then
say the mechanism is proposed rather than shown.

---

## T2: does the sparse-KV over-allocation pattern reproduce outside DSv4?

**Claim under test.** For sliding-window or sparse-attention models, a large
`max_num_batched_tokens` reserves far more KV-related state than the real
attention window needs, so long-context capacity looks VRAM-bound when it is
configuration-bound. His worked example moves a 17,300-token pool to a 1,925,540-
token pool by *lowering* `max_num_batched_tokens` to 512 and raising
`max_model_len` to 1,048,576, preserving weights, quality and decode speed while
slowing long-prompt prefill.

**Provenance.** [Hikari, `nodes/serving/vllm-sparse-kv-overalloc-pattern`](https://github.com/hikarioyama/Hikari-knowledge),
`confidence: mixed`. He labels the DSv4 case measured and **explicitly labels
broader recurrence a hypothesis**. That is the hypothesis this item tests.

**Why it matters if true.** This is the highest-value item here for someone who
is not us. The wrong conclusion it prevents is "my card is too small", which is
expensive and acted on immediately.

**Lane.** Any vLLM sparse-attention or sliding-window lane on a test node. Needs
a model whose real window is documented so it can be derived rather than guessed.

**Rough cost.** Two server starts and a capacity read, plus one long-prompt
prefill timing to confirm the stated trade-off. Very cheap; no eval run needed
for the capacity claim itself.

**The check.** Same checkpoint, same node. Arm A: stock settings. Arm B:
`max_num_batched_tokens` reduced toward the real window, `max_model_len` raised.
Read the **actually allocated** pool from the server after restart, not the
requested value. Then a quality probe on both arms from the same binary.

**Confirm.** Pool capacity increases materially on a model that is not DSv4, with
weights, quality and decode speed preserved and the prefill slowdown present and
quantified. Promotes his hypothesis to reproduced-here on a second model.

**Refute.** Capacity does not move, or moves at a quality or decode cost he did
not report. Either scopes the pattern to his configuration, which is equally
useful and should be published as such.

**Note.** His own gotcha applies to us: derive the real window from the model or
cache specification, not from the model's name, and include **every** cache
family in the memory breakdown, because a state cache can dominate the usual KV
estimate.

---

## T3: does the FlashInfer JIT cache serve a stale binary after a header change?

**Claim under test.** The FlashInfer JIT cache key can reuse a stale compiled
binary after headers change, so a rebuilt kernel silently does not run.

**Provenance.** [Hikari, `nodes/serving/nvfp4-kv-cache-sm120-vllm`](https://github.com/hikarioyama/Hikari-knowledge), gotchas section.

**Why it matters if true.** It is a false-healthy instance in our own taxonomy: a
build that reports success and serves the previous kernel. Every kernel A/B we
run on a JIT path is exposed to it.

**Lane.** Any lane where we build a FlashInfer path. We have several.

**Rough cost.** Near zero. Change a header in a way that must change behaviour,
rebuild without clearing the cache, and check whether the behaviour changed.

**Confirm.** The rebuilt kernel serves old behaviour until the JIT cache is
cleared. Entry, and a line in the container build playbook.

**Refute.** The cache key covers headers on our version. Then it is version-scoped
and should be recorded as such rather than dropped.

---

## T4: does a successful KV pool allocation still OOM on the first real request?

**Claim under test.** Unaccounted scratch space can cause an OOM *after* an
apparently successful pool allocation, so a server that started cleanly can die
on its first real request.

**Provenance.** [Hikari, `nodes/serving/nvfp4-kv-cache-sm120-vllm`](https://github.com/hikarioyama/Hikari-knowledge), gotchas section.

**Why it matters if true.** It is the sharpest possible instance of our existing
rule that **readiness is a completed generation, not an endpoint answering**. If
it reproduces, it stops being a doctrine sentence and becomes a measured example
with a failure mode attached.

**Lane.** Any lane pushed near its memory ceiling on a test node. Deliberately
provoking an OOM means the lane must be one we own for the session.

**Rough cost.** Low, but it is a destructive test by design and needs the lane
borrow discipline followed exactly.

**Confirm.** Startup succeeds, pool allocation is reported, first real request
OOMs. Strengthens the readiness rule with a measured case.

**Refute.** Cannot provoke it on our stack at any utilisation we would serve.
Record as not-reproduced-here and leave his node credited as the origin.

---

## T5: gate GPU peer DMA before enabling TP collectives

**Claim under test.** Incorrect GPU peer DMA yields plausible but corrupted data
with **no runtime error**, so P2P-dependent collectives should be gated on a
two-direction transfer correctness check after any boot or platform change.

**Provenance.** [Hikari, `nodes/methodology/gpu-p2p-iommu-pt`](https://github.com/hikarioyama/Hikari-knowledge).
His `iommu=pt` resolution is configuration-specific and he says so; the **gate**
is the portable part and is what we would adopt.

**Why it matters if true.** We run TP=2 pairs. A silent corruption path under
collectives is the worst class of failure we could carry, because every
downstream measurement inherits it without a signal.

**Lane.** Our TP=2 hardware. **Read-only on the production lane:** the check is a
small tensor copy and can in principle run at request level, but any form of it
against production is an owner decision, not a runner's. Prefer a test node.

**Rough cost.** Minutes. It is a tensor copy and a sum comparison.

**Confirm.** The gate is implementable on our fabric and passes, in which case it
becomes a preflight rather than an entry. If it ever **fails**, that is a serious
finding about our own fabric and takes priority over everything else in this file.

**Refute.** Not applicable; this one is adopted as a check regardless of outcome.
It earns a registry entry only if it catches something.

**Note.** His own caveat carries: the sum check detects gross corruption and is
not a byte comparison. Do not oversell what a passing gate proves.

---

## T6: in-graph K=1 self-speculation versus batched K>=2 under CPU offload

**Claim under test.** Two of his nodes read as a pair. Conventional batched
verification at K>=2 **loses** on CPU-offloaded MoE, because expert reads scale
close to linearly with verification width, while **in-graph K=1 self-speculation
wins** in the same regime by avoiding a separate draft forward. His measured
figures: no speculation 5.93 tok/s, n_max=8 4.78, n_max=3 4.40 on a GLM-5.1
llama.cpp partial offload; and +18.8% for GLM-5.2 in-graph K=1.

**Provenance.** [Hikari, `nodes/specdec/spec-decode-cpu-moe-dead`](https://github.com/hikarioyama/Hikari-knowledge)
(tombstone) and `nodes/serving/glm52-mtp-selfspec`. The **pairing** is the
insight; either node alone is weaker.

**Why it matters if true.** It inverts the usual "more speculation is better"
intuition based on where the experts live, and we run llama.cpp partial-offload
lanes where this applies directly.

**Lane.** A llama.cpp partial CPU-MoE offload lane on a test node.

**Rough cost.** Moderate. Three arms and a throughput measurement, following the
soak and A/B playbooks for warm-up and replicate count.

**Confirm.** Wider verification is slower than no speculation on our offload
lane, in the reported direction. Reproduces the tombstone on a second stack.

**Refute.** Wider verification wins on our offload configuration. That is more
interesting than a confirmation and should be published with the offload split
stated exactly, since his result is explicitly scoped to his layer split.

**Caution.** His acceptance and throughput figures here are report-level and he
labels them so. Do not quote them as measured.

---

## Not queued, and why

- **All 5 steering nodes**, and 3 of 4 training nodes. Activation steering and
  training-side work. Careful material, wrong registry.
- **All 14 paper bridges.** A reading list, not findings.
- **The 3 `dspark-*` nodes.** His own draft-head training programme, conditional
  on his recipe and hardware, and he says so. No portable trap in them.
- **`alpha-dial-k-expansion`.** Already held as trap 33, including his full alpha
  sweep. The only genuinely new content in it is the head-eight mixture share
  series and the effective-k percentiles, which are not independently useful.
- **`serve-bench-discipline`.** Adopted as method rather than queued as a test;
  see the replicate standard in
  [before you publish an A/B](../playbooks/before-you-publish-an-ab.md) and
  [reading a soak](../playbooks/reading-a-soak.md).
