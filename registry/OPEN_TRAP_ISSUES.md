# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **19 of 138** entries.  119 uncovered entries remain outside automated doctor checks.

## OPEN

### Q71. SGLang answers a request naming a model it does not serve

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/71
- **CONFIRM.** On a serve whose resolved server state proves model A is loaded, send an OpenAI-compatible request naming a different model B that is not served. Confirm the server returns ordinary HTTP-200 assistant content rather than rejecting the model mismatch, while a control stack that validates model identity rejects the same mismatch.
- **REFUTE.** The mismatched model request is rejected, or resolved server state shows the supposedly mismatched name is actually served.
- **Boundary.** This queue records the public issue and its adjudication criteria only; raw reproduction artifacts are not stored here.

### Q72. Omitted reasoning effort resolves to the most expensive setting on the reported SGLang path

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/72
- **CONFIRM.** On the same pinned lane, compare rendered/request accounting for omitted effort and the model's maximum effort setting, with at least one lower explicit effort control. Confirm omission matches the maximum while the explicit lower setting is measurably distinct, and separately verify any server-side default override if claimed.
- **REFUTE.** Omission does not match the maximum setting under the pinned protocol, or the alleged client effort knob is genuinely inert across the controls.
- **Boundary.** Generation wall time is supporting evidence, not the sole mechanism test; the public issue's deterministic prompt-token/rendering control is preferred.

### Q87. Deterministic inference hard-caps FlashInfer prefill workspace and kills long prompts

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/87
- **CONFIRM.** On the reported pinned SGLang + FlashInfer lane, compare otherwise matched serves with and without `--enable-deterministic-inference`. Verify from resolved runtime state/source behavior that the flag forces the FlashInfer workspace to 2 GiB and defeats a larger same-name environment setting, then sweep fresh prompt lengths across the predicted workspace threshold while recording required workspace, HTTP/process outcome, KV capacity, and crash trace. Confirm the deterministic arm fails at the computed boundary while the control survives materially longer prompts.
- **REFUTE.** The flag does not force the claimed workspace limit, the environment setting remains effective, matched long prompts fail identically with the flag off, or the process death is attributable to an independent capacity/runtime fault rather than the deterministic planner/workspace path.
- **Boundary.** This is a production-serving side effect, not a refutation of issue #73's narrow determinism result. Short-prompt quality/speed parity cannot be used as evidence that the flag is safe for long-context serving.

### Q88. Architecture guard falls through to an unsafe fallback instead of rejecting an unsupported device

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/88
- **CONFIRM.** On the pinned unreleased engine/model/device combination, prove startup and metadata health checks pass on the unpatched build, then capture the first-inference failure and resolve the architecture guard/fallback path from source. Apply only the reported guard widening and show that text/vision inference now executes through a supported dispatcher path. Require a correctness control against a public checkpoint/reference result before treating the patch as safe rather than merely crash-avoiding.
- **REFUTE.** The first-request failure is not reached through the alleged guard/fallback path, the device is already explicitly supported/rejected by the pinned build, widening the guard does not remove the failure, or correctness controls reveal numerical corruption after the patch.
- **Boundary.** Successful model load and HTTP metadata readiness are not positive inference controls. A patch that stops the crash is insufficient by itself; the issue's central risk is that the unsafe fallback could otherwise produce fluent wrong output.

### Q89. Sustained two-box TP=2 rank divergence is fixed by the engine build, not the tested flags

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/89
- **CONFIRM.** On matched two-node GB10 TP=2 hardware/configuration, reproduce the old-build failure under sustained load and capture two time-separated stacks on both ranks at the first stall warning. Confirm one rank remains inside the collective the peer never enters, with clean fabric/RDMA error counters and no memory-pressure explanation. Repeat the same killer workload on the reported newer engine build and require multiple long survivors without the stall signature, while separately confirming the tested config toggles do not rescue the old build.
- **REFUTE.** The old build survives the preregistered sustained workload, both ranks enter the same collective rather than diverging, fabric/config drift explains the failure, one of the claimed flag changes reliably fixes the old build, or the newer build reproduces the same rank-divergence death.
- **Boundary.** Keep this distinct from startup-only NCCL hangs and from upstream reports where every rank spins inside the same collective. Cross-node launch/config identity must be proven before attributing a two-box result to the engine.

### Q100. Docker missing bind-mount source is fabricated as a directory and can create late or persistent failures

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/100
- **CONFIRM.** On a disposable Linux Docker fixture, define a bind mount whose host source is intentionally absent and whose container target expects either a model directory or a file. Record host-source type before launch, container-create/start outcome, the host path Docker leaves behind, and the engine/container failure surface. For the file case, repeat the reported lifecycle: begin with a real file source, delete it, restart the container, verify the missing source is recreated as a directory and the container fails with a file-vs-directory mount error; then restore the intended file and determine whether the fabricated directory must be removed before recovery. Require the useful failure evidence to be distinguished between container logs and `.State.Error` if that part is claimed.
- **REFUTE.** The pinned Docker version refuses the absent source without creating it, creates a source of the expected type, the late model/checkpoint failure cannot be attributed to the fabricated mount source, or the deleted-file restart does not produce the reported directory/type mismatch under the declared mount syntax.
- **Boundary.** Keep this separate from canonical trap 127 unless adjudication proves the same mechanism. Trap 127 is whole-file package shadowing plus image drift/unattended update; Q100 is host-source absence/deletion changing mount-source type. Scope any promotion to the tested Docker bind-mount syntax/version rather than claiming every Docker version or mount API behaves identically.

### Q105. DFlash draft budget 2 fails during decode CUDA-graph capture on the reported SGLang path

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/105
- **CONFIRM.** On the pinned SGLang DFlash2/NVFP4 lane, hold image, target, drafter, block size and all other serve flags fixed while sweeping `--speculative-num-draft-tokens` across at least 2, 4, 6 and 8. Treat startup as the measured outcome before any benchmark request. Confirm budget 2 deterministically fails during the draft worker's decode CUDA-graph capture with the reported non-contiguous FP4-quantization path, while the 4/6/8 controls reach health under the same launch conditions. Preserve the full traceback and resolve whether the tensor-contiguity difference is actually caused by depth 2 rather than merely correlated with it.
- **REFUTE.** Budget 2 reaches health under the pinned build, one or more matched 4/6/8 controls fail with the same signature, the failure occurs outside the draft decode graph/FP4 path, or source-level inspection/reproduction shows an independent configuration or checkpoint defect explains the contiguity failure.
- **Boundary.** Keep the observed startup cliff separate from generic high-depth quality/performance or OOM traps. Do not promote the issue's inferred tensor-shape mechanism as proven until source inspection or a bounded reproduction identifies why depth 2 changes contiguity. A failed-to-start arm is an explicit failure outcome, not a zero-score or missing benchmark cell.

### Q107. Qwen3 sliding-window config can silently resolve every layer to full attention

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/107
- **CONFIRM.** On a pinned Transformers version matching the report, instantiate a small Qwen3 config with `num_hidden_layers < max_window_layers` and a declared `sliding_window`. Verify separately that omitting `use_sliding_window=true` nulls the effective window and that enabling it while leaving the default `max_window_layers` still derives only `full_attention` layer types. Then construct the corrected config with an explicit compatible `max_window_layers` or explicit `layer_types` and prove the effective per-layer attention types/windows match the intended architecture after reconstruction. For the ModelOpt exporter sub-claim, inspect/reproduce the pinned 0.46.0 export logic and verify whether the written top-level config loses the trained window under the reported gating condition.
- **REFUTE.** The pinned Qwen3 config class preserves the declared window without the reported gates, small-model layer derivation produces the intended sliding layers under the reported inputs, or the exporter writes/reconstructs the effective window correctly on the pinned path.
- **Boundary.** The structural config-class half is CPU/source reproducible and may be adjudicated independently from the exporter half. Do not generalize to every Qwen3-family checkpoint or claim a served-quality regression without proving the affected published/runtime config actually resolves to the wrong per-layer attention behavior. Dedupe against existing config/requested-vs-effective traps before allocating a new canonical ID.

### Q113. GB10 page cache can impose a large calibration slowdown while `MemAvailable` barely moves

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/113
- **CONFIRM.** On the reported GB10 unified-memory calibration path, use a byte-identical workload and run **counterbalanced repeated arms** with controlled cache seeding: hot-cache → cold-cache and cold-cache → hot-cache, with an untimed/discarded warm-up before each measured sequence and enough repeats to report a preregistered median or other repeated statistic. Preserve workload/manifest identity, `MemFree`, `MemAvailable`, `Cached`, elapsed time and driver-pressure messages for every arm. Confirm the hot-cache condition repeatedly shows materially higher elapsed time while `Cached` and `MemFree` move materially and `MemAvailable` remains nearly unchanged. Do not confirm from a single ordered hot/cold pair.
- **REFUTE.** The counterbalanced repeated hot/cold comparison does not reproduce a material slowdown, `MemAvailable` tracks the condition sufficiently to distinguish the arms, the effect reverses or disappears when order/warm-up is controlled, another launch/workload difference explains the elapsed-time delta, or the reported cache state is not actually present at launch.
- **Boundary.** Treat the reported 62% as one paired comparison on one box, not a universal page-cache tax or confirmation by itself. Do not claim reclaim contention or the driver's `NV_ERR_NO_MEMORY` line is the proven causal mechanism unless independently instrumented. Adjudicate as an extension or separate measurement trap only after semantic dedupe against trap 119's allocation-time page-cache mechanism and trap 54's run-order/warm-cache controls.

## Privacy rule

Raw candidate research and unpublished evidence are not a public-repository surface. Public promotion starts from a deliberately scrubbed/adjudicated change, not by copying a private research directory into this repository.