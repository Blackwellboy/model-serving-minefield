# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **70 of 164** entries.  94 uncovered entries remain outside automated doctor checks.

## OPEN

### Q197. Qwen3.8 TP=2 GB10 startup can hang at the first PYNCCL collective

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/197
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** Reproduce a bounded startup hang on the same two-node GB10 topology with the exact pinned model, weights, image/build, launch flags, CUDA/NCCL versions and interface routing recorded. Capture timestamped logs and Python/native stacks for **both ranks** at the collective boundary, including NCCL channel/interface/peer selection; run a minimal value-checked cross-node collective and a same-image known-good model control. Then isolate whether the model-specific GDN/state initialization actually reaches or blocks that collective. The observed startup hang may be confirmed independently of the hypothesised GDN mechanism.
- **REFUTE.** The four-message or earlier startup pattern reaches a serving-ready bounded generation under matching conditions; the hang is attributable to a different rank/process, a transport-path or interface mismatch, missing loaded artifacts, or an image/build-specific failure; or controlled GDN-path changes do not change the stalled boundary. Do not equate one successful alternative model with proof that every fabric path is healthy.
- **Boundary.** Reported five repeated hangs across several builds, but no preserved raw logs or rank stacks. GDN causality is **unproven**. Do not promote a model-specific suspected mechanism from the final printed PYNCCL line alone. Dedupe against Trap 160's post-startup rank divergence and existing transport/startup failure classes before adjudication.

### Q198. NGC GB10 PyTorch image plus Unsloth --no-deps lacks transformers

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/198
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** In a fresh digest-pinned `nvcr.io/nvidia/pytorch:25.11-py3` container on GB10/aarch64, inventory installed packages first, apply the exact documented `pip install --no-deps unsloth unsloth_zoo bitsandbytes` procedure, preserve install output and capture the failing `import unsloth` with the missing `transformers` dependency. In a clean matched container, install the stated HF dependencies before the identical --no-deps command and require import, a bounded model-load/generation smoke test, and a package-version inventory.
- **REFUTE.** The pristine pinned image already includes an importable compatible transformers stack, the documented sequence installs it, the baseline Unsloth import succeeds, or the matched HF-first setup fails on the same package/build pins. Distinguish missing dependency from incompatible version or another transitive import failure.
- **Boundary.** This is a **fine-tune toolchain setup** issue, not a serving failure. User-reported successful workaround is not a universal version-compatibility guarantee. Keep original and resolved package versions, platform and container digest attached to any promotion; dedupe against versioning/dependency traps before creating a canonical entry.




### Q113. GB10 page cache can impose a large calibration slowdown while `MemAvailable` barely moves

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/113
- **CONFIRM.** On the reported GB10 unified-memory calibration path, use a byte-identical workload and run **counterbalanced repeated arms** with controlled cache seeding: hot-cache → cold-cache and cold-cache → hot-cache, with an untimed/discarded warm-up before each measured sequence and enough repeats to report a preregistered median or other repeated statistic. Preserve workload/manifest identity, `MemFree`, `MemAvailable`, `Cached`, elapsed time and driver-pressure messages for every arm. Confirm the hot-cache condition repeatedly shows materially higher elapsed time while `Cached` and `MemFree` move materially and `MemAvailable` remains nearly unchanged. Do not confirm from a single ordered hot/cold pair.
- **REFUTE.** The counterbalanced repeated hot/cold comparison does not reproduce a material slowdown, `MemAvailable` tracks the condition sufficiently to distinguish the arms, the effect reverses or disappears when order/warm-up is controlled, another launch/workload difference explains the elapsed-time delta, or the reported cache state is not actually present at launch.
- **Boundary.** Treat the reported 62% as one paired comparison on one box, not a universal page-cache tax or confirmation by itself. Do not claim reclaim contention or the driver's `NV_ERR_NO_MEMORY` line is the proven causal mechanism unless independently instrumented. Adjudicate as an extension or separate measurement trap only after semantic dedupe against trap 119's allocation-time page-cache mechanism and trap 54's run-order/warm-cache controls.

### Q172. vLLM Whisper can fail English-only defaults and separately collapse smaller checkpoints when a prompt is injected

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/172
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** Treat the issue's two mechanisms as separate matrices on pinned vLLM 0.26. Use the same shareable audio, deterministic settings and repeated requests across English-only and multilingual Whisper checkpoints. For the `.en` matrix, compare an omitted language field with explicit `language=en`, preserve HTTP status and traceback, and require the plain request to fail while the explicit-language control succeeds on the same checkpoint. For the prompt matrix, compare no prompt versus the exact vocabulary prompt across several checkpoint sizes, score transcript error and repetition/empty-output signatures, and include large-v3 as a control. If available, test the corrected previous-context token path and require it to remove the collapse without changing the audio.
- **REFUTE.** English-only checkpoints succeed without language; explicit language does not recover them; prompted and unprompted smaller checkpoints perform equivalently across repeated clips; the prompt body is malformed or exceeds a model limit; or the corrected token path does not change the result.
- **Boundary.** A single synthetic clip cannot support a general accuracy ranking, and the `.en` HTTP failure and prompt-induced transcript collapse may warrant separate canonical entries. Do not state that every checkpoint below large-v3 fails or that `language=en` is a measured fix until that control is run. Scope source claims to the pinned serving path and dedupe against any existing transcription-template or previous-context entries before promotion.

## Privacy rule

Raw candidate research and unpublished evidence are not a public-repository surface. Public promotion starts from a deliberately scrubbed/adjudicated change, not by copying a private research directory into this repository.
