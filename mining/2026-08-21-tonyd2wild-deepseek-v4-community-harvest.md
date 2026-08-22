# 2026-08-21 — tonyd2wild DeepSeek V4 Flash / DGX Spark community harvest

Source repository reviewed at current main on 2026-08-21:

- https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark
- reviewed main: `b61440dd579b7f53279af79dcc2fb573fa499ec3`

This note is the audit trail for a source-mining pass requested by Blackwellboy. The source repo contains a mix of merged fixes, measured deployment findings, corrected earlier hypotheses, negative reproductions, and still-open mechanism questions. We preserve those classes separately rather than flattening every interesting line into a canonical trap.

## Promoted to the explicit upstream tier

These are public, attributed, measured reports that this registry has **not** independently reproduced. They therefore live under `upstream/`, do not count toward the canonical registry total, do not enter Core, and do not count toward doctor coverage.

- **U17** — client stop strings firing inside think-in-prompt reasoning can truncate before `</think>` and turn a valid run into `content: null`; includes the speculative-decoding same-chunk edge. Source: merged PR #21, @Capicua25x.
- **U18** — explicit empty `tool_calls: []` on streamed content deltas can make JavaScript clients route valid text into the tool branch and display no answer. Source: merged PR #17, @hhackbarth.
- **U19** — putting writable JIT/workspace caches inside shared NFS `HF_CACHE` can produce cross-rank compile races, partial cubins and ABI-mismatched generated binaries. Source: issue #27 as integrated in merged PR #28, @antoniohlc / @tonyd2wild.
- **U20** — a direct GB10 QSFP pair can use one of two virtual NICs and leave substantial bandwidth unused; reported `nccl-tests` busbw 98 -> 161 Gb/s after dual-HCA configuration. Explicitly scoped to back-to-back pairs. Source: merged PR #35, @Capicua25x.
- **U21** — under the affected speculative vLLM stream, one SSE content delta can represent a decode step carrying several accepted tokens, so counting deltas as tokens measured 14.7 versus 60.1 actual tok/s on the same request. Source: 0731 loader/benchmark correction commit `8a62e8b8`, @tonyd2wild.
- **U22** — the DSpark draft loader silently skipped twelve shared-expert tensors at DEBUG level; target verification kept quality correct while acceptance and throughput collapsed. Source: commit `8a62e8b8`, @tonyd2wild. **Route this as upstream/corroborating evidence for existing Q17 / Issue #38, not as a second independent discovery or a new canonical trap number.**
- **U23** — sparse-index consumer gathered block-table entries for invalid padding tokens carrying stale `torch.empty` indices; validity/allocation bounds close that OOB but are not sufficient for total engine stability. Source: merged PR #4, @paulbrav.
- **U24** — per-request DSpark draft-KV slot ids can go stale across request condensation; contributor A/B: baseline 7/7 deaths in 76-142 min, guard-on two 4h clean runs, guard-off restores same assert at ~120 min on a 6->5 condensation tick. Source: merged PR #4, @paulbrav.
- **U25** — naive fixed-block uniqueness can call templated loops fresh: one captured runaway was 92% unique by 120-char blocks while phrase-level 8-gram novelty showed ~96% recycling. Source: merged PR #29, @Capicua25x.
- **U26** — fatal inner vLLM EngineDead can still end the outer serving container with exit code 0, so restart-on-failure logic leaves the endpoint down. Recipe mitigation `restart: unless-stopped` merged in PR #23. Original low-level CUBLAS trigger remains separate. Source: issue #8 / PR #23, @DaveCharland / @tonyd2wild.

## Existing canonical owners extended instead of allocating duplicate numbers

### Trap 01 — reasoning field names

Merged PR #23 documents that this DeepSeek V4 runtime returns `message.reasoning` / `delta.reasoning`, while two source-repo benchmark tools read only `reasoning_content`. That is the existing Trap 01 mechanism, so it is an addendum rather than a new entry.

### Trap 07 — reasoning-effort acceptance versus real semantics

Merged PR #24 found the stock tokenizer's `reasoning_effort` surface partially/mis-implemented: the single constant named MAX was actually the model's high prompt; ordinary high injected nothing; low was not distinct; real max was unreachable. The corrected table produced distinct `/tokenize` lengths 51 / 527 / 577 for low/high/max. That extends Trap 07 rather than allocating a duplicate.

## Retained as mining / not promoted

### Issue #8 CUBLAS engine death — root cause unresolved

The public issue captured a real failure chain: `CUBLAS_STATUS_INTERNAL_ERROR` -> EngineDead -> API shutdown -> later NCCL timeout. Several mechanism hypotheses were proposed, including unified-memory pressure, CUDA-graph interaction, JIT behavior and old-tree/parser differences. None is sufficiently isolated for a canonical mechanism claim.

The most important fresh negative evidence is the source maintainer's current-main cross-stack run: the 69-scenario public suite completed twice (**138 scenarios**) with **zero CUBLAS errors, zero EngineDead, zero NCCL timeout and zero JIT-monitor warnings** on the maintainer's current configuration. That narrows the incident but does not prove the old trigger fixed because runtime/config variables changed. Keep this as non-reproduction evidence, not "new main fixes CUBLAS".

**CONFIRM for a future promotion:** reproduce the original fatal CUBLAS signature under a pinned old/current A/B while isolating one proposed variable and capture memory/JIT/concurrency/context telemetry before the first error.

**REFUTE a proposed root cause:** the failure survives when that variable is removed or fails to reproduce under the allegedly causal condition while a different controlled variable restores it.

### Non-default port health check derived before `.env` source

PR #24 also fixed start/status/smoke scripts that constructed health-check URLs before sourcing `.env.dspark`, leaving checks pinned to port 8888 while the server correctly started on a configured non-default port. This is a clean source-level defect and may deserve promotion later, but it overlaps the broader readiness/config-drift class and has not been independently run here.

### `--tokenizer-mode deepseek_v4` ignoring model-dir `chat_template.jinja`

PR #23 documents that prompt formatting on this route comes from the built-in encoder rather than the model-directory Jinja; a Jinja override users expect to work can therefore have no effect. This is likely an extension of existing template-ownership traps rather than a new number. Preserve until owner reconciliation against traps 24/30/56/77.

### `reasoning_effort: none` plus `thinking: true` returning null content

PR #23 reports 4/4 null-content behavior from this contradictory control combination because chat-mode formatting and the armed reasoning parser disagree. This may belong under an existing parser/template mismatch owner; do not allocate a duplicate without a matched local reproduction.

### CUDAGraph capture-size derivation

PR #23 removes an explicit `max_cudagraph_capture_size` because the derived value could be truncated by the runtime and route hot shapes off the intended graph set. Later issue #8 discussion reports a different runtime where adding the exact missing batched-decode shape improved aggregate throughput. Interesting, but the stability/throughput mechanisms need one clean owner before promotion.

### Dual-HCA adjacent claims

PR #35 carries two adjacent observations: some pre-2026-04 BIOS configurations reportedly wire the second controller at Gen5 x2, and GB10 reports GDR 0 as a remaining ceiling. Those are not folded into U20's measured one-HCA-versus-two-HCA mechanism. The first needs its own pinned firmware/PCIe evidence; the second is a platform capability statement rather than a failure mechanism by itself.

### Fragmented-loop detector limitation

PR #29 discussion includes @brianmswheart's field report that 1-8k-character loop fragments separated by tool calls can stay below the detector's three-window floor. A proposed repeated-sentence/recycled-mass tier reportedly catches them. This is explicitly a limitation of U25's corrected detector and not yet promoted as a second mechanism.

## Claim discipline

- No item in this note upgrades public contributor measurements to `reproduced here`.
- The upstream U17-U26 entries are intentionally excluded from the canonical 124-entry registry count.
- Corrected/retracted source claims are not preserved as current facts. In particular, earlier DSpark draft-path attribution for the long-context crash was superseded by the later two-bug analysis, and earlier `draft_sample_method=probabilistic` speed/garble causality was withdrawn by the source repo.
- The source repo's current-main 138-scenario clean result is negative evidence, not proof that every historical engine-death mechanism is fixed.
