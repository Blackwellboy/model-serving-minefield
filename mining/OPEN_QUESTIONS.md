# The open queue: what is unsettled, and what would settle it

Registry entries under `traps/` are verified. The notes beside this file are
candidates that were tested and did not or could not promote. **This file is the
layer above both: everything currently open, with the criteria that would close
it written down before anyone runs it.**

Publishing this is deliberate. A registry that only shows its finished work
invites you to assume the rest is settled. It is not, and some of these are
things a stranger with the right hardware can close faster than we can.

## The rule this file exists to enforce

**CONFIRM and REFUTE criteria are written before the run, not after.** That is
what made the trap [33](../traps/routing/33-moe-inference-topk-expansion-tax.md)
confirmation defensible: the primary contrast, the value of k, the n and the
test were fixed in a
[verification queue](2026-07-28-qwen36-a6b-verification-queue.md) before a
single sample was generated, so the result could not be the shape of a search.
An item without both criteria is not an entry in this queue.

Every row carries: the claim, its source and whether that source is **PRIMARY**
(vendor documentation, the code itself, or our own raw) or **secondary** (a
review, a summary, a report of a report), the hardware and stack it needs, the
CONFIRM criterion, the REFUTE criterion, and a rough lane cost.

**Lane cost** is in units of a serving lane's time, ours or yours: `S` under an
hour, `M` a few hours, `L` a day or more, `XL` needs hardware nobody here has.

---

## OPEN

### Q1. Does forcing chunked prefill on and off change the cold-versus-cached answer divergence?

- **Claim under test.** Trap [60](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md)
  measured that a cold prefill and a prefix-cache hit answer the same prompt
  differently. Two mechanisms could produce that, and the entry does not
  separate them: chunked prefill changing the reduction order, or cache replay
  reconstructing state differently.
- **Source.** PRIMARY, ours. Fully specified and pre-registered at
  [the experiment note](2026-07-28-chunked-prefill-vs-cache-replay-experiment.md).
- **Needs.** A DeepSeek-V4-Flash class lane on a **scratch serve**. It cannot
  run on the lane it was written from, because it needs a serve-flag change and
  that lane is production. This is the whole reason it has not run.
- **CONFIRM.** The divergence tracks the chunked-prefill setting and disappears
  in the arm where it is off, with the cache arm held constant.
- **REFUTE.** The divergence persists with chunked prefill off, which points at
  cache replay instead.
- **Cost.** M, plus a serve you are allowed to restart.
- **Note.** Written to be executable by someone else. If you have that lane, this
  is the highest-value open item here.

### Q2. TheTom's held entry: the with-and-without chunked-prefill pair

- **Claim under test.** One entry of the thirteen in the
  [43 to 55 contribution](../CHANGELOG.md) is **held, not landed**, because its
  status promises a with-and-without chunked-prefill comparison that the entry
  never states. Holding it was the right call and it stays held.
- **Source.** PRIMARY, the contributor's own submission.
- **Needs.** The contributor's stack, or any lane where chunked prefill can be
  toggled against a fixed workload.
- **CONFIRM.** The pair is produced, both arms stated, and the entry lands at
  whatever label the pair actually supports.
- **REFUTE.** The pair shows no difference, in which case the entry lands as a
  negative, which is worth the same and is published the same way.
- **Cost.** S for whoever already has the lane configured.
- **Note.** Shares a mechanism with Q1 and they should be read together, but they
  are separate runs on separate stacks and neither settles the other.

### Q3. Does DeepGEMM's architecture requirement explain our inert flag?

- **Claim under test.** `VLLM_USE_DEEP_GEMM` measured **inert** on a GB10
  (`sm_121`) NVFP4 lane, published in the
  [tuning sweep](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/sweep/LAGUNA_TUNING_SWEEP_20260723.md)
  with an A/B table and no mechanism. DeepGEMM's README requires "NVIDIA SM90 or
  SM100 architecture GPU" and never mentions SM120 or SM121.
- **Source.** PRIMARY both halves: our own A/B, and the vendor requirements
  line. A secondary review supplied the lead and its narrower "FP4 kernels are
  datacenter-only" framing is **not** what the primary source says.
- **Needs.** Any consumer-Blackwell lane running vLLM with the flag settable.
- **CONFIRM.** vLLM or DeepGEMM emits an observable line declining the
  architecture, or a build-side check shows no kernels compiled for `sm_12x`.
  That would turn two consistent pieces of evidence into one demonstration.
- **REFUTE.** The library is shown to build and dispatch on `sm_121`, which
  would mean the null has some other cause and the entry should not be written.
- **Cost.** S, and it is mostly log reading rather than benchmarking.
- **Note.** An entry is **drafted and deliberately not landed** pending this. It
  pairs with trap [90](../traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md)
  as the same shape one library over, except that trap 90 fails loudly and this
  one does not fail at all.

### Q4. Does weight-only NVFP4 (W4A16) beat fully quantized W4A4 in decode on a consumer Blackwell?

- **Claim under test.** That mature FP16 GEMM kernels beat early-stage FP4 ones
  hard enough that the less-quantized configuration decodes faster on an
  RTX 5090.
- **Source.** **secondary**, a review document. No figure from it is quoted or
  treated as measured, here or anywhere. Our own working assumption about GB10
  has a different shape, which is exactly why this is worth running rather than
  believing.
- **Needs.** An RTX 5090 lane and one checkpoint available in both W4A16 and
  W4A4. We have the hardware.
- **CONFIRM.** W4A16 decode tok/s exceeds W4A4 at matched concurrency, prompt
  length and context, on the same build, with the gap outside the sample spread
  and both arms reproducible under the isolation rules in traps
  [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md)
  and [92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md).
- **REFUTE.** W4A4 is equal or faster at matched settings, or the difference sits
  inside the spread.
- **Cost.** M.
- **Note.** State the kernel path per arm, not just the label: trap
  [10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) is the
  reason a result here means nothing without it.

### Q5. Is the Qwen dose-depth relationship real, or did it inherit a refutation it was never tested for?

- **Claim under test.** Whether system-prompt dose modulates reasoning **depth**
  on Qwen, as distinct from firing rate. The Laguna depth-collapse reading was
  refuted in-run and the correction is published. **Qwen was deliberately left
  OPEN rather than assumed to inherit that refutation.**
- **Source.** PRIMARY, ours. Related published work is the
  [cross-model gate curve](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/cross-model/QWEN_GATE_CURVE_20260728.md).
- **Needs.** A Qwen 3.6 35B-A3B lane and an **in-run interleaved** design. Not a
  between-run comparison: the depth refutation turned on task composition and
  tool-boundary truncation, so arms must be interleaved within one run.
- **CONFIRM.** A monotone dose-depth relationship survives interleaving with the
  tool-exit and direct-answer paths split, per the finish-path rule.
- **REFUTE.** Depth differences vanish once exits are split, matching the Laguna
  result.
- **Cost.** M.
- **Note.** The known confound is on record: the C8 cell shares the tool-call
  confound at 14/40, so any design that does not split on exit path reproduces
  the original error rather than testing it.

### Q6. Does a template-less tokenizer hard-fail on SGLang's OpenAI route?

- **Claim under test.** R2-13, that a checkpoint shipping no chat template
  requires one to be passed explicitly or the OpenAI-compatible route fails.
- **Source.** secondary, an upstream report. Untested here.
- **Needs.** SGLang, plus an **ungated checkpoint that genuinely ships no chat
  template**. That is the blocker and it is a specific ask: Llama-3.2-1B is gated
  on HuggingFace, and the ungated substitute chosen to stand in for it,
  `Qwen3-0.6B-Base`, turned out to ship a `chat_template` key in its
  `tokenizer_config.json` anyway, so it does not exercise the path at all.
- **CONFIRM.** Serving a genuinely template-less tokenizer makes the OpenAI route
  fail, and passing a template explicitly fixes it.
- **REFUTE.** SGLang supplies a default and serves, in which case the report is
  scoped to whatever version it was filed against.
- **Cost.** S once the checkpoint exists.
- **Note.** **Naming a small, ungated, genuinely template-less checkpoint is a
  complete contribution to this queue.** No hardware needed to help.

### Q9. Which uncovered entries deserve a doctor check?

- **Claim under test.** The doctor implements checks for **19 of 97** entries and
  says so on every run. That is a coverage statement, not a plan. Which of the
  78 uncovered entries are reachable by a request-shaped probe is unanswered.
- **Source.** PRIMARY, ours.
- **Needs.** No hardware. Reading, plus a lane to validate any check written.
- **CONFIRM.** A candidate is reachable if a probe can distinguish the trap from
  every other state that produces the same observation, per the doctor's own
  clean-verdict contract.
- **REFUTE.** If acceptance, silence or a missing template would explain the same
  result, it cannot reach CLEAN and belongs in COULD NOT CHECK instead.
- **Cost.** S to triage, M per check written with tests.
- **Note.** Two concrete candidates already exist with their checks written up
  but not implemented: the portable device-memory assertion in trap
  [96](../traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md)
  (`free_mib <= total_mib`) and the full-offload decode reference in trap
  [97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md).
  Both would change the coverage arithmetic, so they need the count updates too.
- **Disclosed because it is the same kind of gap.** The doctor recommends
  comparing GPU utilisation against power draw as a runtime tell for a fallback
  kernel path (trap [10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md)
  territory), and **nobody here has ever measured a util-versus-power pair**.
  The only power figures in this registry are a contributor's. So the tool
  currently carries a recommendation we have not tested ourselves. Closing it is
  cheap on any lane already up: sample
  `nvidia-smi --query-gpu=utilization.gpu,power.draw,power.limit` during a
  known-good decode and during a known-fallback decode, and record both. One
  warning for anyone writing that check: GB10-class boards report power as
  `[N/A]`, so a script that coerces it to zero false-alarms on exactly that
  hardware, and the guard has to come first.

### Q10. Does the DeepSeek-V4 system-message quality cliff exist at a usable n?

- **Claim under test.** R2-31, a quality cliff tied to system-message handling.
- **Source.** secondary, upstream. Our attempt did not reproduce it at small n
  and measured system-independent behaviour instead; it
  [stays open pending an upstream recipe](2026-07-27-r2-31-deepseek-v4-system-message-no-cliff-small-n.md).
- **Needs.** The upstream recipe, specifically the prompt set and the scoring, or
  enough lane time to run a properly powered arm.
- **CONFIRM.** The cliff appears with a stated effect size at an n that clears
  the agreement floor.
- **REFUTE.** No cliff at adequate n with the upstream recipe followed exactly.
- **Cost.** M, and it is blocked on the recipe rather than on hardware.

### Q11. Does a backend-layout mismatch reproduce the trap 44 failure without touching a swizzle flag?

- **Claim under test.** Trap [44](../traps/quantization/44-fp4-dequant-scale-swizzle-layout.md)
  measured one FP4 scale-layout mismatch. Vendor documentation shows several
  more ways to land the same mismatch: per-backend layout and shuffle
  requirements differ, and NVFP4 and MXFP4 differ in both scale type and block
  size. Whether those produce the same silent, cosine-passing corruption is
  documented as plausible and measured by nobody here.
- **Source.** PRIMARY for the layout differences (CUTLASS and FlashInfer
  documentation, cited in the entry). The measured instance is
  contributor-measured. The generalisation is **unmeasured**.
- **Needs.** Any Blackwell-class lane and one FP4 checkpoint.
- **CONFIRM.** Feeding an artifact prepared for one backend's layout to another
  reproduces high aggregate cosine with a failing discriminative probe.
- **REFUTE.** The mismatch fails loudly, or is rejected, in which case the silent
  class is narrower than the entry's new section implies and the section should
  be narrowed with it.
- **Cost.** M.

---

## CLOSED, so nobody re-opens them

Recorded because three of these kept being re-queued. A settled disposition is
as much a result as an entry.

| Item | Disposition | Where |
|---|---|---|
| R2-39 thinking plus tools yields empty output | **REFUTED AS STATED**, then closed on the stack it was re-scoped to. Empty content tracks tools alone, in both thinking states, and every empty response carried a tool call. Not a defect: a harness reading `content` and ignoring `tool_calls` | [note](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md) |
| R2-27 Mistral tokenizer-mode | **llama.cpp-inapplicable, NOT weight-blocked.** A Mistral checkpoint arriving does not unblock it: the flag is hard-rejected by the binary and GGUF conversion discards the tokenizer the flag selects. Open only against a stack that implements the flag | [note](2026-07-27-r2-blocked-not-testable.md) |
| Is SGLang feasible on this hardware class? | **ANSWERED: not infeasible**, and since superseded by an actual first-party bring-up. Stop re-asking the feasibility question; the open SGLang items are Q6, Q7 and Q8 | [note](2026-07-28-sglang-on-gb10-feasibility.md) |
| R2-29 tool calls as raw JSON on Nemotron NVFP4 | **REFUTED AS WORDED, reframed.** Nested XML, not JSON, and vLLM rejects the tools-without-parser request with HTTP 400 rather than degrading | [note](2026-07-28-r2-29-tool-calls-refuted-as-worded.md) |
| R2-16 multi-slot batching non-determinism | **CONFIRMED**, with a prompt-length floor that makes the natural minimal reproduction a false negative | trap [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) |
| R2-41 shared system prompt changes determinism | **CONFIRMED and resolved**: same effect as R2-16, and the shared prompt was special for being long, not for being shared | traps [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md), [92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) |
| R2-17 timestamp in system prompt kills the cache | **REFUTED AS WORDED.** Mechanism real at a different position; the received mitigation is the harmful move | trap [93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md) |
| R2-46 partial offload misread as slowness | **CONFIRMED and stronger than claimed**: no endpoint names the split | trap [97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md) |
| R2-18 cache and unified-memory reporting, reporting half | **REPRODUCED**, on WSL2 rather than the unified-memory hardware it was blocked for. The **cache-sizing half remains open** and is not covered by this row | trap [96](../traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md) |
| Does raising MoE inference top-k cost accuracy on a quantised build? | **CONFIRM**, pre-registered, monotone across four values of k in two protocols on two passes | [note](2026-07-28-trap-33-q1-nvfp4-confirmed.md) |
| What is our own agreement floor? | **ANSWERED**: 97.58% pooled item agreement, calibrated to plus or minus 1.3 points at n=600 for MMLU-style paired comparisons, explicitly not transferable to binary outcomes | [note](2026-07-28-our-agreement-floor-greedy-not-reproducible.md) |
| Is temp-0 reproducibility a property of the card? | **ANSWERED as a regime, not a ranking.** Both architectures diverge at 220 tokens; only one still does at 444 | trap [94](../traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md) |
| Does co-tenancy on one host perturb a lane? | **NEGATIVE**, for two GPUs with headroom. Does **not** cover two models on one GPU | trap [95](../traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md) |
| Q7: is SGLang's NVFP4 path broken for Laguna? | **REFUTED under the pre-registered generation criterion.** The non-Laguna NVFP4 control generated first, then Laguna loaded through `CompressedTensorsW4A4Nvfp4MoE` and generated a correct first token. Longer Laguna output was degraded, so this is not a correctness or support claim | [note](2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md) |
| Q8: is the doctor portable to SGLang? | **CONFIRMED.** Two 14-request runs completed with meaningful bounded verdicts. The generic stack label was a real reporting defect and has a regression-tested SGLang detector | [note](2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md) |

---

## How to use this file

If you can close one of these, the
["I hit a trap" issue form](../../../issues/new?template=report-a-trap.yml) takes
a result as readily as a bug report, and a **refutation is as welcome as a
confirmation**. State the criterion you were testing against before you say what
happened, so the result can be read against the same bar everyone else's was.

If you think an item here is already settled somewhere we have not seen, that is
also worth an issue. Half of what is open above is open because nobody looked in
the right place.
