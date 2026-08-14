# First-party promotion audit — 2026-08-14

**Disposition: routing note only. No new canonical trap IDs in this PR.**

A wider audit of Blackwellboy's private first-party campaign/evidence repositories and historical Minefield staging branches found several candidates that were not represented in the initial 2026-08-14 public audit. This note records only public-safe mechanism summaries and publication gates. Raw private evidence, machine names, endpoints, local paths and session data are intentionally not copied here.

The purpose is to stop good evidence being lost while preserving the registry's evidence standard: a private observation does not become a public canonical trap merely because it is interesting.

## Strong promotion candidates

### 1. Resumed tool-result history loses required API metadata

**Current class:** `STRONG_FIRST_PARTY_CANDIDATE`

A fresh OpenAI-compatible structured tool turn can pass while a resumed/persisted agent session later reconstructs a materially different `role=tool` message. In the first-party incident, an internal tool identity survived persistence but the API-facing `name` field did not. Restoring the missing tool-result metadata and validating the associated tool-call ID, assistant tool-call object and ordering repaired the isolated history path and passed the targeted validator.

The general lesson is narrower than "the model's tool parser broke": **a one-turn tool smoke does not prove that the harness can serialize and replay persisted tool history.**

Current public ownership search found no exact canonical owner for metadata lost specifically during persisted/resumed tool-result reconstruction. [Trap 84](../traps/template/84-tool-roundtrip-then-user-turn-is-unrenderable.md) is adjacent but different: it owns a template alternation failure after a tool round trip, not loss of tool-result metadata during persistence.

**Publication gate:** produce a sanitized minimal request-history reproducer and rerun exact ownership search against the then-current registry before allocating an ID.

### 2. Cold SM120 JIT compilation can exhaust host memory when large model weights are already resident

**Current class:** `STRONG_FIRST_PARTY_CANDIDATE`

A first-party RTX 5090 / SM120 campaign isolated a startup failure where a heavy CUDA/FlashInfer compilation phase and resident model weights competed for host memory. The compiler, rather than the model engine itself, was killed under memory pressure. The working operational shape was to compile the cold path before model load, serialize the heavy compiler work, persist/version the resulting cache, and then load/serve from the warm cache.

This is distinct from a generic "GPU OOM" diagnosis: **the failing resource owner can be the host compiler process created by cold JIT, and compile/load ordering is part of the serving configuration.**

Current public search found no exact canonical owner for this cold-JIT-plus-resident-weights host-OOM class.

**Publication gate:** publish a sanitized, version-pinned compile/load A/B with enough logs to distinguish compiler host OOM from engine/GPU OOM.

### 3. Practical request admission can be lower than the displayed context/KV headline

**Current class:** `STRONG_FIRST_PARTY_CANDIDATE`

A first-party hybrid-KV/speculative-serving campaign found a bounded request-size region below the configured/displayed context headline where a request could remain waiting on capacity before prefill, with no ordinary OOM and no immediate API validation failure. The practical boundary was determined by the serving engine's actual whole-sequence block admission rules, reserved blocks and free block pool under that configuration, not by the headline token figure alone.

[Trap 13](../traps/memory/13-utilization-fraction-on-unified-memory.md) and [Trap 98](../traps/runtime/98-speculative-decode-default-max-seqs-oom-uma.md) are adjacent memory/speculation owners. Neither currently states this narrower failure mode: **a request below the advertised/configured context can be unadmittable and wait before prefill because practical block admission is lower than the displayed capacity.**

**Publication gate:** sanitize the exact block arithmetic, pass/fail boundary and affected serving build before canonical promotion.

### 4. The UI-selected benchmark endpoint can differ from the data-plane endpoint actually measured

**Current class:** `STRONG_FIRST_PARTY_MEASUREMENT_CANDIDATE`

A first-party benchmark-HUD bug made endpoint selection look successful while local requests still traversed the development proxy's default `/v1` target. Pasting or scanning another local port changed the visible endpoint, but the benchmark traffic could continue hitting the same default backend. The correction made the local proxy route by the selected port/path and recorded the actual live API base in result output.

The general Minefield lesson is important: **control-plane selection is not evidence of data-plane identity.** A benchmark can display model/endpoint B while the HTTP path still measures endpoint A, producing perfectly plausible but mislabeled numbers.

Current public ownership search found no exact canonical owner for endpoint-selector/proxy divergence in a benchmark client.

**Publication gate:** create a small two-mock-endpoint regression showing different model IDs/response markers and prove that selector A and B really reach different backends. Preserve the actual resolved request base in the benchmark receipt.

### 5. Stale injected skill/profile truth can beat the live runtime configuration

**Current class:** `STRONG_FIRST_PARTY_HARNESS_CANDIDATE`

A short first-party agent session answered a concrete live-infrastructure question with a stale, different deployment. The useful A/B is that the bare model did not invent that deployment; the agent harness loaded a stale skill/profile surface containing the old lane and then the model repeated and mutated those injected facts. The live provider configuration already pointed at the correct deployment, but that control-plane truth was not itself present in the model-facing prompt.

The general lesson is distinct from ordinary model hallucination: **a harness can possess correct live configuration while simultaneously injecting stale retrieved/bootstrap context that tells the model something else.** A pointer to canonical truth is not proof that the runtime loaded or obeyed it.

Current public search found no exact canonical owner for stale retrieved skill/bootstrap truth overriding a correct live provider configuration.

**Publication gate:** sanitize a minimal harness A/B with (a) live config truth, (b) stale injected skill truth, (c) exact model-facing prompt/tool trace, and (d) bare-model control. Do not publish private fleet identities.

### 6. Accepted structured-output schema can be semantically inert

**Current class:** `BOUNDED_FIRST_PARTY_API_COMPAT_CANDIDATE`

A bounded llama.cpp/Muse API matrix found `response_format=json_object` effective while a `response_format=json_schema` request was accepted on the tested path without demonstrating that the supplied schema constrained the output. Current public ownership searches found no exact canonical record for the narrower **accepted schema request != schema enforcement** contract.

This is not a claim that all llama.cpp structured output is broken. It is a request-surface verification rule: **valid-looking JSON and HTTP acceptance are not evidence that a specific JSON schema was applied.**

**Publication gate:** rerun a minimal schema that the unconstrained model predictably violates, prove the request is accepted, and compare the returned object against the exact supplied schema on the pinned build.

### 7. Bulk-copy bandwidth can hide production transfer-geometry skew

**Current class:** `PROMISING_FIRST_PARTY_CANDIDATE / NEEDS_GENERALIZATION`

A distributed model-loader investigation found that bulk memory-copy tests looked healthy while the real loader issued a very large number of much smaller copies and exposed substantial per-rank skew. Storage locality explained one part of load time but not the remaining production-copy difference.

The candidate lesson is: **benchmark the transfer-size and call-count geometry the loader actually uses; a bulk-copy number can falsify neither a many-small-copy bottleneck nor rank-specific overhead.**

Current public search found no exact canonical owner. The evidence is strong enough to retain, but a portable paired reproducer is still preferred before promotion.

## Recovered first-party fabric queue

A historical five-node/200G fabric campaign had a private candidate list that was easy to miss because most of the raw material lived outside the public Minefield repository. The ledger describes the following as measured campaign observations, while the later consolidation layer still requires sanitization/raw-artifact reconciliation before publication:

- cable/seating state misdiagnosed as an EEPROM/cable-identity problem;
- L2 MTU / PMTU black-hole behavior on the high-speed path;
- TCP jumbo/MSS failure while smaller/RDMA traffic could still look healthy;
- mixed distributed container/runtime images across ranks;
- wrong secondary HCA/interface selection;
- compatibility/out-of-band traffic escaping over the wrong default route;
- directional host-memory-to-NIC/DMA impairment that a simpler bulk check did not expose.

The per-host GID-index item from the same campaign is already public as [Trap 114](../traps/runtime/114-hard-coded-rdma-gid-index-not-portable.md), so it is excluded from this recovered queue rather than duplicated.

**Current class for the seven remaining items:** `HISTORICAL_FIRST_PARTY_MEASURED / PROMOTION_PACKET_REQUIRED`.

The public-safe summary is intentionally weaker than the private ledger's shorthand. Before any of these get a trap number, recover the relevant raw artifact, reconcile the historical `MEASURED` label with the later `REPRO_REQUIRED` bookkeeping, sanitize topology/host data, and search current public ownership again. The strongest promotion order is the network-path mechanisms (MTU/PMTU, mixed rank images, HCA selection, route selection) before the more hardware-specific directional-DMA observation.

## Nemotron/SM120 intake items recovered after the first audit

The Nemotron intake branch contains more than the two items originally surfaced in this PR. Routing after current-public ownership review:

- **GPU tenancy collision / a second process reappearing outside the expected service manager:** lifecycle/tenancy evidence. Keep as operational guidance unless a minimal general mechanism is isolated.
- **hardware FP4 capability versus the quant/backend actually selected by the runtime:** existing quant/backend-verification family; do not infer the execution kernel from the GPU capability or checkpoint label alone.
- **session/automation lifetime kills the serve and mimics engine failure:** [Trap 112](../traps/runtime/112-process-liveness-is-not-model-readiness.md) lifecycle/readiness family, not a new ID.
- **native MTP K=1 changes the loaded footprint enough to make KV allocation fail at one memory-utilization setting, while a higher bounded setting reaches READY:** strong additional evidence for [Trap 98](../traps/runtime/98-speculative-decode-default-max-seqs-oom-uma.md)'s central rule that a speculative configuration must be requalified for memory/readiness. It does not establish a universal utilization threshold.
- **DFlash/hybrid admission cliff below the displayed context headline:** retained as strong candidate #3 above because the observed WAIT-before-prefill mechanism is narrower than ordinary speculative OOM.

The same branch also cross-walked the latest DeepSeek V4 champion campaign against current Minefield. Nearly all of those 19 mechanisms already route to existing owners (12, 03/29/57, 26, 42, 47/60, 91, 112, 55/61, 54, 80/105, 11/111, 62/71/109 and version-pin doctrine). Do not manufacture duplicate traps from that campaign.

## Muse/Offlabel private-ledger reconciliation

A branch-level review of the earlier Muse candidate ledger found that most apparently-open items were already absorbed by PRs #30/#31 or existing canonical owners:

- forced named `tool_choice` ignored -> already recorded as an addendum to [Trap 78](../traps/tools/78-tool-choice-accepted-and-ignored.md);
- single-turn sequential-tool false negatives -> [Trap 42](../traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md) / harness guidance;
- speculative score parity != exact text identity -> [Trap 111](../traps/evaluation/111-greedy-spec-decode-medians-are-a-content-lottery.md);
- content-only stream consumer sees false blank -> [Trap 23](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md);
- missing generation config -> [Trap 21](../traps/versioning/21-no-generation-config-server-defaults-win.md);
- accepted but dead reasoning controls -> existing 07/77 family;
- actual-token context proof and retrieval-vs-synthesis -> existing context/evaluation doctrine or playbook material.

The `json_schema` acceptance/enforcement item remains the clearest not-yet-owned API-compatibility candidate from that ledger and is separated as candidate #6 above.

Older Offlabel-derived private candidates for quiet-compliance classifier blind spots, judge capability floors and probe rows contaminating task denominators remain reproduction/fixture work, not automatic new traps. The current public Offlabel cross-check does not silently promote them.

## Private bilateral research-share audit

A separate private mechanism/fact-card ingest branch was also recovered and reviewed. Its publication queue contains many potentially useful serving leads, including SM120 JIT/kernel compatibility, context/KV accounting, P2P/IOMMU, NVFP4 KV-cache paths, CPU-MoE/speculation interactions and quantization/export gotchas.

**No source-derived item from that private share is promoted in this PR.** The source is private and permission-limited, so Minefield must not copy its prose or present those cards as Blackwellboy evidence. The correct route is to use them as private research leads and either independently reproduce the mechanism or locate a public primary source before public promotion.

This is why the deep audit can find more useful work without inflating the public registry.

## Existing-owner extensions and playbook material

### HTTP health versus authenticated agent/session readiness

The first-party Desktop/session incident is already owned by [Trap 112](../traps/runtime/112-process-liveness-is-not-model-readiness.md): an HTTP listener or health response is not proof that the authenticated session/run/stream path used by the client is ready. No new ID.

### Forced capacity overrides do not create physical memory headroom

First-party capacity work provides another concrete example adjacent to Traps 13 and 98: overriding a calculated block count can bypass a calculator, not create physical memory. Useful evidence, but not a clean new owner in this pass.

### Residual memory accounting needs lifecycle attribution

A derived residual bucket can be numerically real without proving which subsystem owns it. Timeline measurements in first-party work moved most of an initially suspicious residual to pre-model/runtime baseline rather than the loader object first blamed. This belongs in measurement guidance unless a distinct reproducible failure mechanism emerges.

### Debug/correctness launch flags can define the throughput regime

A first-party CUDA-graph A/B showed a large performance change when an eager-mode launch flag disabled graph execution. The current routing is benchmark/configuration guidance: record graph/eager mode with results rather than treating the flag as incidental.

### Provider-bound reasoning configuration is the runtime fact

First-party agent work again showed that operator-facing reasoning settings can differ from what is actually sent after profile nesting/precedence. This remains in the existing reasoning/configuration family: capture the provider-bound request before labelling an A/B "thinking on" or "thinking off."

### Fail-closed is containment, not successful-call reliability

A guard that refuses to execute malformed native tool markup can make a bad turn safe. It cannot turn that turn into a pass. Report containment and successful-call rate separately.

## Kept private pending stronger reproduction

### Post-tool native markup event

An earlier post-tool failure was reconstructed and exact replay later ran clean repeatedly. The original event was not independently reproduced. It is retained privately as an observation, not promoted here.

### Long-session garbling after repaired tool history

A later long continuous session still contained two garbled turns despite no native-tool-markup leak and no fail-closed event. The owner layer remains unresolved. Exact bad-turn provider request/response reconstruction and replay are required before attributing this to the model, server, agent harness or desktop/session layer.

### Client timeout as a benchmark handicap

Historical BlackwellBench triage found long-context/multi-turn cases failing at the client timeout while the endpoint remained alive. The public promotion gate remains the obvious control: rerun the timed-out IDs with a deliberately generous explicit timeout and show that the score outcome changes. Until that is done, keep it a blocked evaluation candidate rather than a trap.

## Already promoted; do not duplicate

The wider private audit also confirmed that several earlier candidates were already promoted correctly:

- hard-coded RDMA GID portability -> Trap 114;
- Exit 137 causal overclaim -> Trap 115;
- post-load first-forward dtype failure -> Trap 116;
- distributed LoadReady / finish lifecycle -> Trap 112 addendum;
- DeepSeek late inline-system welding -> Trap 56, with broader role-contract coverage in Trap 113;
- Muse forced-named-tool behavior -> Trap 78 addendum;
- Muse DFlash exact-text non-identity -> Trap 111 corroboration.

## Result

`NEW_CANONICAL_TRAP_IDS_IN_THIS_PR=0`

The recovered first-party queue is no longer represented by one small intake file: the audit now includes the Keys/Hermes history work, Nemotron SM120 staging, the historical fabric queue, the benchmark-HUD routing failure, Muse leftovers, recent agent/bootstrap evidence and the older private Minefield consolidation branches.

Strongest next canonical-promotion targets, after their stated gates, are:

1. persisted tool-history metadata loss;
2. cold-JIT host OOM with resident weights;
3. practical admission cliff below displayed context/KV capacity;
4. benchmark endpoint-selector/data-plane divergence;
5. stale injected skill/profile truth overriding live runtime truth;
6. accepted JSON-schema request without demonstrated schema enforcement.

The historical fabric candidates should be handled as a separate sanitized promotion batch rather than mixed into those six.
