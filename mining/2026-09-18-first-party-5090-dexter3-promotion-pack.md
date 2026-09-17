# 2026-09-18 first-party promotion pack — RTX 5090 LCP + Dexter3 SAGE TP1

This note is an **adjudication packet, not a canonical trap promotion**. It preserves the evidence boundary from two Blackwellboy-owned campaigns and points the normal Minefield promotion machinery at the parts that are strong enough to keep.

Public tracking issues:

- #125 — RTX 5090 Qwen3.8 LCP/hybrid-SWA semantic-loop discriminator
- #126 — Dexter3 one-Spark DeepSeek V4.1 SAGE findings

Upstream report:

- vcruz305/DeepSeek-V4.1-Flash-EXL3-DGX-Spark-recipe#23 — independent GB10 TP1/Tabby validation

## Candidate A — long Qwen3.8 hybrid/SWA sessions can silently loop after LCP slot reuse

**Proposed tier:** `FIRST_PARTY_OBSERVED_UNPROMOTED`, with a strong discriminator but an intermittent failing arm.

Tested stack:

- RTX 5090
- Qwen3.8-27B-OBLITERATED Q4_K_M
- TurboQuant llama.cpp `tqp-v0.3.0`, `b1-30d6881` family
- 300032 context
- K=q8_0 / V=turbo4
- MTP n=2 unless explicitly disabled
- reasoning medium

Observed production failures remained transport-clean while generation entered a semantic cycle. MTP acceptance stayed high (~0.925–0.994), so acceptance was not a semantic-quality signal.

Matched ~45.5k-token discriminator:

| arm | result |
|---|---|
| checkpoints=0 + default LCP + MTP n2 | FAIL in 1/2 matched runs; one failure repeated a semantic span ~68 times / ~20k output tokens |
| checkpoints=0 + `--slot-prompt-similarity 0.0` + MTP n2 | PASS 2/2; LCP selections=0 |
| checkpoints=0 + default LCP + MTP OFF | FAIL; MTP is not required for the failure |

The LCP-off production winner then passed real Hermes/tool-agent recertification at approximately 45K, 64K, 90K and 128K with zero semantic loops, zero PEG-native failures and zero unbounded tool loops.

### Mechanism boundary

Forced full prompt re-processing still occurred with LCP disabled: 56 logged events / `n_past=0`-class resets across the recertification. No semantic loop occurred.

Therefore the current supported statement is:

> LCP-selected prior slot state is a high-confidence trigger/participant in the tested hybrid/SWA semantic-loop failure; forced full re-prefill alone is insufficient. The exact low-level corruption/recurrent-state mechanism remains unproven.

Checkpoint restoration was an earlier aggravating path, but it is not required: later production loops occurred with `ctx-checkpoints=0` and no checkpoint restore.

### Proven mitigation

```text
ctx-checkpoints=0
slot-prompt-similarity=0.0
MTP n=2
KV q8_0/turbo4
reasoning medium
```

Winner short decode was ~99.8 tok/s. Reliability was preferred over LCP reuse throughput.

### Promotion decision

Do **not** mint a canonical trap yet. The A arm is intermittent (1/2). Promote when either:

1. another bounded matched A-fail/B-pass replication lands, or
2. upstream/source evidence identifies the invalid LCP-selected hybrid/SWA slot transition.

Potential overlaps to adjudicate before promotion:

- runtime/47 `prefix-caching-autodisabled-hybrid`
- runtime/60 `cold-prefill-and-cache-hit-disagree`
- runtime/88 `cache-prompt-false-does-isolate-here`
- runtime/92 `prompt-cache-is-a-second-divergence-source`
- runtime/122 `full-cuda-graph-corrupts-qwen38-mtp-verification` — **not the same discriminator**
- upstream/U13 `llamacpp-iswa-cache-reuse-needs-swa-full`

A related observation was prepared for `ggml-org/llama.cpp#25592`, but the current GitHub integration did not have permission to post the comment. Preserve this note for a later manual/upstream submission; do not record the comment as sent.

Private owning receipts:

- `chatgpt-handoff/2026-09-17-RTX5090-SESSION2E-LCP-DISCRIMINATOR.md`
- `chatgpt-handoff/2026-09-17-RTX5090-SESSION2F-LCP-OFF-RECERT.md`

Evidence commits: `ec77d47100d09c7251600dc8c6b422f28788d302`, `a6737e689242a5be0ede858519362610701fc3ac`.

---

## Candidate B — GB10 UMA placement can cross the real load cliff despite nominal model-size arithmetic

**Proposed disposition:** first check whether this is an extension of traps 13 / 98 / 125 rather than a new canonical owner.

Tested on one 128 GB DGX Spark with ATS, `vcruz305/DSV4.1-Flash-SAGE-EXL3-1.59bpw`, ExLlamaV3 `954a8ca6e59d`.

The documented fast placement:

```bash
EXL3_ATS_MMAP=1
EXL3_ATS_COPY='^(?!mtp\.)'
```

failed for both DRAFT=0 and DRAFT=1 on this box. Pre-load MemAvailable was ~115–117 GiB; during load it fell to zero, CUDA allocation failed, and the kernel OOM-killed the model process plus user-session helpers. The host was temporarily unreachable.

The GUI was only ~0.12–0.14 GiB, refuting a hard "must be headless" explanation on this system.

Control:

```bash
EXL3_ATS_MMAP=1
EXL3_ATS_COPY='^$'
```

fully aliased Profile B remained stable with roughly 98–100 GiB MemAvailable in DRAFT0.

Candidate lesson:

> Nominal checkpoint/model byte arithmetic does not prove a GB10 UMA placement recipe is operationally loadable; runtime/workspace/loader peaks can cross the host-wide memory cliff.

Do not create a duplicate if an existing unified-memory trap already owns that mechanism.

---

## Candidate C — fully mmap/ATS-aliased MoE can show a large cold-prompt page-fault cliff

**Proposed tier:** `FIRST_PARTY_OBSERVED_UNPROMOTED` unless adjudication shows evaluation trap 54 already owns the exact failure.

Same fully aliased Profile B, DRAFT0:

- cold example: 2.66 tok/s, ~5,946 MiB NVMe reads, ~28k major faults;
- identical warm repeat: ~8.96 tok/s, ~0 NVMe reads, ~0–1 major faults;
- four-prompt zero-fault warm ceiling: ~9.05–9.18 tok/s;
- new/multi-prompt workloads remained slower because different prompts activated/faulted different MoE expert pages;
- measured per-prompt working sets varied roughly 7.8–33.3 GiB.

Controls:

- ~2574 MHz SM clock;
- ~86–95% GPU utilization;
- no thermal/power throttle;
- ~116.01 GiB aliased, zero policy copies, zero alignment fallback;
- sm_121a EXL3 mixed-K path active;
- warm NVMe/iowait ~0.

Candidate lesson:

> Warm-repeat throughput can substantially overstate service throughput for mmap/UVA/ATS MoE weights when novel prompts demand-fault different expert pages from NVMe. Record major faults and storage traffic alongside warm/cold decode results.

This may be an extension of trap 54's run-order/warm-cache ownership rather than a new trap. Preserve the measured MoE/ATS symptom even if adjudicated as an extension.

---

## Candidate D — TabbyAPI detects an in-checkpoint MTP head but draft-first single-GPU autosplit fails on GB10 ATS

**Proposed tier:** `FIRST_PARTY_OBSERVED_UNPROMOTED` until load-order/autosplit mechanism is fixed or independently reproduced.

Qualified DRAFT0 TabbyAPI `53da7919d4e45c63f4acbc00cbe0f60a1ce65` on fully aliased Profile B:

- ExLlamaV3 pin `954a8ca6e59d` preserved;
- ~116 GiB aliased / ~0 copied;
- load ~26.2 s;
- ~98 GiB MemAvailable;
- raw completion, chat, streaming, JSON and multi-turn PASS;
- warm ~8.4–8.8 tok/s;
- 64-byte re-laid pad-tensor pack accepted.

DRAFT1 result:

- in-checkpoint `mtp` component detected;
- no second model pack loaded;
- stock draft-first + single-GPU autosplit path did not leave a safe route for the main model to load under GB10 ATS;
- attempts to reserve more room for the draft starved the main load;
- native ExLlamaV3 DRAFT1 on the same fully aliased checkpoint works and passes quality.

Native DRAFT1 reference on this Spark: acceptance ~0.814, warm coding ~20.17 tok/s, reasoning ~13.5 tok/s.

Do not generalize this into "DeepSeek V4.1 MTP unsupported". The failure owner is currently the Tabby/native integration/load-order path.

Upstream report: `vcruz305/DeepSeek-V4.1-Flash-EXL3-DGX-Spark-recipe#23`.

---

## Existing-trap extension — DeepSeek V4.1 turn formatting can masquerade as quant failure

The first quality smoke was misleading. Correct serialization on this native path required effectively:

```text
BOS + <｜User｜>…<｜Assistant｜></think>
```

with the delimiter/control tokens encoded as special tokens. Missing `</think>` and/or encoding the delimiters as ordinary text caused immediate-EOS-looking failures; after correction, DRAFT0 and native DRAFT1 quality passed.

This should be adjudicated as an extension of the existing template/reasoning family, not automatically given a new trap number.

Private owning receipts:

- `chatgpt-handoff/2026-09-17-DEXTER3-VICTOR-TP1-FEASIBILITY.md`
- `chatgpt-handoff/2026-09-17-DEXTER3-PROFILE-B-DIAG.md`
- `chatgpt-handoff/2026-09-18-DEXTER3-WARM-CLOSURE.md`
- `chatgpt-handoff/2026-09-18-DEXTER3-TABBY-QUAL.md`

Evidence commits include `b3f81541`, `762f3cab`, `af6855a0`, `523d7741`.

## Recommended next adjudication

1. Keep the 5090 LCP case staged with discriminator; do not count it yet.
2. Extend an existing UMA trap with Candidate B if ownership fits.
3. Add Candidate C to the public first-party lead catalogue if trap 54 does not already own the exact MoE-demand-fault symptom.
4. Add Candidate D to the lead catalogue as a TabbyAPI/GB10 MTP integration lead unless Victor provides a fix/reproduction that justifies a stronger tier.
5. Fold the DeepSeek serialization finding into the existing template family.
