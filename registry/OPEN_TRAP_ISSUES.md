# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **19 of 137** entries.  118 uncovered entries remain outside automated doctor checks.

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

### Q73. Reload-to-reload score drift is removed by deterministic/autotune pinning on the reported stack

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/73
- **CONFIRM.** Reproduce reload-to-reload teacher-forced score movement under the reported stock launch, then repeat matched reloads with deterministic inference enabled and FlashInfer autotune disabled. Confirm per-item score movement collapses to zero (or the preregistered deterministic tolerance) without a material quality or short-prompt throughput regression.
- **REFUTE.** The stock reload drift cannot be reproduced under the pinned protocol, or the drift persists after deterministic/autotune pinning.
- **Boundary.** A successful determinism pin establishes this stack-specific measurement remedy only. It does not establish that `--enable-deterministic-inference` is safe for production or long prompts; issue #87 separately tests that serving-side cost.

### Q83. GLM-5.3-Flash vision suppression kwargs redirect reasoning into content instead of stopping it

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/83
- **CONFIRM.** On the same pinned GLM-5.3-Flash vLLM vision path, run matched image requests with the bare default, `enable_thinking:false`, `thinking:false`, and the model's in-text `/nothink` convention. Record both reasoning/content partition and total completion-token accounting. Confirm the suppression kwargs leave the overall reasoning work materially unchanged while relocating it into `content`, and confirm `/nothink` behaves distinctly as reported. Reproduce on the two reported checkpoint formats if available.
- **REFUTE.** Either suppression kwarg actually reduces/stops reasoning under matched accounting, the apparent leak disappears when reasoning is measured independently of the response parser, or the behavior cannot be reproduced on the pinned vision path.
- **Boundary.** Issue #83 explicitly proposes an extension to canonical trap 29. If the mechanism is the same off-switch/representation failure already owned by trap 29, adjudicate as scoped corroboration/addendum rather than allocating a duplicate trap ID.

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

### Q94. vLLM n-gram prompt lookup duplicates tokens inside structured output

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/94
- **CONFIRM.** On the reported pinned vLLM 0.28.0 aarch64 / Qwen3.8-27B lane, run the same deterministic structured-output fixture twice with all serve and request conditions matched except the draftless n-gram speculative config. Strictly parse every response body and retain raw bodies. Confirm the n-gram arm reproducibly introduces duplicated ordinary tokens/keys that make JSON malformed while the speculation-off control removes those same malformed cases. Require HTTP/process success in both arms so transport failure cannot explain the result, and repeat on the reported sibling checkpoint if available.
- **REFUTE.** The malformed JSON reproduces with n-gram speculation disabled, disappears while n-gram remains enabled under the pinned fixture, is attributable to a parser/template/request mismatch rather than emitted model tokens, or cannot be distinguished from the already-known drafter/special-token mechanism in trap 62.
- **Boundary.** Treat this as a possible new draftless prompt-lookup mechanism, not automatic proof that all n-gram settings, models, engine versions, or draft-model speculative decoding corrupt structured output. Canonical promotion requires preserving the single-variable A/B and distinguishing it from trap 62's drafter-model/special-token failure class.

### Q100. Docker missing bind-mount source is fabricated as a directory and can create late or persistent failures

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/100
- **CONFIRM.** On a disposable Linux Docker fixture, define a bind mount whose host source is intentionally absent and whose container target expects either a model directory or a file. Record host-source type before launch, container-create/start outcome, the host path Docker leaves behind, and the engine/container failure surface. For the file case, repeat the reported lifecycle: begin with a real file source, delete it, restart the container, verify the missing source is recreated as a directory and the container fails with a file-vs-directory mount error; then restore the intended file and determine whether the fabricated directory must be removed before recovery. Require the useful failure evidence to be distinguished between container logs and `.State.Error` if that part is claimed.
- **REFUTE.** The pinned Docker version refuses the absent source without creating it, creates a source of the expected type, the late model/checkpoint failure cannot be attributed to the fabricated mount source, or the deleted-file restart does not produce the reported directory/type mismatch under the declared mount syntax.
- **Boundary.** Keep this separate from canonical trap 127 unless adjudication proves the same mechanism. Trap 127 is whole-file package shadowing plus image drift/unattended update; Q100 is host-source absence/deletion changing mount-source type. Scope any promotion to the tested Docker bind-mount syntax/version rather than claiming every Docker version or mount API behaves identically.

## Privacy rule

Raw candidate research and unpublished evidence are not a public-repository surface. Public promotion starts from a deliberately scrubbed/adjudicated change, not by copying a private research directory into this repository.