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

### 4. Bulk-copy bandwidth can hide production transfer-geometry skew

**Current class:** `PROMISING_FIRST_PARTY_CANDIDATE / NEEDS_GENERALIZATION`

A distributed model-loader investigation found that bulk memory-copy tests looked healthy while the real loader issued a very large number of much smaller copies and exposed substantial per-rank skew. Storage locality explained one part of load time but not the remaining production-copy difference.

The candidate lesson is: **benchmark the transfer-size and call-count geometry the loader actually uses; a bulk-copy number can falsify neither a many-small-copy bottleneck nor rank-specific overhead.**

Current public search found no exact canonical owner. The evidence is strong enough to retain, but a portable paired reproducer is still preferred before promotion.

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
- DeepSeek late inline-system welding -> Trap 56, with broader role-contract coverage in Trap 113.

## Result

`NEW_CANONICAL_TRAP_IDS_IN_THIS_PR=0`

The recovered first-party queue is no longer lost, but canonical publication remains a separate promotion step. The strongest next promotion targets are persisted tool-history metadata loss, cold-JIT host OOM with resident weights, and the practical admission cliff below the displayed context/KV capacity.
