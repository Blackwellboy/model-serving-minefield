# DeepSeek V4.1 Flash SAGE EXL3 — one DGX Spark GB10 notes

**Evidence status: first-party observed. Canonical-trap ownership is not assigned by this page.**

This page records an independent September 2026 qualification of `vcruz305/DSV4.1-Flash-SAGE-EXL3-1.59bpw` on one 128 GB DGX Spark GB10 using the author's native ExLlamaV3 fork.

Tracking issue: [#126](https://github.com/Blackwellboy/model-serving-minefield/issues/126).

Upstream report: [vcruz305/DeepSeek-V4.1-Flash-EXL3-DGX-Spark-recipe#23](https://github.com/vcruz305/DeepSeek-V4.1-Flash-EXL3-DGX-Spark-recipe/issues/23).

## Tested identity

- model: `vcruz305/DSV4.1-Flash-SAGE-EXL3-1.59bpw` @ `0c29707b…`
- recipe: one-Spark TP1 at `6cd44b3bd8478922396fd623a39010ba09d4de7b`
- ExLlamaV3: `vcruz305/exllamav3@954a8ca6e59d`
- CUDA 13, `TORCH_CUDA_ARCH_LIST=12.1a`
- ATS addressing mode
- 64-byte re-laid checkpoint on internal NVMe

## Finding 1 — the fast copy-main placement crossed this Spark's real UMA cliff

The documented fast placement:

```bash
EXL3_ATS_MMAP=1
EXL3_ATS_COPY='^(?!mtp\.)'
```

failed on this system with both DRAFT=0 and DRAFT=1. Pre-load MemAvailable was about 115–117 GiB, then fell to zero during load; CUDA allocation failed and the kernel OOM-killed the model process plus user-session helpers. The host was temporarily unreachable.

This was not a hard headless requirement on this box: the measured GUI footprint was only about 0.12–0.14 GiB.

The safe control was fully aliased placement:

```bash
EXL3_ATS_MMAP=1
EXL3_ATS_COPY='^$'
```

That profile loaded stably with roughly 98–100 GiB MemAvailable in DRAFT0 and a large operational safety margin.

Minefield lesson to adjudicate against existing UMA traps: **nominal checkpoint/model byte arithmetic does not prove a GB10 unified-memory placement recipe is operationally loadable; loader/runtime/workspace peaks can cross the host-wide cliff.**

## Finding 2 — fully aliased MoE weights have a large cold-prompt page-fault cliff

With the stable fully aliased DRAFT0 profile:

- cold example: 2.66 tok/s, ~5,946 MiB NVMe reads, ~28K major faults;
- identical warm repeat: ~8.96 tok/s, ~0 NVMe reads, ~0–1 major faults;
- four-prompt zero-fault warm ceiling: roughly 9.05–9.18 tok/s;
- new/multi-prompt workloads remained slower because different prompts activated and faulted different expert pages;
- measured working sets varied roughly 7.8–33.3 GiB by prompt.

Hardware/runtime controls were healthy: about 2574 MHz SM clock, 86–95% GPU utilization, no throttle, ~116.01 GiB aliased, no policy copies, no alignment fallback, and the sm_121a EXL3 mixed-K path active.

Operational lesson: **warm-repeat throughput can materially overstate service throughput for mmap/UVA/ATS MoE weights when novel prompts demand-fault different expert pages from NVMe.** Record major faults and storage traffic next to warm/cold throughput.

This should be compared with evaluation trap 54 and existing cache/runtime traps before deciding whether it is a new owner or an extension.

## Finding 3 — DeepSeek V4.1 turn serialization can masquerade as quant failure

The initial quality harness produced misleading immediate-EOS/weak results. Correct serialization on this path required effectively:

```text
BOS + <｜User｜>…<｜Assistant｜></think>
```

with the delimiter/control tokens encoded as special tokens. Missing `</think>` and/or encoding those delimiters as normal text produced false quality failures. Once corrected, DRAFT0 and native DRAFT1 quality passed.

Treat this as an extension candidate for the existing template/reasoning family rather than minting a new trap solely from this observation.

## Native DRAFT1 is useful on the safe fully aliased profile

With `EXL3_DSPARK_CONF=0.7`:

- quality: PASS;
- acceptance: ~0.814;
- warm coding: ~20.17 tok/s;
- warm reasoning: ~13.5 tok/s;
- short prose: ~8.5–9 tok/s.

The benefit is prompt-dependent, so one aggregate speculative-acceptance or throughput number is not representative of every task family.

## Finding 4 — TabbyAPI DRAFT0 works; in-pack MTP DRAFT1 does not yet

TabbyAPI `53da7919d4e45c63f4acbc00cbe0f60a1ce65` preserved ExLlamaV3 `954a8ca6e59d` and qualified end-to-end with the **safe fully aliased DRAFT0** profile:

- load ~26.2 s;
- ~116 GiB aliased / ~0 copied;
- ~98 GiB MemAvailable;
- raw completion PASS;
- chat PASS;
- streaming PASS;
- JSON PASS;
- multi-turn PASS;
- 64-byte re-laid pad-tensor pack accepted;
- warm ~8.4–8.8 tok/s, only a small overhead versus native DRAFT0.

Tabby DRAFT1 behaved differently:

- it correctly detected the in-checkpoint `mtp` component;
- it did not load a second checkpoint pack;
- the stock draft-first / single-GPU autosplit path did not leave a safe route for the main-model load under GB10 ATS;
- attempts to reserve more space for the draft starved the main load;
- native ExLlamaV3 DRAFT1 remained healthy on the same checkpoint.

Current evidence therefore supports a **TabbyAPI/ExLlamaV3 single-GPU draft-load ordering/autosplit integration problem**, not a claim that DeepSeek V4.1 MTP is unsupported.

The upstream recipe author was sent the independent results in issue #23 above.

## Evidence boundary

These observations are useful troubleshooting data, but this page does not assign new canonical trap numbers. Promotion should compare:

- the UMA load cliff against existing unified-memory/admission traps;
- the cold expert-fault result against trap 54 and existing cache/run-order ownership;
- the chat serialization result against existing template/thinking traps;
- the Tabby DRAFT1 failure as a first-party integration lead until a code-level fix or independent reproduction exists.
