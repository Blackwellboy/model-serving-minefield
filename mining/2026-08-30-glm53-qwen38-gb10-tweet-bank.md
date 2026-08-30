# Tweet bank: GLM-5.3 / Ling-3.0 / Qwen3.8 GB10 harvest

**Date:** 2026-08-30

Companion to [`2026-08-30-glm53-qwen38-gb10-public-source-harvest.md`](2026-08-30-glm53-qwen38-gb10-public-source-harvest.md).

These are public-post drafts, not evidence upgrades. Status language follows the mining packet. Community-source findings stay community-source; existing Minefield owners stay credited; unresolved items are written as unresolved; H30-31 is a source-vetting lesson, not a bug claim.

## H30-01 - explicit KV pin / activation reserve

**Tweet**

A server can boot clean, warm clean and pass short prompts... then die only when a long prompt arrives.

Why? Explicitly pinning KV memory can remove the activation headroom the automatic allocator would have reserved.

"It fits" is not proven at boot. It is proven at peak first-forward.

## H30-02 - fast load is not stable load

**Tweet**

A faster model loader can win the stopwatch and still lose the deployment.

One DGX Spark report saw a dramatically faster load path, then a distributed rank disappeared roughly a minute later.

Measure:
load complete -> first forward -> generation -> dwell.

Not just "weights loaded".

## H30-03 - GB10 UVM livelock

**Tweet**

96% GPU utilisation.
~10 W power draw.
Model making no useful progress.
Host still partly alive.

That is the kind of telemetry that makes debugging GPU servers dangerous.

High utilisation does not prove useful compute. On UMA systems, memory pressure can look like activity while forward progress is dead.

## H30-04 - page cache is GPU headroom on UMA

**Tweet**

On DGX Spark, "free GPU memory" is not just a GPU question.

Host page cache competes with CUDA-visible unified memory.

Two boots can show the same model and same flags while having materially different usable headroom because the host memory state is different.

UMA means memory accounting has to be whole-system accounting.

## H30-05 - dependency install downgrades NCCL

**Tweet**

This is a brutal dependency trap:

You install a performance dependency to fix an attention/kernel path.
Package resolution succeeds.
An unrelated NCCL version silently changes underneath you.
Your previously working multi-node fabric stops initialising.

A successful pip install is not a preserved runtime.

## H30-06 - mixed compiler stack after successful install

**Tweet**

"pip install succeeded" is not the same as "the compiler stack is coherent".

A resolved environment can still leave mismatched CuTeDSL/CUTLASS components that fail much later during kernel compilation.

Lock the dependency graph you actually executed, not just the package you intended to change.

## H30-07 - in-range does not mean valid

**Tweet**

One of my favourite failure classes from this mining pass:

A sparse index buffer can contain stale IDs that are still numerically IN RANGE.

So bounds checks pass.
The gather reads real memory.
It is just the wrong logical memory.

"Valid address" is not "valid state".

## H30-08 - corrupted token IDs hidden by readable text

**Tweet**

Intermittent token-ID corruption can hide surprisingly well in normal English.

A bad token may render as a small text glitch and look harmless.

Until the corrupted ID lands on a tool/control boundary and desynchronises the parser.

For serving validation, inspect token IDs too. Readable output is not enough.

## H30-09 - 377 MB logical tensor, 13.6 GB allocation

**Tweet**

A tensor can look like ~377 MB by logical size and still trigger a ~13.6 GB allocation.

Padded/strided views can describe a backing-storage span wildly larger than `numel * element_size`.

If memory math only counts logical elements, the allocator can still surprise you by an order of magnitude.

## H30-10 - warm restart stdout corrupts JSON

**Tweet**

Cold start: works.
Warm restart: crash loop.
Same image. Same config.

Cause? A Python `sitecustomize` hook printed one diagnostic line to stdout. Shell command substitution captured it before JSON and turned a valid `--speculative-config` into garbage.

Machine-readable stdout is an API boundary.

## H30-11 - 100K prefill crushes peer decode

**Tweet**

A 100K cold prefill dropped a peer decode from ~55 tok/s to 5 tok/s.

No preemption.
Perfect speculative acceptance.
Healthy hardware.

The global step budget was simply being consumed by the sparse-MLA prefill.

Scheduler counters can be green while latency is getting murdered.

## H30-12 - 1.1M KV tokens that were not fungible

**Tweet**

The server reported ~1.1 MILLION KV tokens.

Yet one ~36K request used 44.6% of the pool and three ~256K sessions could not fit.

After the allocator fix, that ~36K request fell to ~16%.

A global "KV tokens" number does not mean those tokens are interchangeable admission capacity.

## H30-13 - context gate misses deeper crash boundary

**Tweet**

A 20K context test can pass and still certify a kernel that hard-crashes at 28K.

That sounds obvious until your qualification suite says "long context passed" because it never crossed the resource-shape boundary where the kernel changes behaviour.

Test the actual claimed window, not a convenient fraction of it.

## H30-14 - average tok/s hides periodic stalls

**Tweet**

Average throughput can hide a server that alternates between fast decode bursts and multi-second zero-progress stalls.

If memory pressure or swapping is involved, publish the inter-token gap distribution too.

30 tok/s average can describe a smooth 30 tok/s server or a terrible user experience.

## H30-15 - Qwen3.8 MTP doom loop

**Tweet**

The Qwen3.8 speculative "doom loop" report is much more interesting than "MTP broke".

It points to 3 separate alignment failures:
- next-step token position
- target/draft LSE rows
- compacted verify slice indexing

One visible repetition loop can be multiple state bugs stacked together.

## H30-16 - not all KV is KV

**Tweet**

A single `kv-cache-dtype=fp8` knob can be semantically wrong on a hybrid model.

Qwen3.8 Flash-Next mixes ordinary attention KV with recurrent GDN/DeltaNet state.

Those are not automatically the same numerical object just because the serving API calls all of it "cache".

One flag can hide multiple precision contracts.

## H30-17 - generic KV abstraction explodes memory

**Tweet**

Generic abstractions are great until the model is not generic.

One GLM DFlash path reportedly turned a custom grouped cache layout into roughly an order-of-magnitude more per-request memory by forcing heterogeneous groups through one uniform page model.

A clean interface can still encode terrible memory geometry.

## H30-18 - rank role, not machine, controls headroom

**Tweet**

Interesting open question from the GLM Spark mining pass:

KV headroom differed by several GiB between distributed ranks, and the gap appeared to follow the rank role rather than the physical Spark.

If true, the smallest role-specific budget caps the whole cluster.

Same hardware does not guarantee symmetric runtime footprint.

## H30-19 - production-only blank tool args

**Tweet**

This one stays OPEN, and that is the interesting part.

A production request repeatedly returned blank required tool args. Byte-identical solo replay was clean. A maintainer then ran 53 synthetic cases and got 0 failures.

Before blaming the model, preserve raw XML/token IDs, finish reason, timeout and cache state.

## H30-20 - NaNs only in the middle shape

**Tweet**

Small shape: clean.
Big shape: clean.
Production shape in the middle: NaNs.

That is why "smoke test + max-throughput test" is not enough for custom kernels.

Sweep the actual shape window. Some backend bugs live in a narrow dispatch/resource region both endpoints completely miss.

## H30-21 - distributed A/B with stale worker image

**Tweet**

A distributed A/B is invalid if one worker never actually received the update.

Same service name and successful restart are not provenance.

After every cluster mutation, prove on EVERY rank:
- image digest
- overlay hash
- runtime commit
- live process start time

Otherwise your A/B may be two different stacks.

## H30-22 - grammar state changes inside speculative window

**Tweet**

Speculative decoding can cross a structured-output state boundary inside one draft window.

Imagine the draft contains `</think>` or a stop token, but later drafted tokens are still advanced against the grammar state from before/after that transition.

This is where "matcher already terminated" bugs get very real.

## H30-23 - position-0 acceptance lies

**Tweet**

A speculative drafter can look healthy at position 0 while later draft positions are collapsing.

Mean acceptance can hide it too.

If you are validating DFlash/MTP, plot acceptance by draft position.

First-token acceptance is not proof the causal/attention semantics of the whole speculative tail are correct.

## H30-24 - grouped cache layouts need per-group accounting

**Tweet**

For hybrid serving, stop publishing one global KV number as if it explains everything.

MLA, indexer, Mamba/recurrent state, K-pool tails and draft SWA can have different page geometry and sharing rules.

Report bytes/token, block IDs and effective allocation PER CACHE GROUP.

## H30-25 - speculative acceptance is workload-dependent

**Tweet**

There is no single honest number called "this model's speculative acceptance rate".

Math, code, structured output and open prose can produce materially different acceptance on the exact same engine.

A single median can be useful operationally. It is not a property of the model independent of workload.

## H30-26 - temperature 0 changes speed too

**Tweet**

Temperature 0 is not only a quality/reproducibility choice.

It can materially change speculative serving throughput because deterministic top-1 verification is not the same execution workload as probabilistic sampling.

If sampling changes, the speed comparison changed too.

## H30-27 - max_num_seqs is not resident-session capacity

**Tweet**

`max_num_seqs=4` does NOT mean "four 256K sessions fit".

It is a scheduler width.
Actual long-session residency is constrained by the cache geometry and allocator underneath it.

Request concurrency, execution concurrency and resident-context capacity are three different numbers.

## H30-28 - fixing decode can worsen TTFT

**Tweet**

A good serving fix can move pain instead of removing it.

Mia's mixed-prefill skip preserved an active decode lane by intentionally refusing to mix a peer prefill into that step.

Decode recovered. Prefills queued.

So benchmark BOTH sides: decode smoothness and TTFT/waiting. One green metric can hide the trade.

## H30-29 - your cold prefix may be warm

**Tweet**

If the server has no reliable prefix-cache reset, repeating the same "cold" prompt does not make it cold.

Salt or uniquify the prefix and prove cached-token count.

Otherwise your benchmark can quietly transition from prefill measurement to cache-replay measurement while the harness keeps calling every run "cold".

## H30-30 - stdout is part of the data plane

**Tweet**

Logs are not harmless if stdout is being consumed by another program.

`sitecustomize`, shell profiles, patch scripts, warnings and banners can all corrupt command substitution or machine-readable pipelines.

Rule: if stdout is data, test it like an API. Diagnostics go to stderr.

## H30-31 - the scary bug report that should NOT become a trap

**Tweet**

Minefield mining lesson: a dramatic reproduction is not enough.

One issue showed tools + JSON mode returning fabricated content instead of a tool call. Minutes later, the REPORTER closed it and said they were not convinced the bug was valid.

Read the closure and comments before turning an issue title into "fact".

## H30-32 - image digest is not source reproducibility

**Tweet**

An exact container digest proves which binary image you ran.

It does not automatically prove which public source commit, local wheel set or overlay patch produced it.

Binary identity and source reproducibility are different provenance claims. You need both if you want to verify whether a code-level fix is actually present.

## H30-33 - thinking:false is already a Minefield trap

**Tweet**

`thinking:false` can still leave reasoning work alive.

We already have this class in Model Serving Minefield: the setting you passed is not the behaviour you proved.

The Ling-3.0 evidence is another reminder to inspect returned reasoning/content and token behaviour, not trust a boolean because the server accepted it.

## H30-34 - accepted memory flag, irrelevant memory manager

**Tweet**

A memory flag can be perfectly valid syntax and still be irrelevant to the allocator actually serving your model.

On a unified-memory path, a "static memory fraction" control may not mean what it means on a discrete-GPU pool.

Parser acceptance proves the flag exists. Runtime telemetry proves whether it did anything.

## H30-35 - launch memory is not fit memory

**Tweet**

"The model loaded with 20 GiB free" is not a capacity result.

First request can create a large memory jump from activations, graphs, caches, workspaces and lazy allocations.

Measure launch, first forward, representative generation and steady state separately.

Fits-at-idle is not fits-in-use.

## H30-36 - disabling CUDA graphs is not a universal rule

**Tweet**

A stack-specific CUDA graph workaround should stay stack-specific.

If one SM121 path is unstable with graphs, the lesson is not "CUDA graphs are bad on GB10".

Find the exact graph/capture/state mechanism, pin the affected build, and keep the workaround scoped to evidence.

## H30-37 - model list green, first chat socket resets

**Tweet**

`GET /v1/models` = 200.
First chat request = connection reset.
Retry 100 ms later = works.
Process never died.

That is why readiness is a ladder.

Port open -> HTTP alive -> model listed -> first real generation -> required capability.

Do not collapse those into one green light.

## H30-38 - JSON-looking string is not a mapping

**Tweet**

Tool arguments can LOOK like JSON and still have the wrong host-language type.

`"{\"city\":\"Sydney\"}"` is a string.
`{"city":"Sydney"}` is an object.

If your agent expects a mapping, visual similarity is irrelevant. Validate the representation your client actually receives.

## H30-39 - NVML memory failure does not mean inference failure

**Tweet**

On UMA hardware, an NVML memory query can fail while inference is completely healthy.

That creates two traps:
1. monitor says GPU is broken when it is not
2. harness silently loses its memory safety signal and keeps testing

Observability APIs need capability checks too.

## H30-40 - /metrics is not guaranteed by OpenAI compatibility

**Tweet**

An OpenAI-compatible serving API does not guarantee a Prometheus `/metrics` endpoint.

One build can serve chat perfectly and return 404 for metrics.

If your soak harness depends on telemetry, probe that capability before the run. "API healthy" and "monitoring available" are separate claims.

## H30-41 - random fixture, fake performance movement

**Tweet**

Nominally "the same benchmark" can move throughput by several percent just because the randomly generated prompt/output shape changed.

Freeze tokenizer-exact fixtures.
Publish actual ISL/OSL.

If the workload changed, the benchmark changed, even when the script name stayed the same.

## H30-42 - SSE chunks are not tokens

**Tweet**

Streaming chunks are transport events, not tokenizer tokens.

One SSE chunk can contain multiple tokens. One token can interact with buffering/control boundaries in ways that change chunking.

Never calculate tok/s from chunk count. Count tokenizer IDs or use server-reported token usage you have validated.

## H30-43 - shared /dev/shm can couple "isolated" services

**Tweet**

Two model servers can have different ports, model paths and GPUs and STILL interfere through shared CUDA-IPC `/dev/shm` state.

Network isolation is not process-state isolation.

If multi-service behaviour is weird, A/B shared vs private shm before blaming the model.

## H30-44 - video preprocessor OOM before model serving

**Tweet**

A multimodal OOM is not automatically a model-memory OOM.

A rough video bytes->frames estimate can explode into thousands of decoded frames before the model's own context/memory limits even run.

Measure the preprocessing allocation separately from model KV/weights.

## H30-45 - RDMA GID is observed state, not a portable constant

**Tweet**

Hard-coding an RDMA GID index because it worked on one host is configuration debt waiting to happen.

Interface/GID selection is discovered state tied to the actual network configuration.

Probe it on the machine you are serving from. Do not turn yesterday's observation into tomorrow's constant.

## H30-46 - shared network JIT cache corrupts builds

**Tweet**

A shared compiler/JIT cache across nodes sounds efficient until two machines race on artifacts with different local assumptions.

For custom CUDA/CuTeDSL serving stacks, node-local cache identity can be a correctness requirement, not just a performance choice.

Cache reuse needs provenance too.

## H30-47 - Qwen full CUDA graph MTP corruption already has an owner

**Tweet**

Important Minefield discipline: same symptom does not mean new trap.

Qwen3.8 MTP corruption under full CUDA graphs is already an existing Minefield class.

The new mining value is the separate positional/LSE/slice alignment report. Deduping mechanisms matters more than growing the trap count.

## H30-48 - familiar quant label, wrong representation

**Tweet**

A "standard NVFP4 loader" can successfully load a checkpoint and still be the wrong execution path for a specialised pack.

Loader acceptance is not representation proof.

For custom `nvfp4_suh`/specialised layouts, verify the effective kernels/tensor representation at runtime, not just the quant label.

---

# Suggested posting order

For maximum public impact, lead with:

1. H30-12 - 1.1M KV tokens that were not fungible
2. H30-11 - 100K prefill crushing peer decode 11x
3. H30-10 - one stdout line breaking warm restart JSON
4. H30-07 - in-range stale IDs reading the wrong KV
5. H30-05 - dependency install silently downgrading NCCL
6. H30-15 - Qwen3.8 MTP doom-loop mechanisms
7. H30-09 - 377 MB logical tensor -> 13.6 GB allocation
8. H30-03 - 96% util / ~10 W / no progress UVM state
9. H30-16 - one KV dtype hiding heterogeneous state
10. H30-31 - the retracted scary issue and why source vetting matters

Then use the remaining posts as a recurring **Model Serving Minefield** series rather than dumping all 48 at once.
