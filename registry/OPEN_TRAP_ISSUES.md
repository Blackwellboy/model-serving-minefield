# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **70 of 168** entries.  98 uncovered entries remain outside automated doctor checks.

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

### Q219. FlashInfer autotuning at vLLM warm-up can take tens of GiB of host memory on a 128 GB unified-memory box

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/219
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** On a GB10 (128 GB unified memory) box with the exact pinned vLLM build, checkpoint revision and launch flags recorded, sample `MemAvailable` at one-second resolution through load and warm-up. Run repeated boots with FlashInfer autotuning on and, as the matched control, with `--no-enable-flashinfer-autotune` and nothing else changed. Use a guard set low enough that the run is not killed before the drop settles, or no guard on a disposable box. Confirm a material, repeatable host-memory drop that starts after model loading finishes, coincides with the autotuner's profiling log lines, is absent in the autotune-off control, and is not bounded by `--gpu-memory-utilization`. Report where free memory settles and whether it is released when tuning ends.
- **REFUTE.** The drop does not repeat across boots; it also occurs with autotuning off; it is attributable to another warm-up step (CUDA graph capture, speculative-decoding setup, KV allocation) or to a different checkpoint, build or flag; or `--gpu-memory-utilization` does bound it under matching conditions.
- **Boundary.** One failed boot stopped by an 8 GiB guard and one control. "About 32 GiB" is the drop up to the stop and may be a floor, not a settled figure. The allocation pool, whether memory is released after tuning, and the speed autotuning would have bought are all unmeasured. Dedupe against trap 13 and trap 119 (unified-memory headroom) and trap 54 (first-request warm-up) before adjudication.

### Q221. A hybrid Mamba model card's vLLM recipe reuses 0 cached prompt tokens, and the DFlash drafter turns reuse off again

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/221
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** With the pinned checkpoint revision, the card's named vLLM nightly and the stated kernel package, run the same repeated-prompt probe (two identical requests, then a fixed mixed-repeat prompt set) and read both per-request cached tokens and `vllm:prefix_cache_hits_total`, changing one variable per arm: card recipe as written; card recipe plus `--block-size 64 --prefix-match-unit 16 --enable-mamba-shared-prefix-checkpoint`; the same plus the card's DFlash drafter. Repeat each arm. Confirm zero reuse for the card recipe while the boot log reports prefix caching on, material reuse once the three flags are added without a drafter, and zero reuse again when the drafter is added with the same flags.
- **REFUTE.** The card recipe as written does reuse cached prefixes under matching conditions; the three flags do not change reuse; the drafter arm reuses prefixes with the same flags; or the zero reading is a metrics or probe artefact (for example prompts below the block or match-unit granularity, or a counter that is not populated on this path).
- **Boundary.** One model, one engine build, one box. The cause of zero reuse under the defaults was not traced, and whether drafter-disabled reuse is intended engine behaviour is unknown. The reported earlier sighting on a sibling hybrid checkpoint is not part of this issue's evidence. The drafter speed figure is context only, not a measured trade-off. Dedupe against trap 47 (prefix caching silently disabled for hybrid and recurrent architectures) before adjudication.

### Q222. SGLang v0.5.20 on a hybrid Mamba model returns different completions for identical temperature-0 requests

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/222
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** With the digest-pinned SGLang v0.5.20 arm64 image, the pinned checkpoint revision and the stated flags, send the same long-generation prompt sequentially at temperature 0, top_p 1 and a fixed seed, at least five times per arm, and hash every completion. Repeat across the issue's arms (card recipe; stochastic rounding off; stochastic rounding and speculation off) on fresh boots, and include short prompts plus a vLLM control with the same harness, prompts and sampling. Confirm multiple distinct completion hashes on the long generation in every SGLang arm while the vLLM control and the short prompts return one hash.
- **REFUTE.** Repeated SGLang requests under matching conditions return one completion; divergence follows a harness difference (concurrent warm-up traffic, seed or sampling fields not reaching the engine, differing max tokens or stop settings); or the vLLM control also diverges on the same prompts.
- **Boundary.** One model, one image, one box, five repeats per arm. Only speculation and stochastic rounding are ruled out; the FlashInfer Mamba backend, chunked prefill, batching with warm-up requests and kernel autotuning were not varied, and `--enable-deterministic-inference` was not tried. This is not a claim of an SGLang bug, only that temperature 0 is not repeatable output on this path. Dedupe against trap 87, trap 91 and trap 108 before adjudication.

### Q223. mlx_lm.server ignores the sampling fields of a shipped generation_config.json

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/223
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** Start stock `mlx_lm.server` (version pinned, and repeated on current main) on the pinned checkpoint whose `generation_config.json` carries `top_k` and `top_p`. Send the same prompt N times with no sampling fields, and again N times with a temperature but no `top_k`/`top_p`, at settings where top-k and top-p would bind. Compare the output distributions with an arm that sends the checkpoint's `top_k`/`top_p` explicitly. Confirm that the omitted-field arms match the server's built-in launch defaults (greedy when nothing is sent; plain temperature sampling when only temperature is sent) and differ measurably from the explicit-field arm.
- **REFUTE.** A live request to stock `mlx_lm.server` shows the shipped sampling fields being applied; the omitted-field and explicit-field distributions are indistinguishable at the tested settings; or the observed behaviour comes from a wrapper rather than the stock server.
- **Boundary.** Source read plus the shipped file only, not a live request against stock `mlx_lm.server`; the serving path that surfaced it was a custom wrapper. Stop tokens are reported as unaffected on this checkpoint. Scope any claim to the versions read. Treat as a candidate third shape of trap 21 (file present, sampling ignored) and dedupe against it before adjudication.

### Q224. Gemma 3 chat template treats the same system message three different ways depending on position

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/224
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** Render the four message lists from the issue through `apply_chat_template` with the pinned tokenizer, the template identified by its sha256 and `add_generation_prompt=True`, and preserve the rendered strings and token ids. Confirm that a leading system message is merged into the first user turn with no system marker, that an inline system message after a user turn gets a `<start_of_turn>system` header the leading path never uses, and that an inline system message after an assistant turn raises the role-alternation TemplateError. Run `minefield classify-inline-system` on the same template and record its verdict.
- **REFUTE.** The pinned template and tokenizer render any position differently from the issue; the classifier's verdict contradicts the issue's AMBIGUOUS reading under the entry's rule; or a different template revision is what produced the reported renders.
- **Boundary.** Template renders only, not a serving-endpoint test; how any server or model responds to these renders is unmeasured. The tool-result variant was not run. One checkpoint build and one transformers version. Treat as a data point for trap 113 on a model family that entry does not yet cover, not a new mechanism, and dedupe against it before adjudication.

### Q225. A single-file read-only bind into a read-only model bind needs the target file to already exist

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/225
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** With a recorded Docker version and runtime, launch a container with a directory bind mounted read-only and a single file bind mounted read-only onto a path inside it, in two arms: the target file already exists in the host directory, and it does not. Preserve the exact Docker error text and the container's view of the mounted file. Confirm the existing-target arm starts with the template visible, and the missing-target arm either fails to start or does not expose the template, and record which. Repeat on a second node or Docker version if available.
- **REFUTE.** The missing-target arm starts and exposes the file under matching conditions; the failure is caused by something else (a missing host path, mount ordering in a different tool, permissions, or SELinux labelling); or the behaviour depends on a Docker version the issue did not use.
- **Boundary.** Seen once, with no preserved Docker error text, so which of the two outcomes goes with which ordering is unknown. This is a container mount trap, not a model or engine trap; the checkpoints named are context for why the folder often lacks a template. Dedupe against existing chat-template and deployment-packaging entries before adjudication.

### Q227. TensorFold keys an omitted request seed to the prompt, so repeated sampled requests return identical replies

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/227
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** On the pinned TensorFold version, send the same prompts several times at a temperature above 0 with no `seed` field, and hash every reply and its token and reasoning counts. Confirm byte-identical replies across draws, that the sampled draws differ from a temperature-0 run of the same prompts (so sampling is live), and that sending a different explicit `seed` per draw makes the draws differ. Cite the engine source location that derives the default seed from the prompt.
- **REFUTE.** Draws without a seed differ under matching conditions; the identity comes from a client or proxy that injects a fixed seed or caches responses; the sampled draws equal the temperature-0 output (sampling not applied); or explicit per-draw seeds also return identical replies.
- **Boundary.** One engine version, one checkpoint family, one box. Prompt and reply text is not shared; per-item hashes are. The engine behaviour is documented in source as deliberate, so the trap is the silent collapse of best-of-n, voting and median methods ported from engines where an omitted seed means a fresh seed, not an engine defect. Dedupe against trap 91 and trap 108, and contrast with Q222's opposite symptom, before adjudication.

### Q232. One request field, three behaviours: `thinking_token_budget` enforced by one vLLM reasoning parser, rejected with HTTP 400 by another, ignored by a different engine

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/232
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** For each named server (the vLLM nightly with the `nemotron_v3` parser, the official vLLM 0.28.0 aarch64 image with the `muse_glimmer` parser, and the TensorFold version with its server-side thinking budget), pin the build, checkpoint revision and launch flags, then send the same hard prompt at temperature 0 with `thinking_token_budget` set small and again without it. Classify each server from its own response: enforced (`completion_tokens_details.reasoning_tokens` stops near the budget and the answer follows), rejected (a 4xx naming the field), or ignored (no difference between the arms). Cite the vLLM source path that raises when `reasoning_config` is not enabled and the parser property that leaves the reasoning start and end strings unset.
- **REFUTE.** Under matching conditions the field behaves the same on all three servers; the 400 comes from a missing launch option the issue did not record (an explicit `--reasoning-config`) rather than from the parser; the "enforced" reading rests on total completion tokens instead of the server's reasoning-token count; or the "ignored" engine does honour a per-request budget when the server flag is absent.
- **Boundary.** One box, three servers, one model each. The per-parser mechanism is read from source in the images, not instrumented. The harness-level consequence (a rejected field scoring every item as failed) depends on the harness. Dedupe against trap 164 (what an enforced budget cut does to the answer), trap 77 (fields silently accepted on another server) and issue #166 (an SGLang budget processor with the wrong marker ids) before adjudication.

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
