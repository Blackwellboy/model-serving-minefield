from pathlib import Path
import re
import subprocess
import textwrap

MAIN_PARENT = "b7186f98f3d3733ec379a4561c4a7446cf1e2cde"


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def require(text, needle, label):
    if needle not in text:
        raise SystemExit(f"missing expected text for {label}: {needle[:120]!r}")


# ---------------------------------------------------------------------------
# PR #61 adjudication: keep 127-130; hold proposed 131; fold proposed 132;
# renumber proposed 133 -> 131. Then promote Q16/#36 -> 132 and Q17/#38 -> 133.
# ---------------------------------------------------------------------------

held_loader = Path("traps/runtime/131-parallel-loader-collectives-wedge-uma.md")
folded_jit = Path("traps/evaluation/132-first-request-after-boot-pays-jit.md")
hf_old = Path("traps/versioning/133-hf-refs-file-breaks-offline-resolution.md")
hf_new = Path("traps/versioning/131-hf-refs-file-breaks-offline-resolution.md")

for p in (held_loader, folded_jit, hf_old):
    if not p.exists():
        raise SystemExit(f"expected PR61 file missing: {p}")

held_loader.unlink()
folded_jit.unlink()

hf = hf_old.read_text(encoding="utf-8")
hf_old.unlink()
hf = hf.replace("# Trap 133:", "# Trap 131:", 1)
hf = hf.replace(
    "Separately, a fetch pinned by commit hash alone writes no `refs/main` at all, so the hub has no mapping from the bare model name to a revision and any offline resolution by name has nothing to look up. Both are quiet byte-level defects in the staged artifact; neither shows up during an online fetch.",
    "Separately, a staging workflow that fetches only by commit hash may leave no `refs/main`. That second case is not necessarily a Hub defect, but it still leaves no branch-to-commit mapping for a later bare-name offline lookup. The trap is treating a staged cache as complete without validating the ref bytes and the resolution path that production will actually use."
)
source_note = (
    "\n\n**Public corroboration for the newline half.** "
    "[`huggingface_hub` issue #4133](https://github.com/huggingface/huggingface_hub/issues/4133) "
    "reports the same offline-resolution failure when a trailing newline becomes part of the commit-hash string. "
    "That upstream report does not upgrade this entry's status; the measured lane and counts here remain contributor-measured."
)
marker = "\n\n**Stacks and builds bitten.**"
require(hf, marker, "HF refs source insertion")
hf = hf.replace(marker, source_note + marker, 1)
write(hf_new, hf)

trap132 = r'''# Trap 132: speculative placeholders can corrupt the prompt tail only on cold chunked prefill

**Found by @tonyd2wild; original scheduler-guard root-cause fix credited to @Roady001.**

**Status: contributor-measured, conditions as reported.** @tonyd2wild measured the bad/good arms on a private 2x DGX Spark (GB10) lane and reported them in [issue #36](https://github.com/Blackwellboy/model-serving-minefield/issues/36). Blackwellboy has not independently reproduced that lane; the captured production payload and raw per-request rows are not published.

**Symptom.** A speculative-decoding server passes warm smoke tests and ordinary short prompts, then real agent sessions that force a cold prefill begin their answer by continuing the system prompt. The corruption is coherent enough to look like a model misunderstanding: replies can start mid-word, reproduce text from the tool/skill catalogue, leak a BOS marker, or return only whitespace while billing tokens. The same prompt becomes clean as soon as its long prefix is warm.

The reported separation was stark: **0/19 warm requests bad** versus **44/44 cold requests bad** across four configurations. The contributor forced the cold path by changing a nonce at the *front* of the long system prompt on every request.

**Mechanism.** On the affected scheduler, speculative-placeholder resizing ran for requests that were still in chunked prefill instead of only for decode steps. That attached speculative tokens to the final prompt chunk of a cold resume and corrupted the prompt tail before generation began. A guard that excludes `is_prefill_chunk` requests from the placeholder path removes that state transition.

The controlled fix is the load-bearing evidence: **44/44 cold bad without the guard -> 0/28 bad with the guard**. Lowering speculative depth was a negative control, not a fix: k=3 remained **10/10 bad** without the scheduler guard, while guarded k=3 and guarded k=5 were both **0/10 bad**. The guard also reduced the reported cold-prefill time from roughly 36 s to roughly 12 s on the captured workload, consistent with speculative work no longer being attached to prefill chunks.

**Stacks and builds bitten.** vLLM `0.21.1rc1` plus a custom GB10 kernel overlay; `fraserprice/DeepSeek-V4-Flash-DSpark`; two NVIDIA DGX Spark GB10 nodes, TP=2 over RoCE; `nvfp4_ds_mla` KV, block size 256; DSpark MTP with `num_speculative_tokens=5`, probabilistic draft sampling; `--max-model-len 1000000`, `--max-num-seqs 6`, `--max-num-batched-tokens 8192`, chunked prefill enabled. The deployed image predated the scheduler guard even though the recipe documented the patched scheduler path.

**The check.** Do not test this with a warm prompt. Use a long prompt and put a unique nonce in its first tokens on every request so prefix reuse cannot rescue the run. Capture the raw first output tokens and compare the same pinned workload with the scheduler guard absent and present. On the affected install, a quick source check is:

```bash
docker exec <container> grep -n 'is_prefill_chunk' \
  /PATH/site-packages/vllm/v1/core/sched/scheduler.py
```

The source check is not a substitute for the cold A/B, but it tells you whether the known guard is even present.

**The fix.** Use a build carrying the scheduler guard, or bind-mount the exact guarded scheduler only when that patch is pinned to the image revision. Do **not** lower speculative depth as a substitute: the contributor's k=3 negative control remained corrupted and only threw away decode throughput.

**Found.** 2026-08-15, after a production-shaped agent payload was forced cold on every iteration and the warm-only smoke-test blind spot became reproducible.

**Attribution.** @tonyd2wild measured the warm/cold separation, the guarded A/B, the speculative-depth negative control and the latency change, and filed [issue #36](https://github.com/Blackwellboy/model-serving-minefield/issues/36). The issue explicitly credits @Roady001 for the original scheduler-guard root-cause fix. Preserve both credits.

**Related.** [60](60-cold-prefill-and-cache-hit-disagree.md) is a different cold-versus-cache behavioral divergence whose mechanism remains unresolved; [62](62-spec-decode-garble-under-wrong-drafter-config.md) is drafter-configuration corruption; [28](28-mtp-fails-only-under-concurrency-or-temperature.md) is a different speculative-failure boundary.
'''
write("traps/runtime/132-cold-prefill-spec-placeholder-corrupts-prompt-tail.md", trap132)

trap133 = r'''# Trap 133: a DSpark draft loader can silently drop shared-expert weights and halve speculative yield

**Found by @tonyd2wild.**

**Status: contributor-measured, conditions as reported.** @tonyd2wild measured the before/after lane and documented the source mapping in [issue #38](https://github.com/Blackwellboy/model-serving-minefield/issues/38). Blackwellboy has not independently reproduced the performance rows. The source locations and missing mapping are inspectable; the contributor's raw per-request benchmark rows are not published.

**Symptom.** The model is coherent and correct, the server reports no warning at normal log level, and speculative decoding is clearly active -- but acceptance and decode throughput sit around half of the expected lane. The target verifier hides the drafter defect because every bad proposal is simply rejected.

On the reported lane, repairing the loader moved cumulative acceptance **25.7% -> 60.2%**, accepted tokens per step **2.28 -> 4.01**, and mean decode throughput **32.7 -> 55.4 tok/s**, while decode steps/s stayed roughly flat (**14.4 -> 13.8**). A warm peak-finder on the fixed path reached **78.4 tok/s at 98.9% acceptance**. The only load-time trace was twelve debug-level `Skipping unknown DSpark weight` messages.

**Mechanism.** The draft loader's `_STACKED_PARAM_NAME_MAPPING` omitted the two shared-expert rows for `.shared_experts.w1` and `.shared_experts.w3`. Across three draft stages that silently dropped twelve tensors belonging to the always-on shared expert. The target model's loader already had the equivalent mapping; the draft path did not. Because the target verifies every emitted token, output quality can stay green while speculative acceptance collapses.

This is a sibling of [Trap 109](../quantization/109-requant-skips-draft-layer-experts.md), not a duplicate. Trap 109 is a checkpoint/requant problem that leaves draft experts in the wrong representation. This entry is a **serving-loader name-mapping gap** on an otherwise loadable drafter path.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3`, private fork with custom sm_120/sm_121 kernels; `deepseek-ai/DeepSeek-V4-Flash-0731` plus a community-abliterated derivative on the second lane; FP8 target weights, NVFP4 MLA KV, DSpark draft stages; two DGX Spark GB10 nodes, TP=2 over RoCE; `dspark_block_size: 5`, target layer ids 40/41/42, markov rank 256, probabilistic draft sampling, prefix caching and chunked prefill enabled.

**The check.** Compare the target loader's stacked-parameter mapping with the DSpark draft loader's mapping on the exact installed build. The affected draft path is missing the shared-expert `w1` and `w3` rows. Then enable debug logging for one load and look for unknown DSpark-weight skips. Finally scrape the server's speculative counters under a fixed workload; a clean target with abnormally low accepted tokens per step is the signature this bug can hide behind.

Do not estimate decode tok/s from SSE chunk count on this stack: one streamed chunk can contain all tokens accepted in one speculative step. Use completion-token accounting against wall time, and keep steps/s separate from tokens/s.

**The fix.** Use a build whose DSpark draft loader carries the shared-expert mapping, or add the two missing mapping rows to the pinned loader and verify that the unknown-weight skips disappear. Make skipped DSpark weights a launch gate or at least a warning; a debug-only skip is too quiet for tensors that can halve the drafter's useful work.

**Found.** 2026-08-15, after low speculative acceptance was traced back from metrics to twelve debug-only skipped weights.

**Attribution.** @tonyd2wild found and measured the loader gap and filed [issue #38](https://github.com/Blackwellboy/model-serving-minefield/issues/38). Keep the performance figures labelled contributor-measured; the source mapping is independently inspectable on the affected build.

**Related.** [109](../quantization/109-requant-skips-draft-layer-experts.md), [71](71-mtp-config-key-and-draft-count.md), [62](62-spec-decode-garble-under-wrong-drafter-config.md), [80](../evaluation/80-parser-buffering-fakes-server-stalls.md).
'''
write("traps/runtime/133-dspark-loader-drops-shared-expert.md", trap133)

# ---------------------------------------------------------------------------
# Correct Trap 10 review feedback from merged PR #60.
# ---------------------------------------------------------------------------
trap10_path = "traps/quantization/10-quant-label-is-not-the-kernel-path.md"
t10 = read(trap10_path)
old = "Behavior/correctness checks remained\ngreen on the matched OBLIT target."
new = (
    "The matched behavior/correctness fixture remained green, but a separate tiny\n"
    "eight-task intelligence smoke scored the Frozenlock reference **8/8** and the\n"
    "matched OBLIT target **7/8** because of one strict tool-call-format near-miss.\n"
    "That bounded miss is reported rather than hidden, and this experiment does\n"
    "**not** establish universal intelligence equivalence."
)
require(t10, old, "Trap 10 Codex P2 correction")
t10 = t10.replace(old, new, 1)
write(trap10_path, t10)

# ---------------------------------------------------------------------------
# Fold Seth's cold-boot JIT evidence into existing Trap 54, and add the new
# first-party GLM 322,672-token cold/warm cache result without creating an ID.
# ---------------------------------------------------------------------------
trap54_path = "traps/evaluation/54-run-order-and-warm-cache-artifacts.md"
t54 = read(trap54_path)
insert54 = r'''
## Added 2026-08-25: first-request JIT can look like a dead lane

**Status of this addendum: contributor-measured, conditions as reported.** @sethforprivacy reported a stock DeepSeek-V4-Flash-0731 DSpark lane on 2x DGX Spark where a 32K request that normally took about **22 s** had still not completed after **10+ minutes** immediately after a cold boot. GPU utilization sat around 96% while the request-level token counters stayed at zero. Worker logs, however, were printing CuTeDSL/Triton JIT and FlashInfer autotuner/perf-cliff messages. A later A/B on the already-warm cluster did not show the event.

That is the mechanism already owned by this trap -- compilation, graph/kernel-cache population and run order -- so it is **folded here rather than assigned a new number**. The extra operational signature is useful: on some stacks the counters advance only when the request completes, so "GPU busy + zero tokens" during the first request is not proof of a wedge. Read the worker log before killing the lane, and do not benchmark until a normal warmup request completes at ordinary latency.

## Added 2026-08-25: 322K context made the cold/warm gap three orders of magnitude

**Status of this addendum: measured here, raw not published.** On the frozen GLM-5.2 Path-A triple-DGX-Spark lane, a tokenizer-counted **322,672-token** retrieval request recovered planted markers at 10%, 50% and 90% in both states. Cold TTFT was **1883.5 s**; the immediate warm repeat was **3.41 s**. The correctness result stayed green in both arms, so this is evidence for the *latency/measurement-state* half of Trap 54, not for Trap 60's answer-divergence mechanism.

Publication rule sharpened by the pair: at deep context, "TTFT" without an explicit cold/warm or prefix-reuse state can differ by roughly three orders of magnitude while the model, request and answer stay the same.

'''
marker54 = "\n**The fix.** Treat any unpaired, un-counterbalanced measurement as a hypothesis."
require(t54, marker54, "Trap 54 insertion")
t54 = t54.replace(marker54, "\n" + insert54 + "**The fix.** Treat any unpaired, un-counterbalanced measurement as a hypothesis.", 1)
t54 = t54.replace(
    "**Attribution.** TheTom. 2026-08-17 cold/idle corroboration and short-request\namortization measurements: @tonyd2wild.",
    "**Attribution.** TheTom. 2026-08-17 cold/idle corroboration and short-request\namortization measurements: @tonyd2wild. 2026-08-25 cold-boot JIT signature and\nmeasurement: @sethforprivacy. 2026-08-25 322,672-token GLM cold/warm pair:\nBlackwellboy.",
    1,
)
write(trap54_path, t54)

# ---------------------------------------------------------------------------
# Trap 124: PR61 accidentally duplicated/truncated prose around the new caveat.
# Restore current-main source, then insert the contributor caveat cleanly.
# ---------------------------------------------------------------------------
trap124_path = "traps/runtime/124-dgx-spark-gb10-stuck-low-power-state-under-load.md"
base124 = subprocess.check_output(
    ["git", "show", f"{MAIN_PARENT}:{trap124_path}"], text=True
)
needle124 = (
    "A single low clock sample from a short kernel is not enough. The measured diagnosis used sustained load because short kernels can leave telemetry stale or sampled between boosts.\n"
)
require(base124, needle124, "Trap 124 clean insertion")
add124 = r'''

**A query caveat for the healthy-but-capped case, contributed by @sethforprivacy.** **Status: contributor-measured, conditions as reported.** On the contributor's private 2x DGX Spark GB10 lane, `nvidia-smi -lgc` successfully applied a clock cap while `nvidia-smi -q -d CLOCK` still printed the hardware `Max Clocks` value and an idle sample remained low. On that measured driver the query did not expose the applied range, so the output can look like "the cap did not apply" even when it did.

For that state, preserve the command/service journal line that records the applied range and sample `clocks.sm` under sustained load. Do not use the static max-clock query alone to distinguish a genuinely stuck-low-power unit from a healthy unit that is intentionally capped.
'''
base124 = base124.replace(needle124, needle124 + add124, 1)
write(trap124_path, base124)

# ---------------------------------------------------------------------------
# README symptom router: final 127-133 map is gapless.
# ---------------------------------------------------------------------------
readme_path = "README.md"
r = read(readme_path)
start = r.index("| A router outage answers 502 for hours while model backends are healthy")
end_marker = "\n\nIf you run one check from this registry"
end = r.index(end_marker, start)
rows = """| A router outage answers 502 for hours while model backends are healthy, and the container restart count climbs | A whole-file bind mount shadowed a module inside the image; an unattended image update made every start die at import | [127](traps/versioning/127-bind-mount-shadow-drift-crash-loop.md) | contributor-measured, conditions as reported |
| Decode collapses under concurrent prefills with the preemption counter pinned at zero, and a single-flag fix changes nothing | The prefill-admission flag is defined but never read in the waiting-admission loop | [128](traps/runtime/128-admission-flag-never-read-decode-starvation.md) | contributor-measured, conditions as reported |
| Warm long requests suddenly re-prefill at zero cache hits while the daytime hit rate is ~97% | The shared prefix hit is the minimum across KV cache groups; sliding-window groups hit zero past their horizon | [129](traps/memory/129-prefix-cache-hit-min-across-kv-groups.md) | contributor-measured, conditions as reported |
| CUDA graphs report captured FULL yet the top decode shape runs eager; a one-token spec-depth change flips it | The capture-size clamp silently drops the largest batch shape from graph coverage | [130](traps/runtime/130-cudagraph-clamp-runs-top-shape-eager.md) | contributor-measured, conditions as reported |
| A staged model fails to resolve offline after a cache copy, or a bare-name offline lookup has no branch mapping | A malformed or missing HF hub `refs/*` mapping makes the local snapshot unreachable by the revision production actually requests | [131](traps/versioning/131-hf-refs-file-breaks-offline-resolution.md) | contributor-measured, conditions as reported |
| Warm spec-decode smokes are clean but a long cold prefill starts the reply by continuing the system prompt | Speculative placeholders are attached to the final chunked-prefill block instead of decode-only state | [132](traps/runtime/132-cold-prefill-spec-placeholder-corrupts-prompt-tail.md) | contributor-measured, conditions as reported |
| Output is correct but speculative acceptance and decode speed are roughly halved, with only debug-level unknown-weight skips | The DSpark draft loader silently dropped the shared expert because two stacked-parameter mapping rows were missing | [133](traps/runtime/133-dspark-loader-drops-shared-expert.md) | contributor-measured, conditions as reported |"""
r = r[:start] + rows + r[end:]
write(readme_path, r)

# ---------------------------------------------------------------------------
# Model index.
# ---------------------------------------------------------------------------
models_path = "models/README.md"
m = read(models_path)
pattern = re.compile(r"^\| DeepSeek V4-Flash-0731, stock weights, Anemll DSpark vLLM .*?\|$", re.M)
if not pattern.search(m):
    raise SystemExit("Seth model-index row not found")
new_model_rows = (
    "| DeepSeek V4-Flash-0731, stock weights, Anemll DSpark vLLM `0.25.2.dev0` image, 2x DGX Spark GB10 (@sethforprivacy's private lane) | "
    "[127](../traps/versioning/127-bind-mount-shadow-drift-crash-loop.md), [128](../traps/runtime/128-admission-flag-never-read-decode-starvation.md), "
    "[129](../traps/memory/129-prefix-cache-hit-min-across-kv-groups.md), [130](../traps/runtime/130-cudagraph-clamp-runs-top-shape-eager.md), "
    "[131](../traps/versioning/131-hf-refs-file-breaks-offline-resolution.md); evidence added to [54](../traps/evaluation/54-run-order-and-warm-cache-artifacts.md), "
    "[61](../traps/evaluation/61-advertised-window-fails-silently.md), [71](../traps/runtime/71-mtp-config-key-and-draft-count.md), [124](../traps/runtime/124-dgx-spark-gb10-stuck-low-power-state-under-load.md) "
    "*(contributor-measured, conditions as reported; proposed parallel-loader/UMA cause held in mining pending isolation)* |\n"
    "| DeepSeek V4-Flash DSpark, private 2x DGX Spark GB10 lanes reported by @tonyd2wild | "
    "[132](../traps/runtime/132-cold-prefill-spec-placeholder-corrupts-prompt-tail.md), [133](../traps/runtime/133-dspark-loader-drops-shared-expert.md) "
    "*(contributor-measured, conditions as reported)* |"
)
m = pattern.sub(new_model_rows, m, count=1)
write(models_path, m)

# ---------------------------------------------------------------------------
# Hall of Fame: preserve all contributor credit and the held/folded dispositions.
# ---------------------------------------------------------------------------
hof_path = "HALL_OF_FAME.md"
h = read(hof_path)
seth_pattern = re.compile(r"^\| \*\*@sethforprivacy\*\* .*?\|$", re.M)
if not seth_pattern.search(h):
    raise SystemExit("Seth Hall-of-Fame row not found")
seth_row = (
    "| **@sethforprivacy** | Five canonical DeepSeek-V4-Flash / DGX Spark contributions from PR #61: whole-file bind-mount shadow drift (127), "
    "an admission flag the scheduler never reads (128), hybrid-KV prefix-cache hit collapse (129), CUDA-graph top-shape clamp/eager fallback (130), "
    "and HF hub refs/offline-resolution staging failure (131). His cold-boot JIT measurement is folded into Trap 54; second-lane data strengthens 61, 71 and 124. "
    "The proposed parallel-loader/UMA mechanism is retained in mining with his credit while its cause is still under-isolated. | "
    "[127](traps/versioning/127-bind-mount-shadow-drift-crash-loop.md), [128](traps/runtime/128-admission-flag-never-read-decode-starvation.md), "
    "[129](traps/memory/129-prefix-cache-hit-min-across-kv-groups.md), [130](traps/runtime/130-cudagraph-clamp-runs-top-shape-eager.md), "
    "[131](traps/versioning/131-hf-refs-file-breaks-offline-resolution.md); [54](traps/evaluation/54-run-order-and-warm-cache-artifacts.md), "
    "[61](traps/evaluation/61-advertised-window-fails-silently.md), [71](traps/runtime/71-mtp-config-key-and-draft-count.md), [124](traps/runtime/124-dgx-spark-gb10-stuck-low-power-state-under-load.md) context |"
)
h = seth_pattern.sub(seth_row, h, count=1)
tony_pattern = re.compile(r"^\| \*\*@tonyd2wild\*\* .*?\|$", re.M)
if not tony_pattern.search(h):
    raise SystemExit("tonyd2wild Hall-of-Fame row not found")
tony_row = (
    "| **@tonyd2wild** | Seven contributor-measured multi-node serving findings: the five DGX Spark entries 117-121, plus cold-prefill speculative-placeholder corruption isolated by a scheduler guard (132), and a DSpark draft-loader mapping gap that silently drops the shared expert (133). "
    "For Trap 132, the original scheduler-guard root-cause fix remains credited to **@Roady001** as Tony's report requests. | "
    "[117](traps/runtime/117-fuse-gemm-comms-accepted-then-disabled.md), [118](traps/runtime/118-ray-log-monitor-off-hides-worker-progress.md), "
    "[119](traps/memory/119-free-memory-drifts-down-after-churn.md), [120](traps/runtime/120-indexer-block-table-omits-spec-overhang.md), "
    "[121](traps/runtime/121-ssh-fanout-mangles-json-args.md), [132](traps/runtime/132-cold-prefill-spec-placeholder-corrupts-prompt-tail.md), "
    "[133](traps/runtime/133-dspark-loader-drops-shared-expert.md) |"
)
h = tony_pattern.sub(tony_row, h, count=1)
write(hof_path, h)

# ---------------------------------------------------------------------------
# Changelog: replace contributor's provisional 127-133 section with the final
# maintainer map and record the PR60 review correction.
# ---------------------------------------------------------------------------
ch_path = "CHANGELOG.md"
ch = read(ch_path)
section_start = ch.index("## 2026-08-24 — traps 127-133: seven contributor-measured entries from a stock DeepSeek-V4-Flash DSpark lane")
section_end = ch.index("## 2026-08-24 — traps 125-126:", section_start)
new_ch = r'''## 2026-08-25 — PR #61 adjudicated + Q16/Q17 promoted (canonical 127-133)

Maintainer pass over **@sethforprivacy** PR #61 plus the two long-standing strong candidates from **@tonyd2wild**. Contributor commits/credit are preserved; numbers are assigned gaplessly at merge as MAINTAINING requires.

- **127** — @sethforprivacy: whole-file bind-mount shadow + unattended image drift can turn a previously valid operator patch into an import crash loop.
- **128** — @sethforprivacy: `max_num_partial_prefills` can be accepted/configured while the measured scheduler path never reads it, leaving decode starvation invisible to the preemption counter.
- **129** — @sethforprivacy: shared prefix reuse can collapse past a sliding-window horizon because the common hit is the minimum across KV groups; high aggregate hit rate can hide it.
- **130** — @sethforprivacy: CUDA-graph capture-size clamping can leave the largest speculative decode shape eager even while smaller shapes are captured.
- **131** — @sethforprivacy: HF hub `refs/*` byte/mapping defects can break offline revision resolution. This is PR #61's proposed 133, renumbered at merge; the trailing-newline half has public upstream corroboration in huggingface_hub #4133.
- **132** — @tonyd2wild, original scheduler-guard fix credited to @Roady001: cold chunked prefill can receive speculative placeholders and corrupt the prompt tail while warm smoke tests remain clean (issue #36 / Q16).
- **133** — @tonyd2wild: a DSpark draft-loader mapping gap can silently skip the shared expert, collapsing speculative acceptance/throughput while target-verified output stays coherent (issue #38 / Q17).

PR #61 dispositions that deliberately did **not** get their proposed numbers:

- proposed **131** parallel-loader/UMA wedge: **HELD in mining**, because the observed NCCL timeout + hard worker wedge is strong but the claimed transient-UMA-memory cause is not isolated from other distributed-loader failure modes;
- proposed **132** first-request JIT: **FOLDED into Trap 54**, because cold compilation/graph/cache warm-up and first-arm A/B contamination are already Trap 54's mechanism. Seth's 10+ minute cold-boot observation and JIT log signature are retained there.

Second-lane additions from @sethforprivacy to Traps **61, 71 and 124** are retained; Trap 124's prose was repaired during integration so the clock-query caveat no longer duplicates/truncates the existing fix paragraph.

Also corrects the newly merged Trap 10 AutoRound addendum after Codex review: the matched behavior fixture stayed green, but the separate tiny intelligence smoke was **8/8 Frozenlock vs 7/8 OBLIT** (one strict tool-call-format near-miss), so no intelligence-equivalence claim is made.

'''
ch = ch[:section_start] + new_ch + ch[section_end:]
write(ch_path, ch)

# ---------------------------------------------------------------------------
# Open questions: promotion is staged on this branch; keep the issue queue valid
# until the PR merges, then issues can be closed with canonical links.
# ---------------------------------------------------------------------------
oq_path = "mining/OPEN_QUESTIONS.md"
oq = read(oq_path)
oq = oq.replace(
    "- **Note.** Strong canonical candidate, deliberately unnumbered until promotion\n  is built against current `main`. It is adjacent to Trap 60 but not currently\n  owned by it: Trap 60 records cold-versus-cache behavioral divergence without\n  this isolated scheduler mechanism.",
    "- **Note.** Canonical promotion is staged as **Trap 132** on the 2026-08-25\n  maintainer adjudication branch, pending exact-head CI/merge. It remains distinct\n  from Trap 60: Trap 60 records cold-versus-cache behavioral divergence without\n  this isolated scheduler mechanism.",
    1,
)
oq = oq.replace(
    "- **Note.** Strong canonical candidate, deliberately unnumbered until promotion\n  is built against current `main`. It is a sibling of Trap 109, not a duplicate:\n  Trap 109 owns a requant/checkpoint-format failure, while this candidate is a\n  serving-loader mapping failure on the drafter path.",
    "- **Note.** Canonical promotion is staged as **Trap 133** on the 2026-08-25\n  maintainer adjudication branch, pending exact-head CI/merge. It remains a sibling\n  of Trap 109, not a duplicate: Trap 109 owns a requant/checkpoint-format failure,\n  while this candidate is a serving-loader mapping failure on the drafter path.",
    1,
)
write(oq_path, oq)

# ---------------------------------------------------------------------------
# Maintainer adjudication note, including held candidate and number map.
# ---------------------------------------------------------------------------
adjudication = r'''# 2026-08-25 maintainer adjudication: @sethforprivacy PR #61 + Q16/Q17

Source contribution: [PR #61](https://github.com/Blackwellboy/model-serving-minefield/pull/61), authored commit `773e0150bba67d46948a17ee91d6c26d87b7fb01` by **@sethforprivacy**. The maintainer integration preserves that commit in ancestry rather than copying the contribution onto main without git attribution.

## Final PR #61 disposition

| PR number | Disposition | Main owner |
|---|---|---|
| 127 bind-mount shadow drift | PROMOTE | Trap 127 |
| 128 admission flag never read | PROMOTE | Trap 128 |
| 129 hybrid-KV prefix hit minimum | PROMOTE | Trap 129 |
| 130 CUDA-graph top-shape clamp | PROMOTE | Trap 130 |
| 131 parallel loader / UMA wedge | HOLD, unnumbered | this mining note |
| 132 first request pays JIT | FOLD | Trap 54 addendum |
| 133 HF hub refs offline resolution | PROMOTE, renumber | Trap 131 |
| second-lane data on 61 / 71 / 124 | RETAIN | existing entries |

The base number **127 is preserved** for the external contribution. Folding/holding two proposals closes the gap before the final PR61 entry, so its proposed 133 slides to 131. That is the merge-time numbering policy already documented in MAINTAINING.

## Why proposed 131 is held

The observation is valuable: fastsafetensors multi-node load reached ~7/24 shards, then a ~600 s NCCL broadcast watchdog fired; the worker remained reachable at L4 but stopped completing service initialisation and required a physical power cycle; reverting to the default loader restored repeatable load.

What is **not yet isolated** is the proposed root cause, "transient unified-memory staging pressure". The report has stronger NVRM allocation-retry noise and a steady-state/peak warning, but no direct transient-memory trace that owns the broadcast timeout. There are also public distributed-fastsafetensors failure mechanisms on 2x DGX Spark -- for example [vLLM #34180](https://github.com/vllm-project/vllm/issues/34180), where rank-local file ordering produces mismatched broadcasts -- showing that "loader + NCCL timeout" does not uniquely identify UMA pressure.

**CONFIRM:** on the pinned affected loader, capture per-rank shard/tensor order plus transient host/UMA pressure through the failure. Show matching collective sequence across ranks, then make one loader-memory/staging control change that removes the wedge while the distributed work ordering stays identical.

**REFUTE / re-route:** demonstrate rank-order/tensor mismatch, another loader bug, or a clean high-pressure control with the same memory envelope but no timeout. In that case the finding may still become a loader/distributed-order trap, but not the UMA-pressure trap as proposed.

Credit stays with **@sethforprivacy** either way.

## Why proposed 132 folds into Trap 54

Trap 54 already owns cold compile/kernel-cache/graph warm-up plus run-order A/B contamination. Seth's contribution adds a particularly useful DGX/DSpark signature -- GPU busy, request token counters still zero, worker logs actively compiling, first request >10 minutes vs ~22 s warm -- but it is the same mechanism and the same fix discipline. The measurement and credit are retained as a dated Trap 54 addendum rather than inflating the canonical count.

## Public corroboration used in adjudication

- `huggingface_hub` [#4133](https://github.com/huggingface/huggingface_hub/issues/4133): trailing newline in `refs/<revision>` becomes part of the offline-resolved commit string.
- vLLM [#51441](https://github.com/vllm-project/vllm/issues/51441): hybrid sparse-attention prefix-cache misses at specific prompt lengths, adjacent corroboration for the multi-KV-group cache issue.
- Mia's current DeepSeek-V4-Flash launcher documents the same family of scheduler/capture constraints (`LONG_PREFILL_TOKEN_THRESHOLD`, a partial-prefill knob that is a no-op on that fork, and capture sizing tied to `max_num_seqs * (k+1)`). These are corroboration only; Seth's entries remain `contributor-measured, conditions as reported`.

## Q16 / Q17

The two older strong open candidates are promoted in the same final numbering block so the registry remains gapless:

- issue #36 / Q16 -> **Trap 132**, measured by **@tonyd2wild**, with original scheduler-guard root-cause/fix credit preserved for **@Roady001**;
- issue #38 / Q17 -> **Trap 133**, measured by **@tonyd2wild**.

Both remain contributor-measured; this integration does not relabel them as Blackwellboy reproduction.

## Separate correction from PR #60 review

Codex correctly flagged that Trap 10's new AutoRound addendum said behavior/correctness remained green without mentioning the separate **7/8** OBLIT intelligence smoke against **8/8** Frozenlock. The canonical text is corrected in this batch to report the bounded tool-format near-miss and explicitly reject an intelligence-equivalence claim.
'''
write("mining/2026-08-25-seth-pr61-q16-q17-adjudication.md", adjudication)

print("MAINT_ADJUDICATION_SOURCE_EDIT=PASS")
