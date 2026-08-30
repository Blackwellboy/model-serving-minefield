# Public-source harvest: GLM-5.3 / Ling-3.0 / Qwen3.8 Flash-Next on DGX Spark / GB10

**Date read:** 2026-08-30

**Canonical trap count impact: 0.** This is a mining/adjudication packet. Nothing below is a new canonical trap, nothing is a first-party Blackwellboy reproduction, and no trap number is reserved by this file.

This pass intentionally prefers silent wrongness, false-health, misleading measurement surfaces, runtime/config drift, distributed-state failures, and failures that pass shallow smoke tests. Loud one-line OOMs are recorded only when the mechanism carries a reusable serving lesson.

## Sources reviewed

Six unique repositories were supplied (one GLM EXL3 URL was duplicated/concatenated in the owner message):

1. `tonyd2wild/GLM-5.3-DGX-Spark-Cookbook` @ `f72b0ddfd491c815027f9b56c82af4866f24e01b`
2. `tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark` @ `1ffba70df364ed0f044b2aba4d99cf492e9ebf85`
3. `tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark` @ `1f03bab8744065d9c7ef3d8e1e6b21d2fea698dc`
4. `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks` @ `79f10b91f84779b2b1ff2c9327b1a5847cd97f70`
5. `MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark` @ `ca840cb8d032353e24648aeee06312b0938348f6`
6. `MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks` @ `0f950012c8d8323acac9a08846a32ef7953f5f62`

Read surfaces included READMEs, launch scripts/tree structure, failure/forensics documents, recent commits, issue trackers, issue comments where a strong claim had a primary issue, and the dedicated Qwen MTP doom-loop report. Community-repo findings remain attributed to the repository/reporters that published them. A repo-maintainer confirmation is stronger than README prose but is still not Blackwellboy first-party reproduction.

## Disposition vocabulary

- **LEAD_QUEUE_HIGH** — concrete, reusable, Minefield-shaped source report worth a dedicated confirm/refute probe.
- **LEAD_QUEUE** — useful mechanism, but lower severity, incomplete causal proof, or narrower scope.
- **EXISTING_EXTENSION** — likely owned by a current canonical/upstream entry; preserve the new evidence without minting a duplicate.
- **SOURCE_CONFLICT / OPEN** — useful contradiction or unresolved mechanism; preserve it, do not choose a winner silently.
- **CONTROL_ONLY** — operational guardrail or diagnostic technique rather than a demonstrated failure mechanism.
- **NOT_TRAP / DO_NOT_QUEUE** — useful serving fact, retracted report, or claim too weak/misframed for Minefield.

## Highest-value findings from this pass

| ID | Priority | Disposition | Short description |
|---|---|---|---|
| H30-01 | A+ | LEAD_QUEUE_HIGH | Explicit KV-memory pin can bypass activation reservation: boot + short smoke pass, long request dies |
| H30-02 | A | LEAD_QUEUE_HIGH | InstantTensor-style fast load can look excellent then lose a distributed rank ~1 minute later |
| H30-03 | A+ | LEAD_QUEUE_HIGH | GB10 UVM livelock: ~96% util at ~10 W, host partly alive, model makes no progress, state can survive container death |
| H30-05 | A+ | LEAD_QUEUE_HIGH | Dependency install silently downgrades NCCL and breaks a previously valid fabric stack |
| H30-07 | A+ | LEAD_QUEUE_HIGH | Uninitialized sparse-indexer pool IDs can gather readable-but-wrong KV and produce a NaN/corruption lottery |
| H30-08 | A+ | LEAD_QUEUE_HIGH | ModelOpt NVFP4 can intermittently emit corrupted token IDs that are nearly invisible in English but can desync parsers |
| H30-09 | A | LEAD_QUEUE_HIGH | Padded/strided KV view can turn a ~377 MB logical tensor into a ~13.6 GB allocator request |
| H30-10 | A+ | LEAD_QUEUE_HIGH | Warm restart: `sitecustomize` stdout contaminates command-substituted JSON and crash-loops a previously clean launcher |
| H30-11 | A+ | LEAD_QUEUE_HIGH | Long cold prefill can collapse a peer decode ~11x with zero preemption and perfect speculative acceptance |
| H30-12 | A | LEAD_QUEUE_HIGH | Hybrid DFlash block-ID tax makes a logged 1.1M-token KV pool unable to hold three ~256K sessions |
| H30-15 | A+ | LEAD_QUEUE_HIGH | Qwen3.8 MTP positional/LSE/master-slice defects can create repetitive “doom loop” corruption only after lookahead advances |
| H30-16 | A | LEAD_QUEUE_HIGH | Recurrent GDN/DeltaNet state cannot be treated like ordinary attention KV; blanket FP8 KV is semantically unsafe |
| H30-19 | A | LEAD_QUEUE_HIGH | Tools can lose required args only under production-like concurrent state while byte-identical solo replay is clean; mechanism still open |
| H30-22 | A | LEAD_QUEUE_HIGH | Speculative structured-output termination can advance a grammar after stop/reasoning-boundary transitions |
| H30-24 | A | LEAD_QUEUE_HIGH | Generic DFlash KV-layout unification can multiply per-request memory because custom grouped layouts are not interchangeable |

The table is a triage view, not a promotion verdict. Exact duplicate/mechanism adjudication still belongs before any trap number.

---

# A. tonyd2wild/GLM-5.3-DGX-Spark-Cookbook

Source: https://github.com/tonyd2wild/GLM-5.3-DGX-Spark-Cookbook

### H30-01 — explicit KV-memory pin can remove the activation reserve that automatic sizing would have protected

**Disposition:** LEAD_QUEUE_HIGH.

The cookbook family and the linked 1M recipe describe a dangerous shape: manually pinning KV memory can make boots deterministic while bypassing the normal “free memory minus profiled peak activation” safety margin. The system can boot, warm, and answer short prompts at full speed, then die only when a long request creates the activation peak the manual pin failed to reserve for.

**Why this is Minefield-shaped:** the manual setting is chosen to make capacity *more deterministic* and can make shallow qualification look cleaner while moving the actual failure to long-context use.

**CONFIRM:** same pinned model/runtime; compare auto-sized KV versus explicit KV-memory pins while recording profiled peak activation, allocated KV, true free UMA, and a long-prompt first forward. Require a pin that boots and passes a short smoke but fails only at the long activation peak.

**REFUTE:** the live build always subtracts activation/workspace reserve even when explicit KV memory is supplied, or the reported failure is attributable to a separate allocation.

**Dedupe note:** adjacent to Trap 61 (advertised window fails silently), Trap 13 / Trap 125 (UMA accounting) and memory-headroom entries, but the proposed owner is specifically **manual KV pin bypassing the activation reservation path**.

### H30-02 — fast model load is not distributed-runtime stability

**Disposition:** LEAD_QUEUE_HIGH.

The Tony GLM family reports an InstantTensor/load-format path that reduced weight-load time dramatically and initially looked like a clear win with a cold page cache, but a rank could disappear roughly a minute after load without a useful kernel/dmesg explanation. Multiple memory budgets were tried.

**Portable lesson:** benchmark “load complete” separately from “ranks remain healthy through first-forward + dwell + generation.” A fast loader can move failure after the stopwatch.

**Related:** Trap 112 is the readiness ladder and should be cited if this promotes; the loader-specific delayed rank-death mechanism may still be distinct.

### H30-03 — GB10 UVM livelock can report high utilization while making no useful progress

**Disposition:** LEAD_QUEUE_HIGH.

Reported symptom under memory pressure: vLLM worker and a UVM thread consume heavy CPU; `nvidia-smi` can show roughly 96% GPU utilization while power is only around 10 W; shard load freezes partway through; the node can remain pingable while SSH cannot reliably fork. Killing the container may not immediately clear the degraded driver state.

The source ties this to unified-memory pressure and page-reclaim behavior. It also reports a two-sided operating constraint: disabling swap entirely can allow a worker to be killed during repack, while allowing active swapping can trigger pathological UVM behavior.

**CONFIRM:** preserve power + clocks + utilization + UVM thread CPU + buddy/page state + shard progress together. Show high utilization/low-power/no-progress persists independently of a live model process and is cleared by the reported memory-state recovery.

**Dedupe:** do **not** collapse into Trap 124 automatically. Trap 124 is a persistent GB10 low-power platform state with measured clock/power/compute recovery after AC removal. H30-03 is a source-reported **UVM/memory-pressure livelock with host progress loss**. They may share telemetry but currently have different claimed mechanisms.

### H30-04 — “free GPU memory” on GB10 is partly a host-page-cache question

**Disposition:** EXISTING_EXTENSION / OPEN.

The cookbook explicitly treats host page cache as competing with CUDA-visible unified memory and recommends cache flushing around deterministic boots. This strengthens the existing Minefield rule that “GPU memory” and host memory are not independent pools on GB10.

Do not mint a duplicate without proving a distinct mechanism beyond Trap 13 / 119 / 125. Useful extension check: record page-cache bytes next to CUDA allocation and allocator high-order-block availability before declaring two boots “same free memory.”

### H30-05 — install one performance dependency, silently downgrade NCCL, lose the fabric

**Disposition:** LEAD_QUEUE_HIGH.

The 2x DFlash deployment report records a FlashInfer nightly install that silently changed NCCL from a previously working 2.30.7 to 2.29.7. The next distributed initialization failed with `ncclCommInitRank internal error` on the Spark interconnect.

**Why this is stronger than generic dependency drift:** the operator is fixing a local attention/kernel problem; package resolution succeeds; the unrelated communication layer changes underneath a known-good multi-node configuration.

**CONFIRM:** pinned working env -> install the reported dependency set -> prove resolved NCCL version changed -> reproduce rank-init failure -> restore matched NCCL and recover with all other variables held.

**Related:** U35 covers a dependency set that resolves but later fails kernel compilation. H30-05 is a different downstream subsystem: **successful package resolution mutates the distributed communication ABI/version and breaks runtime initialization**.

### H30-06 — successful package resolution can still leave a mixed compiler stack

**Disposition:** EXISTING_EXTENSION to U35.

The same deployment encountered a mixed CuTeDSL/CUTLASS DSL environment after a nightly change and later hit a compiler internal error near the end of model load. Preserve as another U35 example; do not mint a second “pip succeeded, compiler failed” trap without a distinct invariant.

### H30-07 — sparse indexer can use uninitialized but in-range pool IDs

**Disposition:** LEAD_QUEUE_HIGH.

The Tony DFlash report describes a sparse top-k/indexer path where a buffer created with `torch.empty` could retain values for positions that did not receive a valid pool ID. Some stale IDs remained numerically in range, so bounds checks did not necessarily catch them. A gather could then read a real allocation belonging to the wrong logical location, turning the failure into a load/order-dependent NaN or wrong-state lottery instead of a clean OOB.

**Minefield value:** “in range” is not “initialized/owned.” This is exactly the sort of defect that can pass small deterministic smoke tests and surface under a particular indexer shape.

**CONFIRM:** poison/init sentinel the ID buffer, assert every consumed ID was explicitly written for the current request, and compare logits/KV gather against a fully initialized control across the affected top-k shapes.

### H30-08 — intermittent corrupted token IDs can hide inside readable English until a parser boundary is hit

**Disposition:** LEAD_QUEUE_HIGH; **primary-upstream follow-up required before promotion.**

The 4x NVFP4 repo reports intermittent token-ID corruption on a ModelOpt NVFP4 path and references vLLM #54150. A deterministic non-English probe reportedly exposed replacement-character events while a RedHatAI/compressed-tensors control did not. The source warns that ordinary English can make corruption look harmless until the bad ID lands inside a tool-call/control-token region, where it can desynchronize parsing or repetition behavior.

**Do not call this upstream-confirmed yet:** this packet read the community report that links the vLLM issue, not the full primary vLLM thread.

**Next action:** read vLLM #54150 and associated fix/PR, then classify UPSTREAM_READY vs community-only.

### H30-09 — a small logical KV tensor can become a gigantic allocation through padded stride geometry

**Disposition:** LEAD_QUEUE_HIGH.

The 1M repo's DFlash forensics describe a block-split/padded-view path where a roughly 377 MB logical tensor could induce an allocator request around 13.59 GB because the view's stride/storage geometry described a much larger backing extent after padding/splitting.

**Portable lesson:** memory accounting from logical `numel * element_size` is insufficient for strided/padded views. Record storage span/stride and the allocation actually requested by the backend.

### H30-10 — stdout from `sitecustomize` can corrupt command-substituted JSON only after a warm restart

**Disposition:** LEAD_QUEUE_HIGH.

Primary community issue read: https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/15

The image used `sitecustomize.py` to run overlay patch scripts at every Python startup. On a warm restart an already-applied patch printed a status line to **stdout**. `start.sh` constructed `--speculative-config` with shell command substitution around a Python JSON encoder, so the status line was prepended to the JSON and vLLM argparse rejected it. An `unless-stopped` policy then turned a one-line stdout mistake into a crash loop.

**Why this is gold:** cold start is clean; the same image/config fails only on warm restart. The Python command itself “works.” The JSON itself is valid before environment startup hooks contaminate stdout.

**CONFIRM:** run a trivial `python3 -c 'print(json.dumps(...))'` cold vs warm with overlay mounted; prove extra stdout enters command substitution; redirect patch diagnostics to stderr and recover without other changes.

---

# B. tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark

Source: https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark

### H30-11 — long cold prefill can starve an already-decoding request without preemption

**Disposition:** LEAD_QUEUE_HIGH, with maintainer confirmation from the Mia recipe's independently reported reproduction/fix.

Primary community issue read: https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/6

Measured report: one ~100K request decoding around 51–55 tok/s fell to **5.00 tok/s** while a second 100K cold prefill shared the engine. Preemptions remained zero, DFlash acceptance reached 100%, hardware/fabric remained healthy, and throughput returned immediately after the peer prefill cleared. MiaAI-Lab confirmed the mechanism on its kit: `max_num_batched_tokens=1024` is the whole engine step, so the long sparse-MLA prefill consumed nearly the full step and left only the small decode slice. Their `GLM53_MIXED_PREFILL_CHUNK=skip` policy restored ~68–69 tok/s in the retest.

**Dedupe:** Trap 128 is a scheduler-admission flag that the scheduler never reads. H30-11 is not that: here the budget is real and consumed, no preemption occurs, and the proposed fix intentionally refuses mixed prefill in a decode step. It may become a scoped Trap 128 extension or a separate “prefill/decode step budget starvation” owner after exact code-level dedupe.

### H30-12 — logged KV token capacity can wildly overstate real concurrent-session capacity

**Disposition:** LEAD_QUEUE_HIGH.

Primary issue + maintainer confirmation read:
https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/13

Before the allocator fix, the recipe logged roughly **1,096,153 GPU KV tokens**, yet one ~36K request consumed **44.6%** of the pool and three ~256K sessions could not reside concurrently. Cause: five DFlash2 SWA layers consumed standalone globally unique BlockPool IDs; much of the hybrid Mamba + sliding-window demand was effectively length-independent. Simply lowering `max-model-len` did not turn leftover UMA into proportional extra slots.

MiaAI-Lab's padded slot-share fix raised logged capacity to ~1.75M and dropped the ~36K request from 44.6% to ~16%, after which three concurrent requests were accepted in the reported test.

**Minefield lesson:** “KV cache size: N tokens” is not automatically “N interchangeable tokens of admission capacity” on a grouped/hybrid cache layout.

**Related:** Trap 106 (KV occupancy ceiling), Trap 135 (client vs execution concurrency), U34 (DFlash/DCP budget undercount). Exact owner here is **block-ID/layout tax making nominal token capacity non-fungible**.

### H30-13 — a 20K context gate can falsely certify a kernel that hard-crashes around 24–32K

**Disposition:** LEAD_QUEUE / likely Trap 61 extension.

The 4x repo documents an SM121 top-k kernel whose block resource requirement exceeds hardware capacity only when the long-context path reaches a deeper shape. A 20K gate passed, while 28–32K testing exposed the hard failure. `/v1/models` could still answer while the engine was dead; that readiness half is already Trap 112.

Preserve the new evidence as a **validation-threshold** lesson unless a distinct resource-shape mechanism survives dedupe with Trap 61.

### H30-14 — `gpu_memory_utilization` can create periodic swap stalls that an average tok/s hides

**Disposition:** LEAD_QUEUE / performance-measurement extension.

The 1M report describes a configuration where host swapping produced long decode bursts separated by multi-second zeros. A single average throughput number made this look like a uniformly slower model instead of periodic memory-stall behavior.

**Check:** publish inter-token gap distribution / windowed throughput beside the average; monitor swap-in/out and UVM activity. This may extend existing run-order/memory-pressure traps rather than become new.

### H30-15 — Qwen3.8 speculative “doom loop” is a compound state-alignment bug, not one bad token sampler

**Disposition:** LEAD_QUEUE_HIGH; split into independently testable sub-candidates before promotion.

Source report:
https://github.com/MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks/blob/main/logs/qwen38-doom-loop-bug-report.md

The dedicated report attributes repetitive corruption such as `test test test ...` after MTP lookahead advances to three coupled defects:

1. **MTP shift:** the accepted/sampled token for the next MTP step is written/broadcast at the wrong end of the sequence, so the draft state starts diverging after the first speculative step.
2. **LSE alignment:** target and draft log-sum-exp rows become off-by-one after compacted hidden-state handling, corrupting acceptance correction.
3. **Master-slice indexing:** full-batch `position_ids` offsets are applied to a compressed row layout, so concurrent multi-token verify can slice the wrong KV/state rows.

**Why not merge these into Trap 122:** Trap 122 owns full CUDA-graph corruption of Qwen3.8 MTP verification. This report claims positional/state-alignment defects that can exist independently of the graph mode. Before promotion, each submechanism needs a one-variable test because a compound patch can make all three disappear at once without proving which was sufficient.

### H30-16 — blanket FP8 “KV cache” can be wrong when part of the state is recurrent, not ordinary KV

**Disposition:** LEAD_QUEUE_HIGH / quantization-runtime boundary.

The Qwen3.8 dual-Spark recipe explicitly distinguishes SWA attention KV from GDN/DeltaNet recurrent state. The recurrent state follows activation/state precision constraints and should remain BF16; treating all cache groups as ordinary FP8 KV can be semantically wrong even when a CLI exposes one umbrella `kv-cache-dtype` concept.

**Minefield angle:** one “KV dtype” flag can hide heterogeneous state with different numerical requirements.

**Related:** Trap 10 (label is not execution path) and Trap 116 (load success is not first-forward dtype proof). Potential new owner is **heterogeneous cache groups do not share one safe dtype contract**.

### H30-17 — generic DFlash KV unification can allocate ~order-of-magnitude more memory than the custom grouped layout

**Disposition:** LEAD_QUEUE_HIGH.

The Tony 1M DFlash notes report that forcing a generic uniform-page abstraction onto GLM's custom grouped/hybrid cache layout can produce an enormous per-request allocation (source reports roughly 27.9 GiB / about 13x the intended shape). This is not just “DFlash uses memory”; it is an abstraction mismatch where a generic allocator makes heterogeneous groups pretend they have one page geometry.

**Dedupe:** adjacent to H30-12 and U34. H30-12 is BlockPool ID consumption on a standalone SWA group; H30-17 is **layout unification multiplying bytes per request**. Keep separate until code-path comparison proves same owner.

### H30-18 — rank-dependent KV headroom can follow TP role, not physical machine

**Disposition:** SOURCE_CONFLICT / OPEN.

The 4x repo reports the worker rank profiling several GiB less KV headroom than the head, with the disparity following rank rather than a particular Spark. Because a distributed pool is limited by the minimum rank, one asymmetric role can cap the whole system even when physical memory looks matched.

The source did not establish the root cause; hypotheses include communication/context/runtime-role allocations. Preserve as an open question, not a trap.

---

# C. tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark

Source: https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark

### H30-19 — a tool-call required-argument failure can be production-state dependent while solo replay is clean

**Disposition:** LEAD_QUEUE_HIGH, but mechanism remains open and a maintainer failed to reproduce the small synthetic.

Primary issue read:
https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/10

The reporter captured a byte-identical production request that failed repeatedly with blank/missing required tool args, yet 15+ standalone replays were clean. A heavy concurrent+cold-prefill synthetic produced one malformed `{}` call amid many timeouts; homogeneous concurrency did not.

MiaAI-Lab then ran 53 live synthetic cases on the recipe and observed **0 blank args / 0 timeouts**. Their analysis also ruled out a process-wide glm47 parser-state table and noted that `{}` can result from several distinct states: actual model omission, generation ending mid-call, client timeout/abort, or streaming assembly finishing a name-only call.

**Therefore:** this is valuable precisely because it is unresolved. Do not publish “DFlash corrupts tool args.” The open Minefield question is: **can a production batching/cache/spec state make tool arguments disappear when solo replay of the same body is clean, or are the observed blanks timeout/truncation/parser-finishing artifacts?**

**CONFIRM:** capture one failing turn with raw assistant token IDs/XML, finish reason, completion budget, timeout state, prefix-cache hits and parsed OpenAI object; reproduce under same concurrent state; then A/B speculation off, prefix cache off, streaming off.

### H30-20 — shape-window NaN can hide between clean small and clean large probes

**Disposition:** EXISTING_EXTENSION candidate to Trap 51 unless source inspection proves a distinct registry owner.

The Tony 2x deployment report describes a FlashInfer FA2/MLA path on SM121 where some mid-size row counts (roughly 64–256 in the reported environment) generated NaNs/deterministic garbage while tiny rows and much larger rows were clean. Updating FlashInfer removed the failure.

The important new evidence is **shape-selective**: a “small smoke + big throughput bench” pair can both be green while the production row range between them is corrupt.

Trap 51 already owns a single-backend fused path producing NaN on a particular architecture/activation shape. Prefer extending its test matrix to include row-shape sweeps unless the primary upstream bug establishes a distinct mechanism class.

### H30-21 — stale worker image can make a distributed A/B compare two different runtimes

**Disposition:** EXISTING_EXTENSION to Trap 53 / distributed provenance controls.

The day-0 report records remote edits that did not actually land on one worker, leaving ranks with different image/overlay state while the operator believed the cluster had been updated uniformly.

Do not mint “cross-rank image mismatch” from this report alone; extend the post-restart identity proof: immutable digest + overlay hash + runtime commit must be checked independently on every rank.

### H30-22 — speculative structured output can cross a grammar termination/reasoning boundary inside one draft window

**Disposition:** LEAD_QUEUE_HIGH; primary runtime patch review needed.

The Mia GLM repo carries fixes/notes around XGrammar + speculation where a grammar matcher can be terminated by a stop token or gated off during `<think>`, while a multi-token speculative tail still contains tokens generated under the previous grammar state. If those later draft tokens are advanced against the newly terminated/activated FSM, the server logs `Failed to advance FSM` / matcher-after-stop warnings and can roll back heavily or fail the request.

This is adjacent to U32 (speculative EOS/stop crossing length cap) but not obviously the same: the proposed owner is **grammar state transition occurring inside a speculative verification window**.

**Next action:** read the exact vLLM/XGrammar patch commits before promotion and separate (a) matcher-after-stop tail advancement from (b) reasoning-end mid-window activation.

### H30-23 — DFlash attention backend can preserve position-0 acceptance while silently destroying later draft positions

**Disposition:** EXISTING_EXTENSION to U33 unless a second mechanism is proven.

Mia's GLM recipe reports that a causal-mask choice on the draft attention path could leave first-position acceptance healthy while later draft positions collapsed, cutting structured throughput roughly in half without a crash. This is the same dangerous shape as U33: causality semantics can drift while the checkpoint and request remain unchanged.

Use per-position acceptance, not only mean acceptance, as the portable check.

### H30-24 — custom grouped KV layout cannot always be collapsed into a generic uniform allocator

**Disposition:** LEAD_QUEUE_HIGH.

This is the allocator counterpart to H30-17: GLM's hybrid groups (MLA/indexer/Mamba/K-pool tail/DFlash SWA) have different page/state geometry. A generic unification step can satisfy a type-level interface while producing absurd memory economics or invalid sharing.

**Check:** report bytes/token and block/ID geometry **per cache group**, then the unified effective allocation. Do not infer correctness from a single global “KV tokens” number.

### H30-25 — DFlash acceptance and tok/s are workload properties, not engine constants

**Disposition:** EXISTING_EXTENSION to Trap 111.

The Tony/Mia measurements show materially different speculative acceptance for structured/math/code versus open prose on the same engine. Preserve as GLM/DFlash evidence for Trap 111; do not publish one median acceptance rate as “the model's DFlash acceptance.”

### H30-26 — temperature zero can materially change speculative throughput

**Disposition:** EXISTING_EXTENSION to sampling/measurement traps (17/94/111 family).

The source reports meaningful speed movement when deterministic top-1 verification replaces probabilistic sampling. This is not a new runtime win unless sampling is held fixed.

---

# D. MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks

Source: https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks

### H30-27 — `MAX_NUM_SEQS=4` does not mean four long contexts fit

**Disposition:** EXISTING_EXTENSION / possible H30-12 evidence.

The repo's long-context issues make the distinction explicit: `max_num_seqs` is an engine scheduling width, while actual resident long-context capacity is limited by grouped KV/block-ID geometry. Lowering `max-model-len` may not recover proportional slots when fixed/windowed state dominates.

This should enrich Trap 135 and H30-12 rather than become another “concurrency isn't concurrency” entry.

### H30-28 — cold-prefix “fix” can intentionally serialize prefills and create a TTFT staircase

**Disposition:** CONTROL_ONLY / measurement warning.

`GLM53_MIXED_PREFILL_CHUNK=skip` protects a decoding lane by refusing to schedule a peer prefill in the same step. That solves H30-11's decode-floor problem, but creates a deliberate latency trade: prefills queue/serialize. A benchmark must report both decode preservation and waiting/TTFT effects.

Not a trap by itself; it is an example of one metric improving because another is intentionally sacrificed.

### H30-29 — prefix-cache “cold” benchmarks can silently become warm when the server has no reset primitive

**Disposition:** EXISTING_EXTENSION to Traps 54/60/92.

The repo's cache testing had to salt/uniquify content because repeated “cold” requests were actually hitting retained prefix state. Preserve the exact fix: a cold benchmark needs a unique-prefix or cache-reset proof, not just the word “cold” in the harness.

### H30-30 — stdout diagnostics from runtime hooks are part of your data plane if shell command substitution captures them

**Disposition:** same owner as H30-10; do not split.

Generalization of issue #15: any `sitecustomize`, shell profile, wrapper, patcher, warning or banner that writes to stdout can corrupt machine-readable command-substitution output. The rule is stronger than “send logs to stderr”: **machine-readable stdout must be treated as an API boundary and tested under cold + warm environment startup.**

### H30-31 — an apparently excellent tools+JSON silent-fabrication report was retracted by its own reporter

**Disposition:** DO_NOT_QUEUE as a bug claim; preserve as source-vetting evidence.

Issue read:
https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/24

The issue demonstrated `tools` + `response_format:{"type":"json_object"}` returning HTTP 200, no tool call, and invented weather JSON while `<tool_call>` tokens conflicted with a JSON FSM. However, minutes later the reporter closed the issue and wrote: **“I'm not convinced this bug is valid. Closing and will re-file if there's a new observation that manifests in a reasonable circumstance.”**

Minefield should not launder the initial dramatic reproduction into a confirmed runtime bug. Keep it as a reminder that a syntactically possible API combination is not automatically a valid application contract on the tested stack.

### H30-32 — source provenance can be insufficient even when the image digest is exact

**Disposition:** LEAD_QUEUE / provenance.

One issue notes an image whose binary digest is known while the effective source/runtime build commit is `unknown` and local wheels/patches are not reconstructable from a public commit. An immutable image digest proves binary identity; it does **not** prove source reproducibility.

Potential owner: version/provenance rather than serving correctness. Promotion bar should require a concrete consequence (e.g. inability to verify a security/correctness fix), not merely missing metadata.

---

# E. MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark

Source: https://github.com/MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark

### H30-33 — `thinking:false` free-text behavior is already canonical Trap 126

**Disposition:** EXISTING_EXTENSION ONLY.

This exact family is already represented by Trap 126: on the tested Ling-3.0 path, `thinking:false` in free text did not mean reasoning work stopped and reasoning could spill into `content`, while structured JSON materially changed behavior.

Do not mint a new candidate from the repo README. Use new Ling measurements only to extend Trap 126's stack/version scope.

### H30-34 — a GPU-memory-fraction flag can be accepted yet be irrelevant under a unified-memory manager

**Disposition:** EXISTING_EXTENSION / candidate evidence for Trap 13 and effective-config checks.

The Ling issue discussion reports `--mem-fraction-static` as ineffective on the DSpark path because memory is managed through the unified-memory mechanism rather than the ordinary static-pool interpretation.

Portable check: do not infer a memory cap from parser acceptance of a flag. Measure the effective allocation/pool after startup.

### H30-35 — launch-memory telemetry is not steady-state memory

**Disposition:** EXISTING_EXTENSION / memory qualification control.

The Ling repo reports a large first-request memory jump after a much smaller launch footprint. Do not call a model “fits with X GiB headroom” until first forward + representative generation has occurred.

This is squarely in Trap 116/readiness-memory territory unless a new allocator mechanism is identified.

### H30-36 — CUDA-graph disablement on SM121 is a stack-specific control, not evidence that CUDA graphs are universally unsafe

**Disposition:** CONTROL_ONLY.

The recipe disables CUDA graphs because the tested path was unstable. Minefield already contains precise CUDA-graph failure mechanisms (e.g. Trap 122). Keep the exact build/path requirement attached to those mechanisms; do not promote “disable CUDA graphs on GB10” as a universal rule.

---

# F. MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks

Source: https://github.com/MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks

### H30-37 — `/v1/models` can be green before the first chat socket/request path is actually stable

**Disposition:** EXISTING_EXTENSION to Trap 112.

The Qwen repo issue tracker reports the API process returning a valid model card while an immediate first chat request can be reset, then a retry ~100 ms later succeeds with the process never dying. This is a clean extension to the readiness ladder: model-list readiness is still not equivalent to first-generation readiness.

Do not create a new trap; add the “first request race after model-list 200” as another Trap 112 example if source evidence is promoted.

### H30-38 — tool arguments serialized as a JSON string instead of a mapping is already covered

**Disposition:** EXISTING_EXTENSION to the current tool-argument representation trap (Trap 43 family).

The Qwen parser work fixed a path where arguments were emitted with the wrong host-language type despite looking JSON-like. Preserve as a Qwen parser example only.

### H30-39 — NVML memory APIs can fail on GB10 UMA while inference is completely healthy

**Disposition:** LEAD_QUEUE / observability, likely Trap 96 extension.

The Qwen repo notes `nvmlDeviceGetMemoryInfo_v2` returning an error on the unified-memory platform, breaking scripts that assume discrete-GPU NVML memory fields are universally available. The model can still serve correctly.

**Minefield angle:** monitoring failure can be misread as GPU failure or can silently remove a memory safety signal from a harness.

Before promotion, dedupe with Trap 96's host/device memory-reporting scope.

### H30-40 — `/metrics` availability is a build capability, not an OpenAI-serving guarantee

**Disposition:** CONTROL_ONLY / versioning note.

One Qwen build returned 404 for the expected vLLM metrics surface and the recipe added Prometheus middleware. Do not assume `/metrics` exists because `/v1/chat/completions` does. Capability-probe observability endpoints before relying on a soak monitor.

### H30-41 — random benchmark prompt generation can create 3–6% apparent throughput movement

**Disposition:** EXISTING_EXTENSION to Traps 54/111 and benchmark fixture controls.

The repo reports repeated runs of nominally the same benchmark yielding materially different tok/s because prompt/output shape changed. Fix by freezing tokenizer-exact fixtures and report actual ISL/OSL.

### H30-42 — streamed text chunks are not tokenizer tokens

**Disposition:** EXISTING_EXTENSION to U21 / token-accounting work.

UI/client counters based on SSE text chunks can disagree with tokenizer IDs, particularly around reasoning/control tokens. Do not use chunk count as token count or throughput denominator.

### H30-43 — shared `/dev/shm` can become a cross-service CUDA-IPC collision surface

**Disposition:** LEAD_QUEUE.

The Qwen dual-service notes require process/service isolation around CUDA IPC shared-memory artifacts. A second serving process can collide through shared shm naming/state even when ports, model paths and GPUs appear separated.

**Promotion bar:** reproduce a collision with shared shm and remove it with per-service shm isolation while holding runtime/model constant.

### H30-44 — rough video-frame estimation can OOM the preprocessor before model memory is the problem

**Disposition:** LEAD_QUEUE, lower priority.

The Qwen repo fixed a media path where a rough bytes-to-frame estimate could allocate thousands of frames for a large video before the model-serving path had a chance to enforce a sensible limit. The resulting OOM can be misattributed to context/model fit.

This is multimodal preprocessing, not GPU KV capacity. Keep those owners separate.

### H30-45 — stale hard-coded RDMA GID selection is already Trap 114 territory

**Disposition:** EXISTING_EXTENSION.

The Qwen multi-node recipe carries the same portability lesson: GID/index values are host/fabric observations, not portable constants. Do not mint a Qwen-specific duplicate.

### H30-46 — shared network JIT/compiler caches can corrupt multi-node build products

**Disposition:** EXISTING_EXTENSION to upstream U19.

The Qwen recipe warns against sharing compiled CuTeDSL/JIT artifacts across nodes and uses node-local cache identities. Preserve as a GB10/Qwen reproduction lead for U19, not a new trap.

### H30-47 — full CUDA graphs + Qwen3.8 MTP corruption is already Trap 122

**Disposition:** EXISTING_EXTENSION ONLY.

The recipe's PIECEWISE/full-graph guidance belongs under Trap 122. The new value in this harvest is H30-15's independent positional/LSE/master-slice “doom loop” mechanisms; do not conflate them with graph capture just because both manifest as MTP corruption.

### H30-48 — “standard NVFP4 loader” can load the wrong representation for a specialized SUH pack

**Disposition:** EXISTING_EXTENSION to Trap 10 / 116.

The Qwen recipe uses a specialized `nvfp4_suh` representation/path rather than assuming any generic `modelopt_fp4` loader is equivalent. Loader acceptance or a familiar quant label is not proof of the execution representation.

---

# Source evolution / contradictions worth preserving

## C30-01 — GB10 swap guidance evolves across the Tony recipes

The higher-level cookbook and later dedicated recipes are not identical about swappiness/swap handling. Later failure forensics are more specific: active swapping can amplify UVM livelock, while *no swap at all* can allow a worker to be killed during a transient repack peak. Do not normalize these into one universal `swappiness=N` command. Treat swap policy as a workload/runtime-specific memory-control variable and record the exact source revision.

## C30-02 — DFlash performance numbers are not automatically cross-workload comparable

Several repos report large speculative speedups, but prompt family, thinking mode, sampling, context and acceptance distribution differ. Minefield should preserve the systems mechanisms without using unmatched speed numbers as cross-repo proof.

## C30-03 — a closed issue is not automatically “fixed”

This pass saw three different meanings of “closed”:

- issue #6: maintainer confirmed mechanism, shipped fix, posted before/after;
- issue #13: maintainer confirmed mechanism and linked allocator patch with live before/after;
- issue #24: reporter explicitly withdrew confidence in the bug claim.

Always read closure/comment context before promoting a source.

---

# Dedupe map against current Minefield

These are the most important “do not mint twice” relationships found in this harvest:

- **Trap 10 / 116** — quant/loader label versus effective execution representation; covers Qwen `nvfp4_suh`, GLM EXL3 execution proof, first-forward dtype/path checks.
- **Trap 13 / 119 / 125** — GB10 unified-memory accounting; cookbook page-cache and memory-fraction observations are extensions unless a new allocator owner is proven.
- **Trap 28 / 91 / 92** — concurrency + speculative/cache state; relevant to unresolved H30-19, but not enough to claim same mechanism.
- **Trap 43 family** — tool args wrong host-language representation; Qwen parser string-vs-map is extension.
- **Trap 51** — single-backend fused-path NaN; Tony's shape-window NaN may extend this unless primary upstream source proves a distinct owner.
- **Trap 53** — config/restart never actually took effect; stale worker image/remote-edit failures extend the live-identity proof.
- **Trap 54 / 60 / 92** — cold/warm/prefix-cache measurement identity; Mia cold-prefix salting and Qwen run-to-run fixture drift extend these.
- **Trap 61** — nominal context window versus usable long context; top-k failure only beyond 24K likely extends it.
- **Trap 62 / U33** — wrong DFlash drafter/causality config; later-position acceptance collapse is extension unless distinct.
- **Trap 96** — host/device memory reporting; NVML UMA failure probably extension.
- **Trap 98 / 106 / 135 / U34** — speculative/hybrid KV capacity and concurrency semantics; H30-12/H30-17 are worth separate mechanism adjudication, not instant duplicates.
- **Trap 111** — speculative medians are content lottery; workload-dependent acceptance/tok/s extends it.
- **Trap 112** — readiness ladder; `/v1/models` green before first chat and engine-dead/model-list behavior are extensions.
- **Trap 114** — hard-coded RDMA GID index portability; Qwen is another source.
- **Trap 122** — full CUDA-graph Qwen MTP corruption; keep separate from H30-15's positional/LSE/slice defects.
- **Trap 124** — GB10 stuck low-power state; do not merge H30-03's UVM livelock until mechanism equivalence is proven.
- **Trap 126** — Ling `thinking:false`; already canonical, no duplicate.
- **Trap 128** — decode starvation from an admission flag the scheduler never reads; H30-11 has a different reported scheduler-budget mechanism.
- **Trap 135** — client concurrency versus actual execution; grouped-KV admission capacity can explain why nominal max sequences still cannot be resident.
- **U19** — shared multi-node JIT cache corruption; Qwen local-cache guidance is extension.
- **U21** — stream chunks are not tokens; Qwen UI token counting is extension.
- **U32** — speculative stop/EOS length-boundary leak; structured grammar-state transitions need separate proof.
- **U33** — missing/changed DFlash causality semantics; TRITON_ATTN later-position acceptance collapse likely extension.
- **U35** — resolved dependencies still fail compile; mixed CuTeDSL nightly state extends this.

---

# Verification queue — best next experiments

These are the candidates with the best ratio of severity, reusability and testability. They are intentionally phrased as confirm/refute experiments rather than desired outcomes.

1. **H30-01 explicit KV pin / activation reserve** — on a scratch GLM lane, same runtime/weights, auto KV vs two explicit pins; short + long first-forward; capture profiled activation reserve and true UMA.
2. **H30-03 UVM livelock** — do not deliberately OOM a production Spark. If the state appears naturally, capture util/power/clocks/UVM thread/buddyinfo/swap/shard progress before recovery.
3. **H30-05 dependency-induced NCCL downgrade** — reproducible in a disposable venv/image without model weights; strongest cheap software test.
4. **H30-07 uninitialized pool IDs** — source-level unit test with poison/sentinel initialization; do not wait for a full model NaN.
5. **H30-08 ModelOpt corrupted token IDs** — first read vLLM #54150; if still valid, use deterministic token-ID probes plus tool-control-token cases.
6. **H30-10 warm-restart stdout contamination** — tiny deterministic container/shell repro; cheap and highly general.
7. **H30-11 mixed cold-prefill decode starvation** — already source-confirmed/fixed; exact duplicate pass against Trap 128 then likely upstream/community promotion path.
8. **H30-12 DFlash block-ID capacity tax** — source-confirmed/fixed; compare logged token pool against actual block IDs/request before/after slot-share.
9. **H30-15 Qwen MTP doom loop** — split into shift/LSE/slice one-variable tests; require token/logit/acceptance evidence, not only coherent output.
10. **H30-16 heterogeneous KV dtype** — assert effective dtype per cache group and compare recurrent-state correctness against BF16-state control.
11. **H30-19 production-only blank tool args** — wait for one artifact with raw XML/token IDs + finish/timeout/cache state before blaming DFlash/parser.
12. **H30-22 speculative grammar boundary** — primary patch/source read, then construct one draft window crossing `</think>`/stop into grammar-on state.
13. **H30-43 shared `/dev/shm` CUDA-IPC collision** — two isolated processes, shared vs private shm A/B.
14. **H30-44 media preprocessor frame-estimator OOM** — bounded synthetic video metadata test; no need to allocate the full erroneous frame set.

---

# Findings deliberately NOT promoted by this packet

- **Mia GLM issue #24 “tools + response_format fabricates data”** — reporter withdrew confidence and closed it. Preserve the source-vetting lesson, not the bug claim.
- **Ling thinking:false** — already Trap 126.
- **Qwen full CUDA-graph MTP corruption** — already Trap 122.
- **Qwen hard-coded GID** — already Trap 114.
- **Qwen shared JIT cache** — already U19.
- **Workload-dependent speculative acceptance** — already Trap 111 family.
- **Generic “disable CUDA graphs”, “use fp8 KV”, “MTP is faster”, “drop caches”** — configuration advice is not a trap without a demonstrated misleading failure mode.
- **Rank-headroom asymmetry** — preserved as open because root cause is not established.
- **Unmatched cross-repo tok/s comparisons** — not evidence of a model/runtime mechanism.

---

# Attribution / claim boundary

This packet is a **public-source mining pass**, not first-party Blackwellboy validation. Credit remains with the source repositories and issue reporters/maintainers:

- `tonyd2wild` for the GLM-5.3 DGX Spark cookbook, 4x 1M KV forensics, and 2x DFlash deployment report.
- `MiaAI-Lab` and the individual issue reporters for GLM-5.3 EXL3, Ling-3.0 and Qwen3.8 Flash-Next recipe evidence, fixes and issue discussions.
- Referenced upstream projects (vLLM, SGLang, FlashInfer, XGrammar, NCCL/CuTeDSL) retain credit for their own bugs/fixes; where this packet did not read the primary upstream issue/PR, the item stays community-source and is explicitly marked for follow-up.

No public Minefield trap should quote a community recipe's number as first-party Blackwellboy measurement. Promotion requires the existing status vocabulary and evidence bar in `MAINTAINING.md`.
