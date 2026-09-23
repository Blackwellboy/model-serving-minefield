# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **19 of 143** entries.  124 uncovered entries remain outside automated doctor checks.

## OPEN

### Q87. Deterministic inference hard-caps FlashInfer prefill workspace and kills long prompts

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/87
- **SOURCE-PROVEN BROKEN PIN.** The related public report in issue #73 identifies SGLang build `0.0.0.dev1+g5f55db35e`. At upstream commit `5f55db35e`, `python/sglang/srt/layers/attention/flashinfer_backend.py` enters the deterministic branch, sets fixed split sizes, disables CUDA-graph KV split and executes `envs.SGLANG_FLASHINFER_WORKSPACE_SIZE.set(2048 * 1024 * 1024)`. Current upstream source no longer contains that specific 2 GiB deterministic setter.
- **CONFIRM.** Treat `5f55db35e` as the broken source pin. Preserve a T0 source check that proves the 2 GiB setter exists under deterministic mode on that pin and is absent on a current/known-good pin. For the runtime half, use the reported broken build with otherwise matched deterministic-on/off serves and sweep fresh prompt lengths across the computed workspace threshold while recording required workspace, HTTP/process outcome, KV capacity and crash trace; confirm the deterministic arm dies at the predicted boundary while the control survives materially longer prompts.
- **REFUTE.** The source mapping from the reported build to `5f55db35e` is wrong, the deterministic branch on that pin does not set 2 GiB, or matched runtime reproduction on the broken pin shows the long-prompt death is caused by an independent capacity/runtime fault rather than the fixed workspace/planner path.
- **Boundary.** This is a **versioned/historical mechanism**, not a claim about current SGLang. The exact `FIXED_BY` removal commit is not yet recorded; current source serves as a known-good/source-fixed control for the specific hard-set. Keep the runtime threshold scoped to the reported model geometry and broken pin. This remains separate from issue #73's narrow determinism result.

### Q89. Sustained two-box TP=2 rank divergence is fixed by the engine build, not the tested flags

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/89
- **CONFIRM.** On matched two-node GB10 TP=2 hardware/configuration, reproduce the old-build failure under sustained load and capture two time-separated stacks on both ranks at the first stall warning. Confirm one rank remains inside the collective the peer never enters, with clean fabric/RDMA error counters and no memory-pressure explanation. Repeat the same killer workload on the reported newer engine build and require multiple long survivors without the stall signature, while separately confirming the tested config toggles do not rescue the old build.
- **REFUTE.** The old build survives the preregistered sustained workload, both ranks enter the same collective rather than diverging, fabric/config drift explains the failure, one of the claimed flag changes reliably fixes the old build, or the newer build reproduces the same rank-divergence death.
- **Boundary.** Keep this distinct from startup-only NCCL hangs and from upstream reports where every rank spins inside the same collective. Cross-node launch/config identity must be proven before attributing a two-box result to the engine.

### Q105. DFlash draft budget 2 fails during decode CUDA-graph capture on the reported SGLang path

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/105
- **CONFIRM.** On the pinned SGLang DFlash2/NVFP4 lane, hold image, target, drafter, block size and all other serve flags fixed while sweeping `--speculative-num-draft-tokens` across at least 2, 4, 6 and 8. Treat startup as the measured outcome before any benchmark request. Confirm budget 2 deterministically fails during the draft worker's decode CUDA-graph capture with the reported non-contiguous FP4-quantization path, while the 4/6/8 controls reach health under the same launch conditions. Preserve the full traceback and resolve whether the tensor-contiguity difference is actually caused by depth 2 rather than merely correlated with it.
- **REFUTE.** Budget 2 reaches health under the pinned build, one or more matched 4/6/8 controls fail with the same signature, the failure occurs outside the draft decode graph/FP4 path, or source-level inspection/reproduction shows an independent configuration or checkpoint defect explains the contiguity failure.
- **Boundary.** Keep the observed startup cliff separate from generic high-depth quality/performance or OOM traps. Do not promote the issue's inferred tensor-shape mechanism as proven until source inspection or a bounded reproduction identifies why depth 2 changes contiguity. A failed-to-start arm is an explicit failure outcome, not a zero-score or missing benchmark cell.

### Q113. GB10 page cache can impose a large calibration slowdown while `MemAvailable` barely moves

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/113
- **CONFIRM.** On the reported GB10 unified-memory calibration path, use a byte-identical workload and run **counterbalanced repeated arms** with controlled cache seeding: hot-cache → cold-cache and cold-cache → hot-cache, with an untimed/discarded warm-up before each measured sequence and enough repeats to report a preregistered median or other repeated statistic. Preserve workload/manifest identity, `MemFree`, `MemAvailable`, `Cached`, elapsed time and driver-pressure messages for every arm. Confirm the hot-cache condition repeatedly shows materially higher elapsed time while `Cached` and `MemFree` move materially and `MemAvailable` remains nearly unchanged. Do not confirm from a single ordered hot/cold pair.
- **REFUTE.** The counterbalanced repeated hot/cold comparison does not reproduce a material slowdown, `MemAvailable` tracks the condition sufficiently to distinguish the arms, the effect reverses or disappears when order/warm-up is controlled, another launch/workload difference explains the elapsed-time delta, or the reported cache state is not actually present at launch.
- **Boundary.** Treat the reported 62% as one paired comparison on one box, not a universal page-cache tax or confirmation by itself. Do not claim reclaim contention or the driver's `NV_ERR_NO_MEMORY` line is the proven causal mechanism unless independently instrumented. Adjudicate as an extension or separate measurement trap only after semantic dedupe against trap 119's allocation-time page-cache mechanism and trap 54's run-order/warm-cache controls.

### Q132. Docker run on a missing image can turn a launch timeout into an implicit WAN-pull timeout

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/132
- **CONFIRM.** On a disposable host where a pinned serving image is absent, prove `docker image inspect <ref>` fails immediately before launch, then invoke the same bounded `docker run -d` path used by the orchestrator and capture whether Docker begins an implicit pull inside that call. Require the orchestrator timeout to expire before a container reaches running state, and preserve whether the pull later completes or leaves a container starting after the orchestrator has already declared failure. Run a matched control with the exact image pre-pulled and require launch to stay inside the same timeout. Also verify that an in-path preflight or an explicit no-pull policy fails fast with an image-missing diagnosis instead of entering the pull.
- **REFUTE.** The missing-image arm fails immediately without attempting a pull, the same timeout reproduces with the exact image already local under otherwise matched conditions, or the reported background/past-timeout container state cannot be tied to Docker's implicit image acquisition.
- **Boundary.** This is an orchestration/launch-contract trap, not a claim that every container runtime or every Docker invocation behaves identically. Preserve Docker version, pull policy, image reference/digest state, network path and timeout. A slow explicit `docker pull` is not itself the trap; the trap is treating `docker run` as a local-only start operation behind a timeout sized on that assumption.

### Q134. A userspace memory-watchdog rule change can invalidate a previously surviving GB10 serving margin

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/134
- **CONFIRM.** On a disposable DGX Spark/GB10 or equivalent unified-memory fixture, pin the model/runtime/launch and the userspace watchdog version. Establish a serve whose steady-state host `MemAvailable` is below the watchdog's absolute memory floor while swap remains above the old swap-free gate. Under the old conjunction require the serve to remain alive; then change only the watchdog decision rule to remove/bypass the swap gate and require the same serve to receive the watchdog's SIGTERM while Docker/kernel OOM indicators remain clean and the watchdog log identifies the decision. Finally lower serving memory utilization enough to clear the watchdog floor while still satisfying the engine's own KV/workspace minimum and require the matched lane to survive.
- **REFUTE.** The matched serve dies under the old rule as well, survives the new memory-only rule while below its configured floor, the process is actually killed by kernel/cgroup OOM or an engine allocation failure, or a model/runtime/configuration change rather than watchdog policy explains the transition.
- **Boundary.** Preserve the exact watchdog implementation/configuration, `MemAvailable`, swap state, engine memory accounting, configured context/KV/workspace requirements and kill provenance. Do not generalize an earlyoom result to every userspace OOM daemon. Keep this distinct from the existing GB10/cgroup unified-memory accounting trap: here an external watchdog is functioning according to its configured rule, and the failure is the hidden dependence of a serving recipe on the watchdog's previous decision semantics.

## Privacy rule

Raw candidate research and unpublished evidence are not a public-repository surface. Public promotion starts from a deliberately scrubbed/adjudicated change, not by copying a private research directory into this repository.