# Public-source harvest: SGLang v0.5.18 + veloGB10 + GLM-5.2 Spark kit

**Date read:** 2026-08-25

**Canonical trap count impact: 0.** This is a mining/adjudication packet. Nothing below is a new canonical trap yet, nothing is first-party reproduction, and no trap number is reserved by this file.

## Sources reviewed

- [sgl-project/sglang v0.5.18 release](https://github.com/sgl-project/sglang/releases/tag/v0.5.18)
- [joesinvestments/glm52-spark-kit](https://github.com/joesinvestments/glm52-spark-kit)
- [sf-stav/veloGB10](https://github.com/sf-stav/veloGB10)

Primary SGLang PRs were opened directly where named below. Community-repo findings below are attributed to the public repository that reports or encodes them and remain unreproduced here.

## Disposition vocabulary used in this packet

- **UPSTREAM_READY**: primary upstream PR was read, the mechanism is concrete, the fix is merged/closed, and the item appears strong enough for the `upstream/` tier after one final exact-duplicate pass.
- **LEAD_QUEUE**: useful public-source mechanism that should enter the unverified-lead/adjudication flow, not the canonical registry directly.
- **EXISTING_EXTENSION**: likely evidence or a scoped extension of something Minefield already has; do not mint a duplicate without proving a distinct mechanism.
- **CONTROL_ONLY**: useful defensive practice or implementation control, but not itself a demonstrated trap.
- **NOT_TRAP**: useful serving knowledge that should not be promoted as a failure mechanism.

## High-priority upstream candidates from SGLang v0.5.18

### H25-01 — speculative draft count above four can silently corrupt DSV4 compressed state

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #34189](https://github.com/sgl-project/sglang/pull/34189), merged; read 2026-08-25.

**Reported by:** @hnyls2002.

**Observed upstream symptom:** DeepSeek-V4 speculative serving can remain alive with no assertion, illegal access or NaN while the compressed-state ring contains stale positions when `--speculative-num-draft-tokens > 4`.

**Mechanism:** the write planner hard-coded an MTP pad of four. Larger speculative verify windows could under-write the ring; a later compression could then read stale slots. The host planner also omitted the pad entirely, so CPU/GPU planner paths could disagree.

**Why Minefield-shaped:** ordinary end-to-end accuracy did not reliably expose the defect. The upstream PR explicitly says the corruption can be silent and alignment/acceptance dependent.

**CONFIRM:** on the pinned pre-fix build, exercise draft counts 5+ and assert ring residency/planner agreement across compression residues; reproduce a stale read or pre-fix regression-test failure.

**REFUTE:** the pinned pre-fix planner already covers the full committed speculative tail and CPU/GPU plans agree for the tested draft counts.

**Related current Minefield material:** Trap 28, Trap 120 and U16 are adjacent speculative/concurrency/state mechanisms, but none was found to be this exact hard-coded write-pad defect.

---

### H25-02 — prefix-cache hit + prefill CUDA graph can restore another request's conv state

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #34184](https://github.com/sgl-project/sglang/pull/34184), merged; read 2026-08-25.

**Reported by:** @ispobock.

**Observed upstream symptom:** a hybrid-SWA/Mamba request can decode from a convolution checkpoint it never produced. The wrong request then stays wrong for the generation. Disabling the prefill CUDA graph removes the failure.

**Mechanism:** captured prefill replay read stale `mamba_track_mask` / `mamba_track_indices` rows left by a previous replay. The current window could be scattered into an earlier request's checkpoint; a later prefix-cache restore then loaded the wrong state.

**CONFIRM:** pre-fix build, prefill graph ON + chunked prefill + concurrency + prefix hit; compare restored conv state/logprobs against a flushed/eager control and inspect the claimed track destination.

**REFUTE:** pre-fix graph and eager/flushed controls are bit/field equivalent across the reported cache-hit/concurrency shape.

**Related:** prefix-cache poisoning/state-retention traps exist, but this exact stale captured-track-row mechanism appears distinct.

---

### H25-03 — unified memory + Triton + deterministic inference can silently corrupt logits

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #33517](https://github.com/sgl-project/sglang/pull/33517), merged; read 2026-08-25.

**Reported by:** @ch-wan.

**Observed upstream symptom:** the three-way combination `--enable-unified-memory` + Triton attention + deterministic inference produces NaN/garbage logits. With async assertions armed it aborts; without them the upstream report says the run can complete locally, making the corruption quieter.

**Mechanism:** the deterministic one-stage extend kernel read the prefix at translated physical KV ids but the extend half at untranslated virtual ids.

**CONFIRM:** compare pre-fix unified vs static-pool outputs/logprobs under all three conditions and then remove one condition at a time.

**REFUTE:** the pinned pre-fix unified path matches static-pool ids/logprobs and never mixes virtual/physical locations.

---

### H25-04 — recycled unified-memory page tails can re-expose historical bytes to speculative attention

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #33974](https://github.com/sgl-project/sglang/pull/33974), merged; read 2026-08-25.

**Reported by:** @ch-wan.

**Observed upstream symptom:** unified-memory + DSPARK can show fake speculative acceptance, invalid accuracy, NaNs or load-dependent corruption. Poisoning the pool makes the class deterministic.

**Mechanism:** page recycling exposed historical bytes in the unused tail of a partial page. The MLA path read whole pages and used arithmetic masking that was NaN-unsafe, so stale/poison tail data could leak into attention. Speculative verify increased exposure.

**CONFIRM:** poison or otherwise mark page envelopes on a pinned pre-fix unified/spec path, recycle pages, and compare against a zero-on-handout or static-pool control.

**REFUTE:** recycled partial-page tails are never consumed by the affected kernel or the pre-fix poisoned and clean runs remain state/accuracy equivalent.

**Note:** keep separate from H25-05; the same upstream PR fixed two independent root causes.

---

### H25-05 — 32-bit slot-stride multiplication can wrap into another request's recurrent state

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #33974](https://github.com/sgl-project/sglang/pull/33974), merged; read 2026-08-25.

**Reported by:** @ch-wan.

**Observed upstream symptom:** a clean boot can work at low slot ids and later produce silent state divergence, fake acceptance or illegal access as slot ids grow.

**Mechanism:** huge unified-memory conv/SSM slot strides individually fit int32, but `slot * stride` wrapped in 32-bit arithmetic at sufficiently high slot ids and addressed other slots or outside the allocation.

**CONFIRM:** replay the affected kernel across increasing slot ids with faithful large strides and compare against an int64-addressing/static control.

**REFUTE:** pre-fix address arithmetic remains exact across the reported high slot-id range.

---

### H25-06 — speculative multi-token accept can leak tokens after EOS/stop when it also crosses the length cap

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #33758](https://github.com/sgl-project/sglang/pull/33758), merged; read 2026-08-25.

**Reported by:** @842974287.

**Observed upstream symptom:** emitted output can look like `[..., <eos>, <junk>]` when one speculative accept run both contains a stop/EOS and crosses `max_new_tokens`.

**Mechanism:** length-first finish handling won before stop handling, so over-accepted tokens after the stop could remain inside the emitted cap.

**CONFIRM:** pre-fix request where a multi-token accept contains EOS/stop before the cap and an extra token after it; assert finish reason and emitted ids.

**REFUTE:** pre-fix output already trims at the in-budget stop and never emits accepted tokens after it.

---

### H25-07 — missing DFlash `is_causal` metadata can change semantics after a runtime update

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #34524](https://github.com/sgl-project/sglang/pull/34524), merged; read 2026-08-25.

**Reported by:** @mmangkad.

**Observed upstream symptom:** an existing DFlash checkpoint's average accept length fell from roughly 5.62 to 5.27-5.30 after runtime behavior changed, even though the checkpoint did not change.

**Mechanism:** the checkpoint omitted `is_causal`; a runtime change changed the default interpretation for sliding-attention draft layers. The fix restored historical layer-specific defaults while honoring explicit metadata.

**CONFIRM:** load a checkpoint that omits the field on pre/post behavior and inspect resolved layer attention types plus acceptance.

**REFUTE:** the allegedly affected runtime resolves the same causality semantics as the historical control.

**Minefield angle:** absence of checkpoint metadata is not a neutral value when runtime defaults move.

---

### H25-08 — DFlash/DSPARK draft KV pool accounting can undercount by the DCP factor

**Disposition:** UPSTREAM_READY

**Primary source:** [SGLang PR #33912](https://github.com/sgl-project/sglang/pull/33912), merged; read 2026-08-25.

**Reported by:** @milesial.

**Observed upstream symptom:** capacity/memory planning for a DFlash-family draft can be too optimistic under DCP even though the exact draft geometry is known.

**Mechanism:** the exact geometry path added a single draft-row cost while the draft pool spans the widened DCP virtual location space and must be budgeted with the DCP replication factor.

**CONFIRM:** compare pre-fix bytes-per-token/cell-size accounting at DCP1 vs DCP>1 against the actual draft-pool geometry.

**REFUTE:** pre-fix exact and fallback paths already include the same DCP factor.

---

### H25-09 — a dependency set can resolve successfully but still make FA4 fail to compile on Blackwell

**Disposition:** UPSTREAM_READY, lower priority because the failure is loud.

**Primary source:** [SGLang PR #34372](https://github.com/sgl-project/sglang/pull/34372), merged; read 2026-08-25.

**Reported by:** @mmangkad.

**Observed upstream symptom:** FA4 startup compilation fails on Blackwell even though package resolution succeeds.

**Mechanism:** `quack-kernels==0.6.3` could resolve with CuTeDSL 4.6.0, but the combination exposed a compiler branch-scope/type-join bug. SGLang moved to a matched Quack/CuTeDSL pair.

**CONFIRM:** reproduce the compile failure on the pinned dependency pair and show it disappears on the fixed matched pair.

**REFUTE:** pinned pair compiles the affected FA4 kernel successfully.

---

## SGLang release-note leads/extensions that should not be lost

### H25-10 — first post-upgrade launch recompiles after cache-directory migration

**Disposition:** EXISTING_EXTENSION, likely to L002 / cold-JIT measurement work rather than a new trap.

v0.5.18 moves Triton, FlashInfer, Inductor, DeepGEMM and CUDA driver caches under `SGLANG_CACHE_DIR`. The release explicitly says the first launch after upgrading recompiles once. A cold post-upgrade launch can therefore be mistaken for a persistent startup regression if compared with a warmed previous version.

**Process:** preserve as a versioned extension/check: record cache identity and compare cold-vs-warm before claiming an upgrade startup regression.

### H25-11 — accepted `--torchao-config` values had become an always-ImportError surface before removal

**Disposition:** LEAD_QUEUE / versioning-config surface.

v0.5.18 removes torchao integration and states `--torchao-config` had raised ImportError for every accepted value after the torchao pin moved to 0.17.0.

**Check:** pin an affected pre-removal SGLang build and distinguish parser acceptance of the option/value from successful runtime construction of the requested quant path.

### H25-12 — "landed" does not mean "present in this release"

**Disposition:** EXISTING_EXTENSION / versioning provenance.

v0.5.18's known issues explicitly call out a Kimi K3 MLA fusion and an AMD GLM-5.2 shared-expert fusion that landed and were reverted in the same cycle. This is a useful provenance check for Minefield: a merged PR or earlier main snapshot is not proof a released tag contains the feature.

**Process:** likely extend an existing versioning/provenance entry rather than minting a new trap.

---

## Public community-repo leads: `joesinvestments/glm52-spark-kit`

These are public, detailed, correctness-gated community measurements, but **not reproduced here**. They should remain in the lead/adjudication path unless separately promoted under the repo's evidence vocabulary.

### H25-13 — gapped CUDA-graph capture ladders can make DCP concurrency look fundamentally broken

**Disposition:** LEAD_QUEUE, high priority.

**Source:** [docs/RECOMMENDATION.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/RECOMMENDATION.md).

**Reported symptom:** a configuration that passes sequential requests can die on the first affected concurrent batch, making "concurrency is broken with DCP" look true.

**Reported mechanism:** capture sizes must form a dense ladder compatible with `1 + num_speculative_tokens`; a gap introduces padded `decode_len=0` rows and reaches a sparse-MLA branch that assumes DCP-sharded and global block-table widths match.

**Check:** same pinned build, contiguous valid capture ladder vs intentionally gapped ladder, including the first batch shape that requires padding.

**Related:** Trap 130 and speculative/indexer state traps are adjacent; exact dedupe required.

### H25-14 — DCP scratch reservation can reserve full global context on every rank and OOM GB10 UMA

**Disposition:** LEAD_QUEUE, high priority.

**Sources:** [README.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/README.md) and [docs/SESSION-2026-08-17.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/SESSION-2026-08-17.md).

**Reported mechanism:** paged-indexer scratch was reserved for full `max_model_len` on each DCP rank although a rank owns about `1/dcp` of request rows. At DCP4, the reported reservation moved from 315,968 rows to 78,994 plus slack after the fix.

**Check:** compare reserved scratch rows/bytes against rank-local row ownership at DCP1/DCP4 and reproduce memory-profile failure on the old calculation.

### H25-15 — one-GPU-per-node topology probing can create a deterministic timeout-shaped boot lottery

**Disposition:** LEAD_QUEUE.

**Source:** [README.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/README.md).

The kit reports a gloo `in_the_same_node_as` probe stalling ~91 seconds against a 90-second timeout and contributing to about 40% boot failures at DCP>1; a one-GPU-per-node topology short-circuit is used in production.

**Check:** pin the reported topology/build and compare boot success/time with and without the topology probe while keeping distributed settings fixed.

### H25-16 — concurrent boot retries can multiply memory pressure and make recovery worse than the original failure

**Disposition:** LEAD_QUEUE / operational safety.

**Sources:** [docs/RECOMMENDATION.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/RECOMMENDATION.md) and [docs/SESSION-2026-08-17.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/SESSION-2026-08-17.md).

The kit reports that stacked retries each loaded roughly 98 GB and once exhausted all four nodes, forcing a physical power cycle. Its production wrapper therefore retries sequentially with a memory-reclaim gate.

**Minefield question:** does this belong as a runtime/ops trap or only a recovery playbook rule? Keep unnumbered until adjudicated.

### H25-17 — `/v1/models` 200 is not a serving-readiness proof

**Disposition:** EXISTING_EXTENSION to Trap 112, not a new trap.

**Source:** [README.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/README.md).

The kit explicitly replaced metadata-endpoint health with a real completion before declaring a retry successful. Add as external corroboration/example if useful; do not duplicate Trap 112.

### H25-18 — DSpark drafter can inherit the target's quantization path and fail before it ever drafts

**Disposition:** LEAD_QUEUE.

**Source:** [docs/DSPARK.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/DSPARK.md).

The public report says a draft config with no own quantization setting inherited the target's compressed-tensors quantization and fell into an incompatible config path. An explicit draft-local configuration was required.

**Check:** prove requested target quant, effective drafter quant, module dtypes and the first failing draft forward on the pinned build.

**Related:** Trap 10, Trap 62, Trap 109 and Trap 133 are adjacent but not obviously identical.

### H25-19 — a dense drafter can inherit a target-only MLA KV dtype

**Disposition:** LEAD_QUEUE; adjudicate whether to merge with H25-18 or keep separate.

**Source:** [docs/DSPARK.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/DSPARK.md).

The target's `nvfp4_ds_mla` KV record is an MLA-specific layout; the dense drafter could not use it and required a per-draft `kv_cache_dtype: auto` override.

**Check:** requested/effective KV dtype per target and drafter plus backend compatibility assertion.

### H25-20 — the first benchmark batch after boot carried a ~14% cold-start penalty

**Disposition:** EXISTING_EXTENSION / measurement warm-up.

**Source:** [docs/RECOMMENDATION.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/RECOMMENDATION.md).

The kit explicitly discards the first post-boot benchmark batch and reports the cold penalty at roughly 14%, almost 3x its stated noise floor.

**Process:** use as evidence for a warm-up/benchmark-state check if an existing entry already owns this mechanism.

### H25-21 — an SM121 Marlin environment switch is reported as a correctness requirement, not a speed knob

**Disposition:** LEAD_QUEUE, high priority.

**Source:** [docs/RECOMMENDATION.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/RECOMMENDATION.md).

The kit states `VLLM_MARLIN_USE_ATOMIC_ADD=1` is a correctness requirement on its SM121 path and that the MoE resolves to MARLIN WNA16, not NVFP4.

**Check before any promotion:** isolate the exact wrong-output/correctness failure with the flag OFF vs ON on the pinned model/runtime/kernel path. The current source provides the rule but this mining pass has not opened a dedicated raw failure packet.

### H25-22 — a custom all-reduce path can turn distributed init into a multi-minute stall

**Disposition:** LEAD_QUEUE.

**Source:** [docs/SESSION-2026-08-17.md](https://github.com/joesinvestments/glm52-spark-kit/blob/main/docs/SESSION-2026-08-17.md).

The session report says `--disable-custom-all-reduce` removed a ~300-second init stall on the tested four-node GB10 path and became part of every launcher.

**Check:** pin topology/build and A/B only the custom-all-reduce selection while capturing the exact blocking collective/init stack.

---

## Public community-repo leads: `sf-stav/veloGB10`

### H25-23 — speculative decoding can resume against stale MTP KV and silently lose its speedup while correctness still passes

**Disposition:** LEAD_QUEUE, very high priority.

**Source:** [src/batch.rs](https://github.com/sf-stav/veloGB10/blob/main/src/batch.rs).

The scheduler documents a specific state rule: once a lane takes a non-MTP step, its MTP KV is missing entries for all tokens decoded since. Re-enabling MTP later would draft against holes/zero rows. Verification can reject the bad drafts, keeping target output correct while speculative acceptance silently collapses.

**Why Minefield-shaped:** a normal correctness gate can stay green while the performance feature is no longer doing useful work.

**Check:** force policy on -> off -> retry within one lane, log MTP KV coverage plus acceptance; compare against a fresh/continuously maintained MTP control.

**Related:** U15/U16, Trap 28, Trap 62 and Trap 71 are adjacent but do not appear to state this exact stale-resume mechanism.

### H25-24 — deep-copying a live CUDA buffer can leave a speculative drafter consuming stale zeros

**Disposition:** LEAD_QUEUE, high priority.

**Source:** [src/dflash2/round.rs](https://github.com/sf-stav/veloGB10/blob/main/src/dflash2/round.rs).

The source documents a prior root cause: `CudaSlice::clone()` was a deep copy. Code that intended to attach the DFlash2 round to a live tap sink cloned the zeroed buffer instead; the drafter then consumed stale zeros until the live staging buffer was copied explicitly before injection.

**Check:** compare pointer/buffer identity and captured tap values at attach/inject time on the pre-fix path; prove draft parity changes when live values are synchronized.

### H25-25 — byte-equivalent tool schemas can stop being token-equivalent if JSON serialization changes order/spacing

**Disposition:** LEAD_QUEUE, high priority.

**Source:** [src/dsv4_chat.rs](https://github.com/sf-stav/veloGB10/blob/main/src/dsv4_chat.rs).

The DSV4 encoder says tool-schema JSON must reproduce Python `json.dumps(ensure_ascii=False)` semantics, including insertion order and separators. Generic `serde_json` behavior without order preservation can reorder keys and compact separators, changing the model-facing wire prompt despite representing the same JSON object semantically.

**Minefield angle:** API/tool schema equality at the object level does not prove prompt/token equality.

**Check:** same tool object -> reference Python wire bytes/tokens vs alternate serializer bytes/tokens, then run the model/tool parser on both.

### H25-26 — an eight-hour memory-leak watch can be a no-op if GB10 telemetry reports `N/A`

**Disposition:** LEAD_QUEUE / telemetry integrity.

**Source:** [ENDURANCE_REPORT.md](https://github.com/sf-stav/veloGB10/blob/main/ENDURANCE_REPORT.md).

The public endurance report explicitly says `nvidia-smi` returned `N/A` for memory-used on the sampled GB10 path, so its memory-monotonic watch was effectively a no-op. The authors correctly did **not** claim independent proof of no memory leak.

**Check:** before publishing a GB10 soak as leak-free, assert the telemetry field is populated and monotonic-check code actually received numeric samples; otherwise use a different memory source or mark the memory result unmeasured.

**Related:** Trap 125 is about cgroup MemoryMax vs CUDA UMA accounting, not this exact telemetry-null issue; adjudicate extension vs new lead.

### H25-27 — content shape can move decode throughput by multiples, making one prompt's tok/s a misleading engine headline

**Disposition:** EXISTING_EXTENSION / measurement discipline.

**Sources:** [README.md](https://github.com/sf-stav/veloGB10/blob/main/README.md) and [ENDURANCE_REPORT.md](https://github.com/sf-stav/veloGB10/blob/main/ENDURANCE_REPORT.md).

The repo reports large code/prose/mixed throughput spreads on the same engine/model and explicitly distinguishes mixed-session averages from sustained code-heavy rates.

**Process:** use as external evidence for prompt/workload-shape controls. Do not create a new trap if the existing benchmark/measurement entries already own this class.

### H25-28 — binary/PTX mismatch is dangerous enough that the engine refuses to run it

**Disposition:** CONTROL_ONLY.

**Source:** [README.md](https://github.com/sf-stav/veloGB10/blob/main/README.md).

The engine uses a build-fingerprint handshake so a binary and foreign/stale PTX set cannot silently drift. This is useful as a defensive design pattern for Minefield's provenance guidance, but this source does not by itself document a measured bad-result incident caused by mismatching them.

### H25-29 — TP node cache is content-addressed and self-healing on missing blobs

**Disposition:** NOT_TRAP / useful control.

**Source:** [MANAGING_CACHE.md](https://github.com/sf-stav/veloGB10/blob/main/MANAGING_CACHE.md).

Useful operational design, but no failure mechanism should be invented from it.

### H25-30 — `--max-batch` changes both scheduling semantics and KV memory footprint

**Disposition:** EXISTING_EXTENSION / generic serving behavior, not new by itself.

**Source:** [QWEN_27B_SETUP.md](https://github.com/sf-stav/veloGB10/blob/main/QWEN_27B_SETUP.md).

The repo explicitly separates max-per-request-speed `max-batch=1` from concurrent lanes and notes KV memory scales per lane. Use only as supporting evidence when a real admission/concurrency trap is being adjudicated.

---

## Dedupe / promotion order

Do **not** promote all thirty rows blindly.

Recommended adjudication sequence:

1. H25-01 through H25-09: exact duplicate search against canonical + `upstream/`; if distinct, these are the strongest candidates for new upstream-reported entries because their primary PRs are concrete and merged.
2. H25-23 through H25-26: strongest community-source leads; add to the unverified-lead catalogue only after checking for exact overlap with existing speculative state, template/tool serialization and GB10 UMA/telemetry entries.
3. H25-13, H25-14, H25-18, H25-19, H25-21, H25-22: community runtime/memory/kernel leads worth preserving and reproducing.
4. H25-10, H25-12, H25-17, H25-20, H25-27, H25-30: likely extensions/corroboration of existing Minefield mechanisms rather than new numbers.
5. H25-16: decide whether recovery amplification belongs in the canonical registry or an operational playbook.
6. H25-28/H25-29: retain only as defensive controls/provenance ideas; do not turn them into traps without an actual failure report.

## Suggested reproduction shortlist on Blackwellboy hardware

When a compatible lane is free, the most efficient first-party reproduction order is:

- H25-26 telemetry-null assertion: cheap, no risky serving mutation if a GB10 soak/telemetry path already exists.
- H25-25 serializer byte/token A/B: offline/local, no model server required for the first gate.
- H25-23 stale speculative-state resume: synthetic/unit or controlled serving lane; correctness + acceptance both recorded.
- H25-13 capture-ladder gap: only on a disposable compatible DCP/config lane; never on protected production.
- SGLang H25-01/H25-03/H25-06 only when the exact affected stack/version can be pinned safely; otherwise keep them upstream-reported.

## Attribution

This packet preserves source ownership rather than laundering public findings into first-party claims.

- SGLang PR authors are credited per entry above.
- `joesinvestments/glm52-spark-kit` findings remain attributed to that public project/source until a specific author/commit is adjudicated for promotion.
- `sf-stav/veloGB10` findings remain attributed to @sf-stav / that public repository until a narrower source-level attribution is required.

No Nous contact, no third-party issue creation, no claim of first-party reproduction.