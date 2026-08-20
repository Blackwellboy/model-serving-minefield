# 2026-08-20 — vcruz305 / Victor Cruz EngineCore-orphan mining and adjudication

## Purpose

Mine PR #53 (`vcruz305:add-vllm-enginecore-orphan-trap`) as an evidence packet rather than treating its generated file count as twenty-three independent findings. Preserve Cruz's authored commit and credit, separate measured facts from generated surfaces and hypotheses, search the existing registry for ownership collisions, and inspect public upstream evidence for corroboration or contradiction.

## What PR #53 actually contains

The PR changes 23 files, but most of that volume is deterministic registry regeneration after adding one canonical candidate. The new source-level content is concentrated in:

1. `traps/runtime/123-vllm-v1-enginecore-orphan-holds-gpu-memory.md` — contributor narrative and runnable diagnosis.
2. `checks/vllm_enginecore_orphan_probe.py` — offline observation adjudicator.
3. README / changelog integration.
4. Generated `dist/`, `minefield/data/`, registry and web surfaces.

Do not count the regenerated bundles as additional independent measurements.

## Contributor-measured facts retained

Source: Victor Cruz / `@vcruz305`, PR #53 and authored commit `05f5729f5589417f8c09e41796db5b37b5faac4f`.

- Date observed: 2026-08-19.
- Hardware: DGX Spark / GB10, 121 GiB unified memory.
- Runtime: vLLM V1 `0.1.dev1+g75231eff2.d20260809`, single-node `uniproc` executor.
- Model class: `NemotronHForCausalLM`, 30B-A3B hybrid Mamba+MoE, NVFP4.
- Trigger used in the measured sequence: direct `kill -9` of the outer API-server PID while iterating launch flags.
- After that PID was gone, a distinct `VLLM::EngineCore` process remained.
- Contributor-reported EngineCore-owned GPU memory: **104277 MiB**.
- Next launch failed with free memory `8.88/121.69 GiB` against desired utilization `0.85` / `103.44 GiB`.
- The sequence occurred twice in the same session.
- Killing the surviving EngineCore directly cleared the measured state.

The LoRA merge, Nemotron family and NVFP4 are lane descriptors. The PR does not isolate any of them as causal, and the canonical entry must not imply that they are.

## Source inspection: what vLLM itself supports

Read current upstream on 2026-08-20.

### V1 process architecture

Primary source: <https://github.com/vllm-project/vllm/blob/main/docs/design/arch_overview.md>

Current vLLM documentation explicitly separates:

- the API server process;
- an EngineCore process per DP rank;
- GPU worker processes that load weights and manage GPU memory.

The API server communicates with EngineCore over ZMQ. This independently supports Cruz's process-separation premise and makes the finding a runtime lifecycle trap rather than a Nemotron-specific model trap.

### Graceful lifecycle machinery exists

Primary source: <https://github.com/vllm-project/vllm/blob/main/vllm/v1/engine/utils.py>

Current source creates EngineCore with a multiprocessing context and attaches a process-manager finalizer / `shutdown()` path. Therefore the broad sentence "killing the API server does not kill EngineCore" is too wide if read as a claim about all normal shutdowns and all builds.

The contributor's measured discriminator is narrower and defensible:

> Direct SIGKILL of only the outer API-server PID bypassed the parent's normal cleanup path on the pinned build, while the distinct EngineCore process survived and retained its GPU allocation.

This is the wording promoted into Trap 123.

## Independent public corroboration

These reports are not Blackwellboy reproductions and do not replace Cruz's contributor-measured status. They are useful because they show the lifecycle class is not unique to his DGX Spark.

| Source | Stack | Relevant observation | What it corroborates |
|---|---|---|---|
| [vLLM #47266](https://github.com/vllm-project/vllm/issues/47266) | vLLM 0.24.0, RTX PRO 6000 Blackwell SM120 | abrupt parent teardown leaves `VLLM::EngineCore` / worker processes alive, retaining GPU memory; next launch gets the same free-memory-utilization class of error | NVIDIA discrete-GPU instance of parent/child teardown miss + resource retention |
| [vLLM #48234](https://github.com/vllm-project/vllm/issues/48234) | vLLM 0.24.0, Qwen3.6 NVFP4 + DFlash, RTX PRO 6000 | crashes leave orphaned `VLLM::EngineCore` processes retaining GPU memory; cleanup kills EngineCore before restart | second NVIDIA Blackwell report of EngineCore retention after abnormal termination |
| [vllm-metal #479](https://github.com/vllm-project/vllm-metal/issues/479) | vllm-metal / Apple silicon | investigator explicitly found `pkill -f "vllm serve"` did not match renamed `VLLM::EngineCore`, leaving EngineCore/resource-tracker processes; later proved their main scheduler stall was separate | process-title / pattern-kill failure mode, not Cruz's NVIDIA memory amount |

The metal report is deliberately not used as a GPU-memory replication.

## Nearby evidence deliberately *not* folded into Trap 123

### Trap 119 — shared-pool free-memory drift

`traps/memory/119-free-memory-drifts-down-after-churn.md` already owns a different mechanism: moving free memory on unified-memory systems from shared host/GPU pressure, page cache, pinned buffers, swap and orphaned contexts. The symptom can look similar, but Trap 123 has a stronger discriminator: a specific surviving EngineCore PID owns the missing GPU memory after the parent-only kill.

Routing rule:

- EngineCore PID survives and owns non-zero GPU memory after outer PID death -> Trap 123.
- No EngineCore ownership proof; free memory merely remains low or drifts -> do not diagnose 123; inspect Trap 119 / other memory-state owners.

### vLLM #42017 — residual memory with no visible process

A current GH200 report describes substantial GPU memory remaining after a vLLM failure while `nvidia-smi` shows no process. That may be a driver/context/resource-release class and specifically lacks Trap 123's live EngineCore discriminator. It is not promoted or merged into 123 from this mining pass.

### Trap 116 — Cruz's earlier contribution

Cruz already has a substantive Minefield contribution in Trap 116. He authored the F16 embedding patch chain and the instrumentation that proved first-forward completion; Blackwellboy supplied the external multi-node hardware qualification and evidence adjudication. PR #53 is therefore not his first useful contribution to this project, only his first direct canonical-trap PR.

## Offline-check adjudication

The submitted checker originally accepted generic `gpu_mem_held_mb > 0` as sufficient even when `engine_core_pid_alive` was false. That could report Trap 123 when an unrelated process owned 512 MiB.

Maintainer correction:

- rename the observation to `engine_core_gpu_mem_held_mb`;
- require `engine_core_pid_alive == true` **and** EngineCore-owned memory > 0 for `PROBLEM`;
- `false + 0` is `CLEAN`;
- contradictory/partial states are `INCONCLUSIVE`;
- preserve the contributor's **104277 MiB** observation as the negative control.

The live diagnostic command was also normalized to NVIDIA's `used_gpu_memory` query field.

## Canonical disposition

**PROMOTE as Trap 123**, after maintainer-scoped wording and exact-head repository gates pass.

Why a new canonical owner is justified:

- operator-visible symptom is specific and expensive: parent looks dead, memory stays unavailable, next launch emits a misleading utilization error;
- concrete discriminator exists: surviving EngineCore PID plus EngineCore-owned GPU memory;
- concrete fix boundary exists: terminate/supervise the actual process tree rather than tuning around the residual allocation;
- existing Trap 119 does not own the named-process lifecycle mechanism;
- independent public reports show the failure class on other V1/Blackwell stacks.

Status remains **contributor-measured, conditions as reported** until Blackwellboy independently reproduces it.

## Claims rejected or narrowed during mining

- **Rejected:** "all vLLM V1 shutdowns leave EngineCore." Current upstream has explicit graceful shutdown machinery; Cruz measured abrupt parent-only SIGKILL on a pinned build.
- **Rejected:** Nemotron, NVFP4 or the LoRA merge caused the orphan. They describe the lane only.
- **Rejected:** any residual GPU memory proves Trap 123. Ownership must bind to EngineCore.
- **Rejected:** vllm-metal #479 is an NVIDIA memory replication. It corroborates process-title/pattern-kill behavior only.
- **Not promoted:** GH200 residual GPU memory with no visible process; different discriminator.

## High-value follow-up experiment

A small first-party lifecycle matrix would move the finding from contributor-measured toward reproduced-here without a large benchmark campaign:

| Arm | Signal / teardown | Expected discriminator |
|---|---|---|
| A | normal service SIGTERM / vLLM graceful shutdown | EngineCore exits; owned GPU memory returns |
| B | SIGKILL API-server PID only | determine whether EngineCore survives and owns memory |
| C | process-group teardown | all vLLM processes exit; memory returns |

Run on one current DGX Spark vLLM build with a bounded model and record PID tree + `nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory` before/after. A discrete-GPU repeat would test whether the lifecycle mechanism is hardware-independent without conflating UMA accounting.

## Credit disposition

Add **Victor Cruz / @vcruz305** to `HALL_OF_FAME.md` for:

1. Trap 123 — finder / contributor-measured EngineCore orphan lifecycle failure on DGX Spark.
2. Trap 116 — author of the F16 embedding patch chain and instrumentation used for runtime proof; Blackwellboy remains credited for external multi-node qualification.

His authored PR #53 commit is preserved in the maintainer integration branch ancestry rather than copied as a fresh Blackwellboy-authored trap.
