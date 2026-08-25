# SGLang

**Measured here:** yes (served first-party and contributor-measured on GB10)


**4 entries name SGLang** in their evidence surfaces (see
[how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)).

This page began as a zero-entry page, when "no page" and "no entries" read the
same from outside and meant different things. **That is no longer the case:
four entries now name SGLang.** Three are contributor-measured request/template
findings; [124](../traps/runtime/124-dgx-spark-gb10-stuck-low-power-state-under-load.md)
is a first-party NVIDIA DGX Spark / GB10 platform low-power state that degraded SGLang throughput
on the measured unit without being SGLang-specific. The zero-entry caveat is
kept below only as the reason the page was created, not as a description of the
stack today.

## Where this stack actually stands

Three things have happened. The newest one is published and closes two of the
stack's pre-registered questions.

**It is not infeasible on this hardware class.** The packaging question was
settled on 2026-07-28 and the working is published:
[SGLang on GB10, feasibility](../mining/2026-07-28-sglang-on-gb10-feasibility.md).
The arm64 wheel exists, `sglang[all]` resolves cleanly on CUDA 13, and the
open risk named there was whether `sm_121` appears in the torch arch list.
That note is packaging only. No server was started for it.

**A server has since been started, first-party, and the results are not
published here yet.**
[CONTRIBUTING](../CONTRIBUTING.md#where-coverage-is-thin) carries the dated
correction: SGLang has been brought up on our own hardware, the
reasoning-parser null-content report that was the standing open ask was tested,
and its disposition is written and awaiting publication.

**A contributor then ran the control SGLang session through generation and
ran the doctor against both endpoints.** The
[DGX Spark field note](../mining/2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md)
records the pinned models, package set, launch conditions and response shapes.
Q7 is refuted under its pre-registered first-generation criterion: the
non-Laguna NVFP4 control generated first, then Laguna loaded its
`CompressedTensorsW4A4Nvfp4MoE` path and generated a correct first token. Q8 is
confirmed: two doctor runs completed with meaningful bounded verdicts. Longer
Laguna output was degraded, so none of this is a correctness or production
support claim.

The blocked-candidate records from before that session are still worth reading
for what they rule out and why:
[R2 blocked, not testable](../mining/2026-07-27-r2-blocked-not-testable.md)
and
[the blocked llama.cpp candidates, adjudicated](../mining/2026-07-28-r2-llamacpp-queue-dispositions.md).

## Upstream reports that do not change the measured count

A 2026-08-25 pass over SGLang v0.5.18 promoted nine source-level mechanisms to
the separate [`upstream/`](../upstream/) tier. **None has been reproduced here,
none counts toward the four measured SGLang entries above, and none counts
toward Doctor coverage or the canonical registry total.** They are useful
because each points to a merged upstream fix and gives a confirmation/refutation
procedure for someone with the affected stack.

The new reports cover:

- [U27](../upstream/U27-sglang-dsv4-spec-draft-over4-stale-compress-state.md):
  speculative DSV4 draft counts above four could leave stale compressed state;
- [U28](../upstream/U28-sglang-prefill-graph-stale-track-prefix-cache.md):
  stale captured Mamba track rows could make a prefix-cache hit restore another
  request's conv state;
- [U29](../upstream/U29-sglang-unified-triton-deterministic-virtual-physical-kv.md):
  unified memory + Triton + deterministic inference could mix virtual and
  physical KV locations;
- [U30](../upstream/U30-sglang-unified-page-recycle-stale-tail.md) and
  [U31](../upstream/U31-sglang-int32-slot-stride-wrap-recurrent-state.md):
  two independent unified-memory/DSPARK corruption mechanisms, recycled page
  tails and int32 slot-stride wrap;
- [U32](../upstream/U32-sglang-spec-stop-eos-crosses-length-cap.md): a
  speculative accept run could leak tokens after an in-budget EOS/stop when the
  same step crossed the length cap;
- [U33](../upstream/U33-sglang-dflash-missing-is-causal-default-drift.md):
  missing DFlash causality metadata could change semantics after a runtime
  default moved;
- [U34](../upstream/U34-sglang-dflash-dcp-draft-kv-budget-undercount.md): exact
  DFlash draft-KV budgeting could omit the DCP replication factor; and
- [U35](../upstream/U35-sglang-fa4-blackwell-resolved-deps-still-fail-compile.md):
  a dependency pair could resolve successfully and still make FA4 fail to
  compile on Blackwell.

The source-mining and dedupe record is
[here](../mining/2026-08-25-sglang-upstream-promotion.md). Treat these as
upstream reports, not as evidence that current SGLang releases or every model
still carry the behavior.

## What to check anyway, from the cross-stack classes

Three of these are now SGLang findings: orphan `</think>` in the absent-kwarg
arm ([02](../traps/template/02-orphaned-think-close-tag.md)), empty content at a
real token ceiling ([12](../traps/evaluation/12-empty-content-at-token-ceiling.md))
and silent acceptance of an invented top-level request field
([77](../traps/reasoning/77-only-one-request-field-is-validated.md)). They are
all contributor-measured, conditions as reported. The remaining classes are
still cross-stack checks rather than SGLang findings.

**1. Read every plausible spelling of the reasoning field.** The name of the
field carrying chain-of-thought is a property of the serving stack, not of the
model, and one server has carried three names split by route
([trap 01](../traps/reasoning/01-reasoning-field-two-names.md), **Core**). Use
`.get` on `content` as well: an empty channel is sometimes an absent key
rather than an empty string.

**2. Send your thinking-off switch, then check that thinking is actually
off.** Do not check the status code. A request field that a server does not
recognise is very often accepted, returns 200, and changes nothing, so a whole
thinking-off arm gets measured on a thinking lane
([trap 77](../traps/reasoning/77-only-one-request-field-is-validated.md),
**Core**). Separately, a server-side off switch can be a default that a client
kwarg overrides
([trap 29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)).

**3. Send one request that will hit the token ceiling, and look at what comes
back.** `finish_reason: length` with empty content scores as a capability
collapse rather than as a budget artifact, and there is no single ceiling that
makes it go away
([trap 12](../traps/evaluation/12-empty-content-at-token-ceiling.md), **Core**;
bucketing rule in [16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md)).

Two more that cost the most elsewhere and have no reason to spare a new stack:
prior-turn reasoning stripped from history
([04](../traps/template/04-history-reasoning-stripping.md), **Core**, the
registry's most dangerous entry because its symptom is a publishable number),
and the quant label not being the kernel path
([10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md),
**Core**).

## What the doctor can do here

The [doctor](../doctor/) now has a field run against SGLang 0.5.16. It completed
14 requests against each of two models and produced meaningful verdicts. That
run also found a reporting defect: SGLang exposes neither `/props` nor
`/version`, so the report fell into the anonymous OpenAI-compatible bucket even
though `/v1/models` said `owned_by: "sglang"`. The doctor now recognises that
response shape, with a regression fixture. Its own README remains explicit
that a clean count covers only the numbered checks it actually executed and is
never a bill of health.

## Where a report would help most

The highest-value next report is a controlled fix for the degraded Laguna
output recorded in the field note. The same lane emitted a Mistral-regex
tokenizer warning, selected compressed-tensors NVFP4, and produced degraded
text; no single cause was isolated, so the mechanism remains open. A report
does not need a writeup or confidence that the first hypothesis is right. Four
plain questions in the
[easy door](../../../issues/new?template=report-a-trap.yml), and a maintainer
does the rest. Scrub hostnames, paths and tokens out of anything you paste;
the form shows you how.

The reasoning field and thinking toggle are **no longer unwritten on this
stack**. The contributor field run established the reasoning field, exercised
the toggle, and its evidence is why SGLang now appears in
`STACKS_WITH_KNOWN_OFF_CONTROL`, with a regression test behind it. Status is
**contributor-measured, conditions as reported**; the maintainers have not
reproduced those conditions.

**What is still unwritten here** is narrower and worth naming precisely: the
**degraded longer-form Laguna output** and its mechanism. The run recorded
incoherent chat-completion output and a transformers Mistral-regex warning, ran
no controlled fix, and deliberately did not attribute the degradation to the
tokenizer, the quantisation, the parser pairing or any other layer. That
remains open and unowned.
