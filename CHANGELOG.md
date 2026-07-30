# Changelog

New entries and structural changes, newest first. Cadence: entries land as
they are verified; issue reports get a first maintainer response within a
few days.

## 2026-07-30

- **Trap [98](traps/runtime/98-speculative-decode-default-max-seqs-oom-uma.md) lands from [@smfworks](https://github.com/smfworks) at `contributor-measured, conditions as reported`.** On his vLLM 0.25.1, Laguna S 2.1 NVFP4, DFlash K=15, 128 GB UMA configuration, `max-num-seqs=256` OOMed before ready, 32 OOMed under concurrent agent traffic, and 4 was stable over the reported four-day operational interval. A separate @Blackwellboy 12-hour soak was stable at K=7 / sequences=32; it is retained as a differently configured counter-observation, without borrowing its session or turn counts. The two runs show that a sequence value validated at one speculative depth must not be assumed safe at another. They do **not** isolate direct K x sequences scaling or a universal threshold. The check now records startup, first-request, bounded-concurrency and declared-window outcomes separately for the exact configuration instead of treating one successful request or a product calculation as a pass. Registry count 107 to 108; doctor coverage remains 19, leaving 89 entries unimplemented.

## 2026-07-29

- **Traps [105](traps/evaluation/105-acceptance-estimator-unnamed.md) through [108](traps/evaluation/108-burn-canary-is-bistable-not-degrading.md): four entries from two long soaks, and three of the four are instrumentation traps rather than serving defects.** Sources are a 2,400-request / 10.20 h soak of a community abliterated DeepSeek-V4-Flash (vLLM `0.21.1rc1.dev339+g1967a5627bc3`, TP=2 on two GB10 nodes, MTP K=3) and a 2,045-turn / 13.009 h soak of NVIDIA Nemotron 3 Super 120B A12B NVFP4 (vLLM 0.20.0, single node). Both are **single serves with no baseline arm**, both land at **measured here, raw not published**, and every entry says so. [105](traps/evaluation/105-acceptance-estimator-unnamed.md) is the one to read: on the same 2,400 requests, token-weighted acceptance is **72.70%** and request-weighted is **66.39%**, a **6.31 point** gap where neither number is wrong, and `/metrics` will hand you a third, process-wide **73.4%** that is not scoped to your requests at all. Pairing that unscoped numerator against a request-scoped denominator inflated our own published gap from 6.31 to 7.0 until it was caught, and the entry keeps that admission because the entry's thesis is exactly the error it made. Per task family the same run spans **43.37% to 78.14%**, a 34.78-point spread against a pooled 66.39% that describes no family on the lane. [106](traps/memory/106-kv-occupancy-ceiling-is-not-a-leak.md) and [107](traps/memory/107-soak-duration-changes-the-verdict.md) are the same error in opposite directions: KV occupancy climbing +3.6 points per 60 requests to a 96.4% ceiling is a prefix cache doing its job (and our own per-request `cache_salt` forcing misses), while container memory rising monotonically for 5.4 h is a **bounded transient that fully reverts** by 13 h, ending below its own h=1.09 value. A short soak would have published both as leaks. [108](traps/evaluation/108-burn-canary-is-bistable-not-degrading.md) is why a consecutive-pair burn detector is the wrong detector: 25 fixed-seed temperature-0 samples produced **exactly 2 distinct outputs**, 21 and 4, alternating, so a detector comparing each sample to the previous one fires on every switch and reports degradation that is not happening. Also in this batch: a dated addendum to [12](traps/evaluation/12-empty-content-at-token-ceiling.md) giving the organic-load rate (**92 of 2,045 turns, 4.50%**, all thinking-on and all `finish_reason: length`, against **0 of 1,022** thinking-off) and the per-family concentration behind it (reasoning **30.82%** of thinking-on turns, three of seven families never once), plus three [mining](mining/README.md) notes. Registry count 103 to 107. Trap **98 remains held** and the numbering helper still reports it as the next free number.

- **The first published SGLang evidence surfaces, from [@newageinvestments25-byte](https://github.com/newageinvestments25-byte) on a DGX Spark.** A pinned Nemotron NVFP4 control generated first; Laguna S 2.1 then loaded its `CompressedTensorsW4A4Nvfp4MoE` path and generated a correct first token, which refutes Q7 under the criterion written before the run without claiming that Laguna's degraded longer output is healthy. Two 14-request doctor runs confirm Q8 portability and add SGLang conditions to traps [02](traps/template/02-orphaned-think-close-tag.md), [12](traps/evaluation/12-empty-content-at-token-ceiling.md) and [77](traps/reasoning/77-only-one-request-field-is-validated.md), all labelled **contributor-measured, conditions as reported**. The same run found a bounded doctor defect: SGLang identifies itself through `owned_by: "sglang"` in `/v1/models`, while the doctor looked only for `/props` and `/version`; the detector and fixture now carry that response shape. [Pinned conditions and disposition](mining/2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md).

- **Traps [99](traps/runtime/99-sdpa-causal-attention-fails-gfx1151.md) through [104](traps/versioning/104-stale-launch-script-silently-reverts-config.md): the registry's first gfx1151 coverage, and its second external batch**, from [@smfworks](https://github.com/smfworks), measured on a mixed DGX Spark, gfx1151 and SM120 fleet. All six land at **contributor-measured, conditions as reported**, which is the label he applied himself, unprompted and correctly, to all seven he filed. That is the first time the [status vocabulary](CONTRIBUTING.md#status-vocabulary) has been used correctly by a contributor without a maintainer correcting it afterwards, and the vocabulary was rewritten in the previous batch precisely because it had misled the previous contributor. The one to read is [100](traps/runtime/100-oem-kernel-kfd-rejects-gfx1151-code-objects.md): GPU memory allocates, the device enumerates, and every kernel then fails with `hipErrorInvalidImage`, because the OEM kernel's KFD rejects every code object built for the card. Nothing in that sequence points at the kernel. [99](traps/runtime/99-sdpa-causal-attention-fails-gfx1151.md) is the same shape one layer up: causal SDPA fails on gfx1151 and the error surfaces asynchronously on a later `torch.cat`, so the traceback names an operation that is not the fault. [102](traps/quantization/102-nvfp4-bottleneck-is-bf16-gemm-not-moe.md) is a redirect rather than a bug: on an NVFP4 MoE serve the BF16 GEMMs are 44% of the time and the MoE path is 22%, so the flag everyone reaches for is tuning the smaller half. Its measurement is [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s and the entry says so; @smfworks is the reporter, not the measurer, and neither of them had to be asked to make that distinction. [104](traps/versioning/104-stale-launch-script-silently-reverts-config.md) pairs with [53](traps/runtime/53-config-edit-never-took-effect.md) and inverts it: there the edit never reached the process, here the running process is correct and the script that would restart it is not, so the configuration is right until the day something restarts it.

- **The seventh entry of that batch is held, and the number is held with it.** His 98 attributes a 12-hour crash-free run to `max-num-seqs=4`. The soak it cites is ours, and ours ran `K=7 / max-num-seqs=32` ([primary](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/soak/LAGUNA_SOAK_12H_20260725_RESULTS.md)), so either the trap is a real measurement on his own fleet whose counts have been attached to the wrong run, or it is a citation error. Those need different fixes and only he can say which, so it is a correction request rather than a rejection and the reconciliation is not ours to do. Trap 98 stays unassigned in the meantime: the [numbering helper](integrity/registry_integrity.py) derives the next free number from the tree and now reports 98, so the entry keeps its number if it comes back.

- **A style rule stopped gating contributor prose, and a leak rule did not.** The push that carried this batch was refused on 27 em dashes by a rule that appeared in no contributor-facing document, alongside one genuine finding: a `HOST:PORT` example carrying a real internal port. Those two were the same check and are now two. Style is the dash class, it is skipped on registry entries whose Status line says contributor-measured, and every skip is printed. Leak is hostnames, ports, home paths, LAN, tailnet and corpus identifiers, and it is whole-tree with no exemption of any kind. See [House style](CONTRIBUTING.md#house-style), which is also now the first place either rule has been written down where a contributor would find it.

## 2026-07-28

- **A fourth tier, [upstream-reported](upstream/), and the fifty-candidate queue behind it is now worked out rather than sitting still.** Roughly fifty mined upstream candidates had been unpublished for months, most blocked as not-testable for want of a stack we do not run, several of them maintainer-confirmed with reproductions in the thread. That is real information helping nobody, and publishing it also creates the one thing a private queue cannot: somewhere for a reader who **does** have the stack to settle it. Eleven are published; twenty-two are closed as too weak so they stop being re-queued; nine are named as already covered by a measured entry. The tier lives in its own **directory**, not behind a word in a status line, so a stranger can tell measured from reported at a glance. Every entry must carry a primary source **with the date somebody opened it**, the reporter, whether a maintainer engaged and the issue state, both from closed vocabularies, an explicit sentence that nobody here has reproduced it, and an invitation with CONFIRM and REFUTE criteria. `integrity/upstream_integrity.py` asserts all seven per entry plus five separations: never in [Core](CORE.md), never in the doctor's `TRAP_PATHS`, never a README symptom row, never a file under `traps/`, and **no new "reported by others" entry in `traps/`** against a recorded snapshot of the twenty-three that predate the tier, without that last one the easy path for the next such report is the old label and the directory separation never gets used. Twenty-four mutation cases, twenty-two firing and two honest controls. One of the controls is the bug this checker shipped with: `read on` and its date land on separate lines in hard-wrapped entries, and the single-space version of the pattern failed 4 of the first 11, every one correctly dated. That is the same line-wrap defect written up in `contradiction_gate.py`, reappearing in the next checker written after it.

- **Reading the primary sources corrected six misdescribed candidates across four classes (out of roughly thirty-five with a source we could read), and two of them we had been about to test for a bug that is not there.** The [classification note](mining/2026-07-28-r2-queue-classified-upstream-tier.md) records every disposition. R2-23, the VL reranker, was ranked seventh of fifty as a well-attested vLLM scoring defect and our own blocked-candidates note carried a test plan to confirm it; the thread closes with **the reporter** saying the scores were fine once the chat template was supplied, and then that a **hand-copied** template still misbehaved where a **downloaded** one did not. That correction is on the blocked note now, and the trap that is actually there, a scoring path has no correctness signal, so it returns confident, well-formed, near-reversed numbers, is published as [U10](upstream/U10-vllm-vl-reranker-without-chat-template.md). Two candidates cited a maintainer's **tracking index** for claims it does not make; one source had been **retracted by its own author**; one had its headline answered by a maintainer with "which is demonstrably incorrect", while the sibling claim in the same issue stayed open and unanswered, and that sibling is what [U02](upstream/U02-ollama-go-runner-drops-sampling-penalties.md) publishes, with the dispute stated. A desk mining list is a lead. The tier's evidence bar now says so and the checker enforces it.

- **The strongest thing in the new directory is two bugs a maintainer reproduced and a bot closed.** [U08](upstream/U08-sglang-harmony-commentary-channel-valueerror.md) carries `maintainer reproduced`, @byjiang1996 wrote "Successfully reproduced the issue" and posted the evidence, with `bug` and `high priority` still attached when an inactivity bot closed it two months later. Anyone searching that tracker today sees a closed issue and reasonably infers it was resolved; nothing in the thread supports that. **`closed, not fixed` is a value in the issue-state vocabulary for exactly this**, and a mutation test asserts that writing a stale close as "closed (stale bot)" fails rather than silently reading as a fix. [U11](upstream/U11-glm-tool-content-array-renders-empty.md) is the opposite kind of provenance and the best-sourced entry here: a report **from the model vendor**, pinned on their own repository, with the fixed template shipped, and it is an independent instance of the mechanism we measured ourselves in trap [67](traps/template/67-history-rendered-as-object-repr.md), reaching the tool role on two other stacks.

- **Five stack pages that exist to say we have measured nothing.** [TensorRT-LLM](stacks/tensorrt-llm.md), [text-generation-inference](stacks/text-generation-inference.md), [TabbyAPI and ExLlama](stacks/tabbyapi.md), [LM Studio](stacks/lm-studio.md) and [text-generation-webui](stacks/text-generation-webui.md). Each names which of our mechanism classes most likely apply **and why**, with the measured entry each class comes from, the check a reader would run, and how to report. TGI is the largest unexplained hole in this registry: not one entry names it in either direction. Writing them caught two counting errors that would have overstated coverage: LM Studio's single entry is **inherited**: trap [24](traps/template/24-official-template-breaks-cpp-jinja.md) names it as an environment the C++ Jinja defect applies to, and that entry was measured on llama.cpp, and the five entries naming **EXL3** name a quantization format, not TabbyAPI or ExLlamaV2 as a server, so the TabbyAPI row is 0 and not 5. Reading those five as stack coverage would have been the exact error trap [10](traps/quantization/10-quant-label-is-not-the-kernel-path.md) is about. The stacks index now carries a separate upstream-reported column, and the two never add together.

- **The front door now warns people before they paste, and blank issues are off.** The trap form asks a stranger what they saw and the honest answer is usually a log, and it carried no redaction guidance at all. It now leads with a prominent scrub warning, a required scrub checkbox, and a worked sanitised-versus-unsanitised log excerpt, because "remove sensitive data" is advice nobody can act on and two placeholder-substituted lines are. A [SECURITY.md](SECURITY.md) covers the case that had no path at all: reporting a credential leak privately, **including one already published in an issue by mistake**, with rotate-first as step one because it is the only step that protects the reporter and it needs nothing from us. Blank issues are disabled, since a blank issue routes around every one of those warnings and a warning the reporter can skip in one click is decoration; a second short form exists so that questions, corrections and "I need to report something privately" still have a door, and it carries the same warning. **The example itself was rewritten once:** the first draft used a realistic token prefix and a private-range address, and the whole-tree sanitizer refused the push over the redaction guidance. It is now built from documentation-reserved values. Adjudicating a waiver would have been the wrong fix, and the file records why.

- **The PR template taught three of the five status labels, and now cannot.** It listed reproduced here, reported by others and under test, missing **contributor-measured, conditions as reported** and **measured here, raw not published**: precisely the two an external contribution needs. That is the same defect that made this registry's first external contribution arrive mislabelled, which we corrected publicly and recorded as **our documentation bug**. CONTRIBUTING was fixed at the time. The template that taught the wrong set was not, because nothing asserted the two agree. The template now carries all five with an evidence-pointer requirement, and `reference_integrity.py` asserts the agreement four ways: the canonical table in CONTRIBUTING is parsed and compared against `contradiction_gate.LABELS`, against this checker's own stem list, against every surface carrying a `status-vocabulary` marker, and against any line anywhere in the tree that slash-joins two or more labels without carrying all five. Eight mutation cases, six firing and two honest controls; the honest controls are not padding, since the first version of the check reported a correctly wrapped label as missing and a guard that fires on good surfaces gets waved through. Two live defects fell out of writing it: two broken links in the new template, and a file-wide containment test that could not see a label deleted from an enumeration when the same label appeared elsewhere in the file.

- **CI now runs what the pre-push hook runs.** `checks/tests/test_check_contract.py`, the guard against a check that cannot fail, was in the local `run_checks` and **not** in the Actions workflow, which named `test_preflight_kwargs.py` alone. So a vacuous-check regression depended on somebody having the hook installed, and that hook had already failed to fire once this week because a file was not executable. Naming files is what let one go missing, so the step now loops over every `test_*.py` under `checks/tests` and **fails on zero collected**, since a pass over an empty set is the exact defect that file exists to catch. The contradiction gate and the status-vocabulary checks are not separate steps, because they are not separate programs, but both are now named in their step titles and in the verdict block rather than being discoverable only by reading an import list. The divergence ran the other way too: CI scanned the Pages site for claim propagation and `run_checks` could not, so a pre-push run passed while the most public of the three surfaces went unscanned. `run_checks` takes `--bbio` now and says plainly when it is not given.

- **Trap [77](traps/reasoning/77-only-one-request-field-is-validated.md) gets a check in the doctor, taking Core coverage to 9 of 12 and total coverage to 19 of 97.** The entry names the probe as its own fix, so implementing it was reading the entry: send one deliberately misspelled parameter and see whether you get a 400. It runs **first**, because it decides whether a 200 from this lane carries any information about whether a parameter was read, and every check after it sends parameters. The CLEAN is paired and the pairing is the whole verdict: the invented field must be rejected **while the identical request without it returns 200**, or a wrong model name, an expired key or a server still loading reads as a strict server. That is the false-CLEAN shape this tool has emitted four times, and it now has a fixture that produces it and a test that refuses to credit it. Scoped narrowly and stated in `CLEAN_CONTRACT`: it rules out "your typo is silently accepted", never that a particular toggle took effect, which stays behavioural with traps 03 and 29. Of the remaining Core three, 35, 53 and 61, none is reachable by a request-shaped probe and [CORE.md](CORE.md) says so.

- **Two stack pages that mostly say what they do not have.** [HF transformers](stacks/hf-transformers.md) has seven entries and **not one of them was measured here on that stack**; six are @Hikari_07_jp's and one is TheTom's, and the two entries whose status lines say "reproduced here" were reproduced on a different build class, which the page states rather than letting the label imply otherwise. [SGLang](stacks/sglang.md) has **zero** entries and the page exists anyway, because "no page" and "no entries" read identically from outside and mean different things. Writing them surfaced a drift of exactly the kind the vocabulary check now catches: the stacks index still said no server had been started on SGLang for this registry, which stopped being true when it was brought up first-party, and [CONTRIBUTING](CONTRIBUTING.md#where-coverage-is-thin) was corrected at the time while the index was not. The count stays at zero until those results are published, because the count is of published entries.

- **Traps [91](traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) to [97](traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md): the determinism axis, plus the registry's first cross-architecture and co-tenancy coverage.** Same lane as 82 to 88: llama.cpp `b9878-2da668617` with `--jinja` against a Mistral-family Q8_0 GGUF of **unstated provenance** supplied by **Exile**, this time on two consumer GPUs of different architectures in one host. Same scoping rule as that batch: no capability claims, no benchmarks, no refusal or alignment probing, and every finding scoped either to that artifact or, where the mechanism is server-side, to the build. The one to read is [91](traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md), because its failure mode is a **false negative**: temperature-0 divergence under continuous batching needs concurrency of at least 2 **and** a prompt above roughly 220 tokens, and the smallest reproduction anyone would write is shorter than that. Pooled with `cache_prompt: false`, 108 to 136 token prompts diverged in 0 of 256 concurrent responses, 220-token prompts in 74 of 256, and 444 to 1900 token prompts in 88 of 512, against a concurrency-1 control of 0 of 512. The divergences are semantic and all correct, so a sampled eyeball passes and only a hash comparison catches it. Two separately queued candidates gave opposite first answers purely because one used a long prompt: the shared system prompt in the second was not special for being shared, it was special for being long.

- **Trap [93](traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md) corrects received advice, and the correction is that the usual remedy is the harmful move.** Measured against a freshly restarted server per arm: a per-turn clock at the head of the **system** prompt moved prefix reuse from 136 cached tokens to 135, because the template relocates the system block onto the last user turn ([trap 82](traps/template/82-system-prompt-relocates-to-last-user-turn.md)), so nothing placed there is in a prefix position. The same clock at the head of the **first user turn** took reuse from 474 tokens to 4 and prefill from 82 ms to 216 ms. So "keep the clock out of your system prompt" is a no-op on this template and "put volatile context in the first user message instead" is the single change that takes reuse from 77% to 0.6%. The surviving rule is positional rather than role-based. A second effect falls out of the same table: identical static text costs about 340 tokens of reuse per turn purely for arriving in the system role, 25% against 77%. **This advice has never appeared in this registry**; the entry corrects wisdom in circulation elsewhere, and no published entry here needed changing.

- **Trap [92](traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) is a self-caught error, recorded because the mistake was ours.** A prefix-reuse A/B re-run in the reverse arm order against the same long-lived server process inverted its own conclusion: the same arm read 4 cached tokens in isolation and 655 with history, having inherited hits from prompts issued roughly a thousand requests earlier. Both runs were internally consistent and one was measuring the other's history. The isolation that works is a **server restart per arm**, asserted by `cached_tokens == 0` on the first request after it; `cache_prompt: false` is not a substitute, because it measures no reuse rather than clean reuse. Separately, the same entry establishes the cache as an independent divergence source visible at **concurrency 1**, tied to partial cache hits, which must be switched off before the batching effect in 91 can be characterised at all.

- **Trap [94](traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md) is a regime, not a ranking, and the middle row is what keeps it honest.** One binary compiled for both architectures, one file, identical flags, two GPUs in one host. At 108 to 136 tokens both are deterministic. At 220 tokens **both** diverge, `sm_86` marginally worse (41 against 33 off-majority responses). At 444 to 1900 tokens `sm_120` diverged in 29 of 32 cells and `sm_86` in **zero** of 32. Confounds excluded and stated: memory pressure (repeated with 12610 MiB free, identical), context size, build skew (one `system_fingerprint` from `/props` on both lanes), prompt cache, and a busy neighbour. No kernel-level mechanism is claimed and no vendor or generation is ranked; what is established is that the axis exists and belongs in any reproducibility claim.

- **Trap [95](traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md) is a negative that removes a standing caveat, and it names the case it does not cover.** Decode medians moved -0.4% and +0.3% under a busy neighbour, inside the sample spread, and divergence rates were identical in all 12 correctness cells. The prefill move on the larger card, -8.0%, is **n=6 with no repeat** and lands explicitly as a **lead, not a result**. Both lanes had headroom, so this does not test two models competing for one GPU's memory pool, which is the case people usually mean by eviction.

- **Traps [96](traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md) and [97](traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md): two things this server will not tell you about itself.** 96 prints 43781 MiB free for a card with 292 MiB actually free and a printed total of 24575 MiB on the same line, because the free-memory query returns host `MemAvailable` under WSL2; the portable check is the self-contradiction, `free_mib <= total_mib`. 97 measures partial offload at 83.3, 3.8 and 2.7 tok/s for `-ngl` 999, 16 and 8, and finds **zero** log lines naming the split at default verbosity or from a foreground run with stderr captured, and no `/props` field for it either; VRAM is no proxy, since the `-ngl 8` lane still held 14078 MiB on a 7.3 GiB file. The refinement is that operators are not merely failing to notice partial offload: on this build there is nothing to notice.

- **Five deferred llama.cpp mining candidates adjudicated** in one place, [here](mining/2026-07-28-r2-llamacpp-queue-dispositions.md), including the two that turned out to be one effect with a length floor, and the reporting half of the unified-memory candidate moving from blocked-for-hardware to reproduced in an adjacent configuration. The cache-sizing half stays open, the VL reranker and SGLang candidates stay blocked, and the llama.cpp-tagged candidates outside this session's scope are recorded as neither confirmed nor refuted rather than swept up.

- **Routing, not new entries: four playbooks, four stack pages, and a Core tier.** At 40 entries a catalog was the right shape. At 90 the symptom table is the bottleneck rather than the science, because operators arrive with a job rather than a clean symptom. Nothing was added to the registry and nothing was renumbered; the existing entries were made findable. New: [playbooks/](playbooks/), four ordered checklists (publishing an A/B, thinking dying multi-turn, porting a harness to a new server, long context looking broken) where every step names the entry it guards against and the check to run. New: [stacks/](stacks/), one page per serving stack with the five entries that bite hardest there and the three checks to run first. New: [CORE.md](CORE.md), twelve load-bearing entries selected on evidence of what has cost people evenings rather than on which entries have the best data, with the rest explicitly Extended rather than lesser. The front page now routes on the job, and the symptom table keeps its premise and its place. [mining/](mining/) is linked from the front page for the first time, as the three things it actually holds: did not reproduce, blocked or not testable, and specification only.

- **The doctor is named honestly: a thinking-stack preflight, not a minefield doctor.** Its 18 checks cluster on reasoning fields, templates, thinking control, tool parsing and ceilings, and it has nothing to say about kernel paths, toolchains, memory, MoE routing, harness confounds or long context. That is now stated on the front page, in [doctor/README.md](doctor/README.md) and in the tool's own docstring, so a clean run cannot be over-read. Its findings are also now ordered **Core tier first** within each verdict bucket, and every run prints which Core entries it implements, which it exercised, and which four (35, 53, 61, 77) it cannot check at all.

- **Traps [82](traps/template/82-system-prompt-relocates-to-last-user-turn.md) through [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md): a fourth serving stack.** llama.cpp `b9878-2da668617` with `--jinja`, against a Mistral-family Q8_0 GGUF of **unstated provenance** supplied by **Exile** for coverage and doctor portability. The checkpoint is deliberately not characterised: no capability claims, no benchmarks, no refusal or alignment probing, and every finding is scoped either to that artifact or, where the mechanism is server-side, to the llama.cpp build. Five template traps, one server introspection trap, and one negative. The one to read is [84](traps/template/84-tool-roundtrip-then-user-turn-is-unrenderable.md): a completed tool round trip followed by a user turn cannot be rendered at all, and the HTTP 400 blames the template rather than the message list, so the operator debugs the wrong thing. [83](traps/template/83-template-carries-a-baked-default-system-prompt.md) is the one with the widest blast radius: a hard-coded default system prompt is injected whenever the request omits one, which means every no-system-prompt control arm ever run on this checkpoint was not a control.

- **Trap [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md) is a negative, recorded with the same care as a positive.** `cache_prompt: false` **does** isolate a request from prior slot state on this build, which is a third data point that does **not** reproduce two prior stacks. It lands at measured here, raw not published, and with its build qualifier attached, because the whole value of a negative is the conditions under which it was obtained.

- **Traps 89 and 90, from [@drowzeys](https://github.com/drowzeys) (Keys)**, shared from his public notes rather than submitted, and credited by handle at his agreement. [89](traps/evaluation/89-hardlink-shard-pollution-invalidates-a-ladder.md): an in-place weight edit mutates the "stock" copy through a shared inode, so a quantisation ladder is measured against a baseline that moved. [90](traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md): a kernel library ships cubins for one architecture only, and the six errors on the way there each look like a fixable config bug; **its check cannot be run on our hardware and stays inline, marked unverified, rather than going under `checks/` where the contract would imply we had exercised it.** Two more of his findings landed inside traps 62 and 79 rather than taking numbers.

- **Trap [33](traps/routing/33-moe-inference-topk-expansion-tax.md) promoted to reported by others + reproduced here**, on a quantised build. The finder's numbers are all bf16 under HF transformers; ours are NVFP4 on vLLM, which under our own different-quant-different-unit rule left the question open rather than settled. It survives at roughly the reported magnitude: monotone across k in {8, 16, 24, 32}, two scoring protocols, two independent passes each, with the pre-registered primary contrast at **-4.50 points** paired at n=600, discordant 37/10, exact McNemar **p = 9.8e-05**, and an independent replicate at -4.00 points, 37/13, p = 0.000936. The same run re-measured our own noise: all four same-k restart pairs landed inside the plus-or-minus 1.3 point band (largest 0.83), every raised-k contrast outside it. The choice-logprob arms, which are the finder's own protocol, came back at -3.17 and -3.67 against his reported -3.67. Every published figure was re-derived from the answer sheets before publication by a checker written separately from the analyser that produced them. Raw is **not** shipped: [MAINTAINING](MAINTAINING.md#shipping-raw-data-in-the-repo) reserves in-repo raw for calibration constants other entries cite, and applying that rule to our own result rather than making an exception for it is the point. The runnable scripts do ship. [Writeup](mining/2026-07-28-trap-33-q1-nvfp4-confirmed.md). **Second first-party confirmation of an external contributor's finding** in this registry, after trap [35](traps/evaluation/35-identical-weights-do-not-score-identically.md); the **Found by** line did not move in either case.

- **Traps 75 to 81: first Ollama coverage**, plus two findings that are not Ollama. Ollama was named in CONTRIBUTING as a stack with no entries at all and is now off that list. The one with the highest operator cost is [77](traps/reasoning/77-only-one-request-field-is-validated.md): exactly one request field is validated and every other one is accepted and dropped, so a harness ported from another server measures its whole thinking-off arm on a thinking lane and every request returns 200. [78](traps/tools/78-tool-choice-accepted-and-ignored.md) is the one to check today if you run agents: `tool_choice` is inert in both directions, so the standard way to gate a turn **fails open**. Entries: [75](traps/versioning/75-release-asset-renamed-pinned-url-404.md), [76](traps/runtime/76-device-rejection-log-line-is-not-fatal.md), [77](traps/reasoning/77-only-one-request-field-is-validated.md), [78](traps/tools/78-tool-choice-accepted-and-ignored.md), [79](traps/memory/79-out-of-range-context-request-accepted.md), [80](traps/runtime/80-reasoning-parser-batches-sse-deltas.md) (a reasoning parser batching the SSE stream, which cost us a published speculative-decoding figure that reversed sign from +12.6% to -32.2% when re-measured), and [81](traps/memory/81-stopped-container-has-not-released-memory.md).

- **Two Ollama findings landed inside existing entries**: a third reasoning field name, split by route, with `reasoning_content` on none of them ([01](traps/reasoning/01-reasoning-field-two-names.md)); and the injection mirror of the in-text thinking toggle, where the template appends the marker to the user's last message and it leaks into the scored answer ([66](traps/template/66-in-text-thinking-toggle-mutates-user-text.md#the-mirror-case-injection-on-ollama)).

- **R2-39 settled on the stack it was scoped to.** Refuted as stated: empty content tracks tools alone, in both thinking states, and every empty response carried a tool call. Not a defect, a harness reading `content` and ignoring `tool_calls`. Also recorded: SGLang is [not infeasible](mining/2026-07-28-sglang-on-gb10-feasibility.md) on aarch64 GB10 CUDA 13, which is the opposite of the expected result and is why the note exists.

- **Traps 63 to 74: the NVIDIA Nemotron 3 family**, three checkpoints on GB10-class nodes across vLLM 0.20.0 and 0.25.1, including this registry's first multimodal lane. The one to read is [63](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md): the history-preservation gate on this family is called `truncate_history_thinking` and **`true` means discard**, which is the opposite polarity to the `preserve_thinking` this registry already documents, so a pipeline standardised on the known name silently does nothing. The field name compounds it: the template source reads `reasoning_content`, but the server drops that key before rendering and maps its own `reasoning` instead, so reading the template produces the wrong fix with high confidence. Entries: [63](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md), [64](traps/reasoning/64-answer-lands-in-reasoning-on-toggle-conflict.md), [65](traps/reasoning/65-parser-only-rescue-kwarg.md), [66](traps/template/66-in-text-thinking-toggle-mutates-user-text.md), [67](traps/template/67-history-rendered-as-object-repr.md), [68](traps/template/68-multimodal-part-order-discarded.md), [69](traps/template/69-minor-template-defects.md), [70](traps/runtime/70-in-repo-parser-not-bundled.md), [71](traps/runtime/71-mtp-config-key-and-draft-count.md), [72](traps/runtime/72-media-fetch-errors-are-5xx.md), [73](traps/evaluation/73-multimodal-token-cost-not-attributable.md), [74](traps/evaluation/74-non-speech-audio-fabricated-captions.md).

- **Eight more Nemotron findings landed inside existing entries rather than as new numbers**, which is the deduplication outcome CONTRIBUTING describes and the one that keeps the registry from fragmenting: a measured empty-content floor plus the demonstration that no single floor is safe to copy ([12](traps/evaluation/12-empty-content-at-token-ceiling.md), pointer in [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md)), two quant-label instances failing in opposite directions plus the labelling pattern itself ([10](traps/quantization/10-quant-label-is-not-the-kernel-path.md)), host-side rather than CUDA memory pressure ([13](traps/memory/13-utilization-fraction-on-unified-memory.md)), an inverted generation-config instance ([21](traps/versioning/21-no-generation-config-server-defaults-win.md)), a family whose card-versus-config answer differs per member ([17](traps/evaluation/17-per-arm-recommended-sampling-confound.md)), the parser-less default ([02](traps/template/02-orphaned-think-close-tag.md)), three read-but-undocumented kwargs against one documented ([07](traps/reasoning/07-reasoning-effort-silently-ignored.md)), and a third route to an empty `content` ([23](traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md)).

- **R2-29 unblocked and settled**: tool calls as raw text on Nemotron NVFP4 is [refuted as worded and reframed](mining/2026-07-28-r2-29-tool-calls-refuted-as-worded.md). The leaked format is nested XML, not JSON, and on vLLM a tools request without the parser flags is rejected with HTTP 400 rather than degraded, so the plain claim is unreachable there.

- **Traps 56 to 62: first coverage of a DeepSeek-V4-Flash serving path**, measured at request level only against a live two-node lane on 2026-07-28. Statuses are split rather than uniform, because the evidence is: the four structural findings are **reproduced here** and name the public source file a stranger reads to check them, while the two behavioural ones (the cold-versus-cached divergence, the depth curve) are **measured here, raw not published** and say so. Entries: [56](traps/template/56-checkpoint-ships-no-chat-template.md), [57](traps/reasoning/57-thinking-kwarg-truthiness-coercion.md), [58](traps/reasoning/58-reasoning-effort-injects-hidden-preamble.md), [59](traps/reasoning/59-reasoning-roundtrip-confabulation.md), [60](traps/runtime/60-cold-prefill-and-cache-hit-disagree.md), [61](traps/evaluation/61-advertised-window-fails-silently.md), [62](traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md), plus a [model page](models/deepseek-v4-flash.md) and a pre-registered but [unrun experiment](mining/2026-07-28-chunked-prefill-vs-cache-replay-experiment.md). Entry 61 was **renamed at merge**: it collided on a title with trap 55 from the external block, the two are distinct material, and ours was the one renamed because the framing was the contributor's first. They cross-link.

- **Traps 43 to 55: the registry's first large external contribution**, from [@TheTom](https://github.com/TheTom), who maintains the offlabel operator guide. Thirteen entries land at **contributor-measured, conditions as reported**: he measured every one on his own hardware and stated the conditions, and we have not reproduced them here. He originally marked them "reproduced here", which was **our documentation bug rather than his error**: CONTRIBUTING then defined that label as "you ran it and can link or produce the raw", which he satisfied exactly. The [status vocabulary](CONTRIBUTING.md#status-vocabulary) now says what we meant by it. Of the fifteen in his PR, one more is **folded rather than held**: his 44 lands as an amendment inside traps [12](traps/evaluation/12-empty-content-at-token-ceiling.md) and [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md), at his own suggestion and credited in both, supplying the reason a budget floor has to be a distribution rather than a number. Exactly **one entry is held**, his 56, pending the with-and-without chunked-prefill pair its status promises and never states. His eight check scripts are in separate review against the check contract, so the entries land with their inline assertions intact and their `Runnable:` pointers removed; every stripped line is recorded verbatim and goes back unchanged when the scripts land. **Numbering is provisional and was assigned at merge**, because five staged sets competed for the same range. His block kept its internal ordering and its **base**, so 43 is still 43. It did **not** keep its numbers: one entry folded and one was held, so everything above 43 slid down one place against the numbers published in the PR, and twelve entries moved. This line originally claimed no entry of his moved, which was wrong; the [PR-to-main map](MAINTAINING.md#the-pr-to-main-number-map) is published so a bookmarked number can be resolved. See [MAINTAINING.md](MAINTAINING.md#numbering-in-this-merge). Entries: [43](traps/template/43-tool-args-string-not-mapping.md), [44](traps/quantization/44-fp4-dequant-scale-swizzle-layout.md), [45](traps/quantization/45-fa-all-quants-cpu-fallback.md), [46](traps/versioning/46-stale-build-missing-arch-kernel.md), [47](traps/runtime/47-prefix-caching-autodisabled-hybrid.md), [48](traps/routing/48-dual-stack-mdns-latency-tax.md), [49](traps/evaluation/49-prompt-not-tokenized-to-target.md), [50](traps/evaluation/50-hidden-state-dump-convention.md), [51](traps/quantization/51-single-backend-nan-fused-path.md), [52](traps/evaluation/52-speed-measured-on-a-broken-config.md), [53](traps/runtime/53-config-edit-never-took-effect.md), [54](traps/evaluation/54-run-order-and-warm-cache-artifacts.md), [55](traps/evaluation/55-supported-context-is-not-trained-context.md).

- [minefield-doctor](doctor/) hardened after two independent adversarial
  audits both ranked it their second finding: the tool could report CHECKED
  AND CLEAN for conditions it had not verified, against its own documented
  contract that anything uncheckable goes to COULD NOT CHECK. Every `ok()`
  call was audited. **Eight false-clean classes were converted**, six of them
  found during the audit rather than named in it: bogus-kwarg acceptance with
  no readable template; a non-200 kwarg probe credited as server strictness
  with no no-kwarg control; a rejection that came from `reasoning_effort`
  rather than from unknown-kwarg strictness; thinking-on returning no
  reasoning field and no think tags; a thinking toggle map in which no arm
  fires; an orphan-tag check reported clean across arms that never returned;
  empty content that did **not** hit the cap; and sampling defaults called
  "matching" a shipped `generation_config` when the two sides declared no keys
  in common. A fourth output bucket, **INCONCLUSIVE**, now separates "the
  probe ran but several materially different states produce this result" from
  "the probe could not run", matching the `UNKNOWN` level
  [checks/preflight_template.py](checks/preflight_template.py) already uses.
- Doctor: `--hf-revision`. `--hf-repo` always read `resolve/main`, so an
  operator serving a pinned revision was compared against today's mutable main
  and told they had drift. The revision is now resolved through the hub API to
  an immutable commit sha, that sha is printed in every config finding, and an
  unresolvable ref is reported as INCONCLUSIVE rather than silently used.
- Doctor: the tool probe no longer over-diagnoses. It forces a call with
  `tool_choice` where the server supports it, which separates
  `MODEL_ELECTS_NOT_TO_CALL` and `TOOL_CALLING_UNAVAILABLE` from
  `TOOL_MARKUP_NOT_PARSED`. Where `tool_choice` is unsupported the ambiguity
  cannot be removed, so the verdict is INCONCLUSIVE, printed with
  **CONFIDENCE: LOW** and all six candidate states listed, instead of the
  PROBLEM the old code asserted.
- Doctor: honest coverage. The root README's "checks most of this registry"
  is corrected to **17 of 42**, and every run now prints
  `implemented N/42 | executed on this stack N | clean N | problems N |
  inconclusive N | not implemented N` plus the caveats that make even 17 an
  overstatement: 25 shares trap 04's heuristic, 16 and 22 are annotations on
  the trap-12 finding, 10/17/21 need `--hf-repo`, and 04/20/25 need a render
  path.
- Doctor: committed regression suite. `doctor/tests/fixture_server.py` is a
  declared-behaviour fixture lane plus a fixture hub;
  `doctor/tests/test_doctor_verdicts.py` asserts the verdict for every
  scenario, pairs each defect with a control lane that differs only in the
  flag under test, and enforces two structural invariants: a CLEAN cannot be
  emitted without at least one assertion that held, and a not-clean verdict
  cannot be emitted without at least one that failed. `--json` now carries
  those assertions verbatim, not only prose. 31 tests, plus the two existing
  suites, all stdlib-only and contacting no network.
- Doctor and [checks/preflight_template.py](checks/preflight_template.py):
  landed the previously staged fixes. vLLM render path
  (`/v1/chat/completions/render` plus `/detokenize`, falling back to
  `/tokenize`), so traps 04, 20 and 25 are no longer skipped on every vLLM
  lane; multimodal probes (surface, usage attribution, content-part ordering,
  media error classification, with audio and video declared uncovered);
  quantisation read from `hf_quant_config.json` when `config.json` is silent,
  so a ModelOpt NVFP4 checkpoint is no longer reported as unquantized; and
  four kwarg-enumeration false-positive classes removed (Jinja tests, filters,
  macro parameters, namespace keyword arguments) while the self-defaulting
  idiom that had been suppressing real kwargs is recovered.
- Trap [35](traps/evaluation/35-identical-weights-do-not-score-identically.md)
  promoted from **reported by others** to **reproduced here**, and generalised.
  [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b) remains the
  originating report (98.7% cross-machine agreement, bf16 under HF
  transformers). First-party measurement on a different build class,
  Qwen3.6-35B-A3B NVFP4 under vLLM nightly `a346d589` on two GB10 nodes:
  pooled 3513/3600 = **97.58%** item agreement across six pairings of four
  identical-configuration runs, MMLU n=600 greedy. The generalisation is that
  **two machines are not required**: the cross-machine pairs (97.17%, 97.83%,
  98.33%) straddle the within-process pair (97.33%), so the disagreement lives
  inside a single server process and same-machine serial execution does not buy
  determinism. Speculative decoding ruled out as the cause (97.33% to 98.17%
  with overlapping intervals). Raw, serial scorer and an independent
  re-derivation script published in
  [mining/2026-07-28-agreement-floor-data/](mining/2026-07-28-agreement-floor-data/);
  write-up in
  [mining/](mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md).
  Calibration adopted: an MMLU-style paired delta below about **1.3 points at
  n=600** is not distinguishable from a re-run on that stack. The band is an
  accuracy delta over four-way multiple-choice items and does **not** transfer
  to binary-outcome results such as firing-rate counts.
- Trap
  [42](traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md):
  a single-turn eval harness scores tool-call exits as wrong answers.
  Found by [@apollo-mg](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067)
  and measured at n=492 on Laguna S 2.1 UD-Q2_K_XL under llama.cpp on 4x
  Tesla P100: pooled pass@1 71.95% against his own 90.85% baseline, a drop
  of 18.90 points, with WRONG moving 30 to 31 and accuracy conditional on
  attempting at 354/386 = 91.71%. Lands as **reported by others** with
  **raw published** (12.7 KB tarball: verbatim system prompt, tool schemas,
  per-sample buckets and token counts for all 164x3, run and driver logs).
  The depth-side half of the same exit-path mechanism was measured here
  independently on NVFP4 under vLLM 0.25.1 on GB10.
- The trap carries an explicit open question rather than a settled claim:
  the termination benefit (no-extractable 11 to 0, cap-hits 12 to 1) is
  untested with tool output fed back, and both parties recorded opposing
  predictions before the discriminating arm runs. Cite it as measured
  under schema-presence-only.
- Nine traps ([33](traps/routing/33-moe-inference-topk-expansion-tax.md)
  through
  [41](traps/runtime/41-static-batching-buys-power-not-throughput.md))
  mined from [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s
  public research log on raising a pretrained MoE's inference top-k from 8
  to 32, offered by him for this purpose and credited by handle. All nine
  land as **reported by others**; three of them were re-scored here from the
  per-item JSON he publishes, and the recomputations match his stated
  p-values.
- New category [traps/routing/](traps/routing/) for MoE expert routing and
  activation config. Trap 33 did not fit quantization (nothing is
  quantized) or runtime (it is a model-config knob, not a stack property),
  and filing it under either would have hidden it from the people who need
  it. As MoE serving knobs proliferate, this is where they go.
- Trap [33](traps/routing/33-moe-inference-topk-expansion-tax.md) is the
  headline: raising a MoE's active-expert count costs accuracy **before any
  training**, with no error and no warning, because the selected gate scores
  are renormalized and the extra experts dilute rather than add. Selection
  is intact and the nesting is exact. Measured monotone in k on two
  benchmarks (MMLU 84.33 to 80.67, GSM8K 89.33 to 86.50, k=8 to k=32,
  n=600 paired, both significant), and repaid with zero training by scaling
  the tail ranks back down.
- The other eight are measurement traps that made real numbers wrong:
  [34](traps/evaluation/34-baseline-you-degraded-yourself.md) a baseline you
  degraded yourself (same arm, same items: a significant +6.10 pt win
  against the handicapped reference, no effect against the shipped one),
  [35](traps/evaluation/35-identical-weights-do-not-score-identically.md)
  identical weights agreeing on only 98.7% of items across machines,
  [36](traps/evaluation/36-token-cap-is-an-arm-level-handicap.md) token caps
  binding at 33.4% of items for one arm and 0.0% for another,
  [37](traps/evaluation/37-uniform-zero-is-a-harness-verdict.md) three
  distinct all-arms-zero results that were all harness faults, one of them
  reporting `infra_error_n=0`,
  [38](traps/template/38-template-owns-the-opening-think-tag.md) the opening
  think tag that the template supplies and the model never writes,
  [39](traps/runtime/39-device-map-auto-offloads-and-returns-garbage.md)
  `device_map="auto"` spilling onto an excluded device and returning
  gibberish,
  [40](traps/evaluation/40-ngram-decontamination-false-positives.md) a
  contamination screen removing 31.7% of a corpus on the strength of one
  boilerplate n-gram, and
  [41](traps/runtime/41-static-batching-buys-power-not-throughput.md) static
  batching that raised GPU utilization to 100% and throughput not at all.
- Verification queue recorded in
  [mining/](mining/2026-07-28-qwen36-a6b-verification-queue.md): trap 33 is
  the first candidate for a **reproduced here** upgrade, since we have a
  Qwen 3.6 35B-A3B NVFP4 lane and his measurements are all bf16 on HF
  transformers.

## 2026-07-27

- [Doctor](doctor/) portability notes from its first mlx_lm field run: 6 of
  9 check families port cleanly with no misfires; the two gaps (stack
  identification, and history-assembly checks lacking a render path on
  stacks without a template endpoint) degrade to explicit COULD NOT CHECK
  rather than wrong output. A `--template-file` argument is recorded as a
  tracked enhancement so the history-assembly checks can run from the
  `chat_template.jinja` that ships next to local weights.
- Trap [32](traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md)
  landed, reproduced here: mlx_lm's server `--max-tokens` launch flag is a
  per-request default, not a ceiling. A client sending a larger
  `max_tokens` runs straight past it (measured 1600 through a 1024 flag,
  167 s on a lane whose normal replies take 1 to 2 s), with no warning and
  nothing in the response distinguishing clamped from obeyed. Behavioral on
  mlx-lm 0.31.3; source-confirmed at that release and current main, where
  the flag's own help text calls it a default. Combined with trap
  [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) on
  the same stack, mlx_lm has no server-side gate a client cannot exceed by
  asking.
- MLX coverage becomes real: a read-only characterization pass on a stock
  mlx_lm lane (prism-ml Ternary-Bonsai-27B-mlx-2bit, Apple silicon) lands
  MLX-scoped sections in five entries. Trap
  [01](traps/reasoning/01-reasoning-field-two-names.md): `reasoning` is the
  one live field name on mlx_lm (non-streaming and streaming), plus two MLX
  wrinkles: empty channels are ABSENT keys (a thinking cap-hit has no
  `content` key at all, so `msg["content"]` raises KeyError), and every
  streaming delta carries `role="assistant"`. Traps
  [03](traps/reasoning/03-enable-thinking-default-drift.md) and
  [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md):
  `--chat-template-args` is mlx_lm's spelling of the
  server-supplies-the-kwarg arm, and it is a per-request default, not a
  gate (second stack for 29). Trap
  [07](traps/reasoning/07-reasoning-effort-silently-ignored.md): third
  stack, with a wider acceptance surface: even invented TOP-LEVEL body keys
  return 200, so a typoed parameter is a silent behavior change. Trap
  [12](traps/evaluation/12-empty-content-at-token-ceiling.md): reproduced,
  with the absent-key flavor of the signature. Traps
  [20](traps/reasoning/20-reasoning-write-field-name-diverges.md) and
  [04](traps/template/04-history-reasoning-stripping.md): the server emits
  `reasoning` while the shipped template only reads back
  `reasoning_content`, confirmed behaviorally with a marker round-trip;
  naive replay silently strips all prior reasoning on this lane. Per-model
  and per-stack index rows added for mlx_lm.
- New [mining/](mining/) area: verification notes on mined candidates that
  did not (or could not) promote to entries, so negatives and blocked tests
  are recorded instead of lost. First three notes, from a hardware
  verification pass over the round-2 queue: R2-39 (thinking plus tools
  yields empty output, Ollama-reported) did not reproduce on vLLM across a
  2x2 kwarg-by-tools matrix on two lanes, scoping the candidate to Ollama;
  R2-31 (DeepSeek V4 system-message quality cliff) did not reproduce at
  small n on the production lane, with an identical system-independent miss
  in all three arms; and R2-27/R2-23/R2-10/R2-29 are recorded as not
  testable on current lanes with exactly what each test needs.
- Trap [06](traps/reasoning/06-identity-sentence-eviction.md) status
  resolved: the promised independent test on a second stack is in, and the
  prefix-key mechanism did not reproduce there (identity as literal first
  line fired 0/40 at the critical cell). A position-generic tail effect was
  found instead: roughly 29 tokens of any token-band-matched text appended
  at the END of the system prompt reopens the gate on both tested builds
  (hybrid and NVFP4, in-run interleaved controls, every suffix vs bare
  p <= 0.025; identity vs matched fillers NS). Entry now scopes both
  results by stack, and the check and fix cover both ends of the prompt.
  Full data and drivers: laguna-s21-lab `identity-prefix/`.
- Trap [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md)
  gains the production-lane replication (28-row ceiling audit, three
  lanes, n=2 to 3 per cell): the budget floor is a distribution, not a
  number. The 27B produced 26K to 61K reasoning chars on the identical
  prompt, so even a 16384 ceiling fails 1 in 3; every capped tail was
  honest truncation, not degeneration. A no-thinking control completes
  everywhere in 1.5K to 5K tokens, tying the floor to
  [trap 29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)'s
  client-kwarg re-enable path.
- Trap [31](traps/evaluation/31-leftover-oracle-reranker.md) landed,
  reproduced here on one frozen suite: a leftover oracle re-ranker (a
  temp-directory debugging script that boosts candidates by expected id,
  or looks them up by the answer's file name stem) turns a failing
  retrieval eval into a passing one, and the inflated number outlives the
  script. Arms were reconstructed mechanisms run in one labelled harness
  next to the honest engine, not recovered original code. Ships the two
  detection fingerprints (top-1 equals top-3 exactly for expected-id
  boosting; saturation at exactly 1.0 for answer-derived lookups) and a
  copyable no-oracle negative control that fails the run when injected
  answer metadata changes a ranking.
- Trap [30](traps/template/30-default-system-message-silently-replaced.md)
  landed, reproduced here (structural, read from the shipped chat template
  of the serving checkpoint pair): the template's built-in default system
  message is used only when the caller sends no system message at all, and
  any caller system message replaces it wholesale. Consequences: every
  with-system-prompt condition is confounded with default-identity-absent
  by construction, and "no system message", "empty system message", and
  "any system message" are three distinct rendered prompts. Found while
  designing the identity-prefix study, before any cell ran.
- Cross-family measurements spliced into three existing entries (staged by
  the standardized probe sweep, landed after review): trap
  [04](traps/template/04-history-reasoning-stripping.md) gains the Qwen 3.6
  template confirmation (same stripping machinery, different rendering, no
  behavioral collapse) and the version-dependent-fix warning (Qwen 3.5
  reads no `preserve_thinking`); trap
  [07](traps/reasoning/07-reasoning-effort-silently-ignored.md) upgraded to
  reproduced-here on two Qwen models on llama.cpp, plus the
  bogus-kwarg-accepted-with-200 finding; trap
  [03](traps/reasoning/03-enable-thinking-default-drift.md) gains the
  four-lane absent-kwarg landing map.
- [minefield-doctor](doctor/) shipped: a single stdlib-only file that
  diagnoses any OpenAI-compatible endpoint against the registry.
  Read-only and bounded (at most 8 small temperature-0 completions),
  three-section output (PROBLEMS / CHECKED AND CLEAN / COULD NOT CHECK),
  every finding linked to its trap, and a `--report` flag that emits a
  paste-ready "I hit a trap" block. Acceptance-tested on five lanes
  across llama.cpp, vLLM, and MLX, where it independently rediscovered
  traps 21, 29, 07, and the 22-class cap behavior already measured there.
- Trap [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)
  landed, reproduced here: a server-side reasoning-off flag is a default,
  not a gate; any client kwarg re-enables thinking and blows non-thinking
  token budgets (15K to 61K chars of reasoning measured through an 8192
  cap).
- Verification round on our fleet: traps
  [26](traps/tools/26-tool-call-inside-unclosed-think.md) and
  [24](traps/template/24-official-template-breaks-cpp-jinja.md) gain dated
  not-reproduced-on-current-build notes (30/30 forced-tool turns clean with
  thinking engaged on llama.cpp b9066/b9193; full tool schema rendered by
  the C++ engine despite `|items` in the template), and the per-model index
  gains a clean-preflights table starting with Ternary-Bonsai-27B on MLX.
  Negative results are recorded, not dropped.
- Traps [21](traps/versioning/21-no-generation-config-server-defaults-win.md)
  and [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md),
  reproduced here on our llama.cpp lanes: no generation_config.json means
  the server's built-in sampling silently becomes "the model's settings"
  (five parameters diverged from the card on Qwen3.5-9B, matched exactly on
  the Qwen3.6-27B control), and the thinking budget floor differs by size
  within one family (9B converts at 8192, 27B needs 16384 on the same
  byte-identical task).
- Six new reported-by-others traps mined from upstream trackers and
  community template work, every linked source read and verified before
  writing (two candidates were dropped when their GitHub issues turned out
  to be resolved as user error):
  [23](traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md)
  streaming answer in the reasoning channel,
  [24](traps/template/24-official-template-breaks-cpp-jinja.md) official
  templates break C++ Jinja engines,
  [25](traps/template/25-empty-think-blocks-poison-prefix-cache.md) empty
  think blocks poison prefix cache,
  [26](traps/tools/26-tool-call-inside-unclosed-think.md) tool call inside
  unclosed think,
  [27](traps/quantization/27-nvfp4-accuracy-cliff-config-misses.md) NVFP4
  accuracy cliffs from config misses,
  [28](traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md)
  MTP fails only under concurrency or temperature. Trap 19 gains the
  vLLM parser-pair face. Hall of fame gains an upstream-reports table.
- New trap [20](traps/reasoning/20-reasoning-write-field-name-diverges.md):
  the reasoning write field is runtime-specific. Found by @Defilan while
  replicating trap 04 on llama.cpp: only `reasoning_content` reaches the
  llama.cpp template, `reasoning` is silently dropped and renders
  byte-identical to the stripped arm, while vLLM passes `reasoning` through.
  Trap 04's fix section now names the correct field per runtime, and its
  stacks section carries the llama.cpp rendering replication.
- Contribution overhaul: "I hit a trap" issue form (four plain questions,
  maintainer writes the entry), [MAINTAINING.md](MAINTAINING.md) promotion
  workflow and status conventions, per-model index at
  [models/README.md](models/README.md), finder named at the top of every
  entry, README reframed around the reader who just lost an evening.
- Expanded beyond the founding stacks: twelve new traps (08 through 19)
  covering runtime toolchains, container images, quantization kernel paths,
  unified memory, speculative decoding, eval harnesses, versioning, and
  tool calling. Category directories, per-entry statuses,
  [HALL_OF_FAME.md](HALL_OF_FAME.md).
- Date normalization: found-dates re-anchored to shipping commits.
- Launched with seven traps (reasoning fields, templates, thinking control,
  scorer normalization) and `checks/preflight_template.py`.
