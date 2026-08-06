# Trap 80: a reasoning parser batches the stream, and every timing you derive from it is fiction

**Found by Blackwellboy.**

**Status: measured here, raw not published.** 2026-07-28, vLLM 0.25.1 with
`--reasoning-parser-plugin` (the `nano_v3` plugin shipped in an NVIDIA Nemotron
3 Nano NVFP4 checkpoint), on an NVIDIA GB10, aarch64, CUDA 13. The 36-row
matrix behind the counts is not published, so a stranger cannot check our rows.
The detection ratio in the check section settles it on their own lane in one
request, which is the cheaper route anyway.

**This one cost us a published number**, and the reversal is in the entry
rather than in a footnote, because that is the strongest argument for reading
it.

**Symptom.** Stream timings that cannot be true, on a lane that is otherwise
healthy. On a lane whose real decode rate is **60 tok/s**:

- a measured **decode rate of 1,812 tok/s**, thirty times the lane's physical
  ceiling
- a measured **TTFT of 5.5 s on a 1,000-token prompt whose entire request took
  6.4 s**
- across a 36-row matrix, **27 of 36 rows** carried fewer than half as many
  stream deltas as they had completion tokens; the count ranged from **0 to 214
  deltas for 384 tokens**

The give-away is that the numbers are not merely noisy, they are impossible: a
time-to-first-token that consumes most of a request whose total time is right.

**Mechanism.** With a reasoning-parser plugin loaded, the server does not emit
one delta per token. It accumulates and flushes in bursts, because the parser
cannot decide which channel a fragment belongs to (`content` versus
`reasoning_content`) until it has seen enough of it. Delta **arrival** times
therefore describe the parser's flush schedule, not token generation.

Everything derived from that is derived from the wrong clock: TTFT, inter-token
latency, and any decode rate computed as
`tokens / (t_last_delta - t_first_delta)`.

**Why this is a trap and not just a bug: the obvious client-side fix does not
work, and looks like it should.** Iterating an HTTP response line by line is a
well-known cause of exactly this symptom, and the standard cure is to read with
`read1()` so bytes surface as soon as they arrive. We applied it. **It changed
nothing**, and the suspect-row count did not move. That is the tell that the
batching is server-side, but an operator who applies the usual fix, sees the
shape of the numbers shift slightly, and re-measures gets the same fabricated
figures and now has a reason to believe them.

Non-streaming totals stay correct throughout, so the lane looks fine on every
check except the one you are making.

**What it invalidates.** Every TTFT, inter-token-latency and stream-derived
decode figure taken on such a lane. Concretely, in our own work: a
speculative-decoding arm published at **+12.6%** was re-measured with a
buffering-proof method and came back at **-32.2%**. The sign reversed. That was
not a rounding problem or a small-n problem; it was a measurement that never
described what it claimed to.

**Stacks and builds bitten.** vLLM 0.25.1 serving through a reasoning-parser
plugin, GB10 aarch64 CUDA 13. Expected on any lane serving through a reasoning
parser, and **not established** beyond the one plugin measured.

**The check.** Detection first, because it is one request:

```python
# healthy is close to 1:1
n_deltas_with_text / usage.completion_tokens
```

Ours ran as low as 0. A ratio well under 1 means the deltas are batched and
every timing you derive from them describes the flush schedule.

Then, if you need a decode rate on such a lane, **do not derive it from stream
timing at all.** Measure a prefill floor and subtract it from total wall clock:

```python
# per (prompt, depth) cell, once:
#   max_tokens=1, non-stream, median of 3 -> prefill_s
# then for each real request:
decode_tok_s = (completion_tokens - 1) / (total_s - prefill_s)
```

That depends on no stream property, only on two wall-clock measurements and the
token count the server reports. **Cross-check** it against raw median `total_s`
at a fixed `max_tokens`: with the prompt set and token budget held constant, a
ratio of totals is a speedup with no derivation involved. If the derived rate
and the total-time ratio disagree, trust neither and find out why.

**The fix.** There is no client-side fix, which is the point. Change what you
measure, not how you read the socket.

**What we have not established.** Stated because the scope is narrow:

- Whether this is specific to the plugin we measured or general to vLLM's
  reasoning-parser path. One plugin, one lane.
- Whether any server flag restores per-token flushing. Not searched for.
- Whether other stacks with reasoning parsers do the same. Untested. On Ollama
  we separately observed a different empty-delta behaviour driven by the token
  budget rather than by parser buffering, so the two should not be assumed to
  be the same phenomenon.

**Found.** 2026-07-28, while re-measuring a speculative-decoding result that
had already been published.

**Attribution.** Blackwellboy. Related:
[trap 41](41-static-batching-buys-power-not-throughput.md), the other case in
this registry where a throughput number described the harness rather than the
system.
