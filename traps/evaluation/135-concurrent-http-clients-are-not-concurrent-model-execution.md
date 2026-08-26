# Trap 135: concurrent HTTP clients are not concurrent model execution

**Found by Blackwellboy.**

**Status: measured here, raw not published.** First-party concurrency ladder on
a portable split-serving OpenAI twin (TCP and Flash arms). Hostnames, addresses,
and private logs stay private. The check below is the stranger-reproducible
half: compare completed-work metrics across client concurrency levels.

**Symptom.** A serving benchmark launches C1 / C2 / C4 concurrent HTTP
requests. The server accepts all of them. The harness reports "concurrency 4."
But batch wall scales approximately with the number of clients, aggregate
completed tok/s stays roughly flat, and generations are effectively serialized.
The operator then reports "the model handles four concurrent generations" or
compares two servers as though client concurrency equals execution concurrency.

**Mechanism.** Distinguish four different quantities:

1. **HTTP / client concurrency** - simultaneous sockets or in-flight requests,
2. **queued request concurrency** - accepted but waiting work,
3. **active model sequences** - sequences the engine believes are live,
4. **simultaneous model execution** - work actually progressing together.

A front end may accept N requests while a downstream lock, worker, single-flight
queue, slot count, or execution policy serializes the actual model work.
Therefore a client-side concurrency setting or N simultaneous sockets is not
proof that the model ran N sequences concurrently.

**Measured evidence (sanitized).** On one portable split-serving adapter with a
synchronous generate lock, a ~4K tokenizer-exact fixture, three matched reps,
zero request failures:

| Arm | C | batch wall (median) | aggregate tok/s (median) |
|---|---:|---:|---:|
| TCP | 1 | 2.192 s | 14.60 |
| TCP | 2 | 4.053 s | 15.79 |
| TCP | 4 | 7.742 s | 16.53 |
| Flash | 1 | 2.021 s | 15.84 |
| Flash | 2 | 4.729 s | 13.53 |
| Flash | 4 | 8.692 s | 14.73 |

C doubles roughly doubled finished-batch wall while aggregate completed
throughput stayed broadly flat. C8 was skipped once C4 already showed
saturation of finished-batch time. The measured adapter serialized generation
behind one lock; the public lesson is the measurement identity, not that lock
as a universal design verdict.

**Stacks and builds bitten.** Any OpenAI-compatible (or similar) serving front
end that accepts concurrent HTTP while a single worker, mutex, single-flight
queue, or `n_parallel`/`max_num_seqs`-style slot policy serializes generates.
Engine- and model-independent at the measurement layer. Not restricted to any
named serving stack; Related neighbours are contrasts, not scope limits.

**The check.** Require evidence from **completed work**, not request admission
alone. At minimum compare C1 vs C2 vs C4 and record:

- batch wall (time to finished batch),
- aggregate completed output tokens,
- aggregate completed tok/s,
- requests/sec,
- per-request latency,
- active sequences / running requests if the server exposes them,
- queue wait if available,
- scheduler / slot / lock state where inspectable.

Strong serialization signature:

- C doubles,
- batch wall approaches ~2x,
- aggregate throughput remains approximately flat,
- active model execution does not materially increase.

Optional discriminator: in a safe test build, instrument or temporarily remove
the serialization gate and show throughput / execution concurrency change.
Do not require private implementation knowledge for the basic check.

Offline metadata helper (no endpoint contact):
[`checks/concurrency_execution_proof_preflight.py`](../../checks/concurrency_execution_proof_preflight.py).

**The fix.** Benchmark and report at least two quantities separately:

1. client / request concurrency,
2. actual execution concurrency / completed-work throughput.

Do not label C4 as "4-way model concurrency" unless execution evidence supports
it. Prefer publishing **time-to-finished-batch**, **aggregate completed tok/s**,
and **active sequence count / actual worker concurrency** beside per-request
tok/s.

**Claim boundary.**

- May claim: concurrent clients do not prove concurrent model execution.
- Must **not** claim from this example alone: that all synchronous locks are
  bad; that a particular engine cannot run concurrently in other
  configurations; that throughput must scale linearly with concurrency; or that
  flat aggregate throughput always means a lock (scheduler, model, or hardware
  saturation can produce a similar shape). The trap is about measurement
  identity first.

**If you miss it.** You publish "C4 concurrency" wins that never executed four
generations together, or you compare two stacks as though client concurrency
were the same independent variable on both sides.

**Related.**
[Trap 46](../versioning/46-stale-build-missing-arch-kernel.md) (follow-on
llama.cpp `--parallel` / slot serialization; different primary mechanism),
[trap 110](110-unscreened-bench-on-a-shared-endpoint.md) (true shared-endpoint
contention; different symptom),
[trap 41](../runtime/41-static-batching-buys-power-not-throughput.md)
(utilization / static-batch vs completed work; related discipline, different
identity),
[trap 128](../runtime/128-admission-flag-never-read-decode-starvation.md)
(prefill/decode admission bug; different mechanism). None owns the general
client-concurrency-versus-execution-concurrency measurement identity.

**Found.** 2026-08-25, portable split-serving concurrency ladder with completed-
work metrics.

**Attribution.** Blackwellboy.
