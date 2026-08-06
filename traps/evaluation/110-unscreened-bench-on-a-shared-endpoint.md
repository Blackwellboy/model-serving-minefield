# Trap 110: a single-stream benchmark on a shared endpoint measures your neighbours

**Found by Blackwellboy.**

**Status: measured here, raw not published.** The degraded and clean numbers
below are from our own lane on 2026-08-03 and the raw is not shipped; the
screening procedure is runnable by anyone against their own endpoint's
`/metrics`, which is what the entry is for.

**Symptom.** A "single-stream" decode benchmark returns 41 to 77 tok/s on a
lane whose clean single-stream range, measured the same day with the same
harness, is 167 to 302 tok/s. Or the same suite run twice returns numbers
that disagree by 3x with no configuration change. The numbers are stable
enough within a contaminated run to look like a real regression.

**Mechanism.** The endpoint is shared. Background clients (in our case,
local agents posting work to the same server) land prefills inside the
benchmark's timing window. On a speculative-decoding lane the effect is
larger than the intuitive "some contention": concurrent requests share
verify bandwidth, so per-request decode drops well below the true
single-stream rate (this lane's 4-stream arm runs roughly 105 tok/s per
request against 200 at true single-stream). A benchmark that does not check
for co-tenant traffic does not measure the serve configuration at all; it
measures the co-tenants, and it does so silently because the endpoint
answers normally either way.

The null result in
[trap 95](../runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md)
brackets this one from the other side: two servers on two GPUs of one host
did not perturb each other there. Sharing a host is not the hazard. Sharing
an **endpoint**, and therefore a batch scheduler, is.

**Stacks and builds bitten.** A vLLM-derived build serving
[Rarri/DeepSeek-V4-Flash-0731-NVFP4](https://huggingface.co/Rarri/DeepSeek-V4-Flash-0731-NVFP4)
with MTP speculative decoding, tensor parallel 2 on 2x RTX PRO 6000
Blackwell. Nothing in the mechanism is specific to that stack: any
continuous-batching server with background traffic will do this to an
unscreened benchmark.

**The check.** Screening is two reads of `/metrics`, and it is cheap enough
to run around every timed request:

1. Before each timed run, read the engine's running-request gauge
   (`num_requests_running` or your engine's equivalent) and do not start
   until it is zero.
2. After each timed run, read the request-finished counters. If any request
   other than yours finished inside the window, discard the run and repeat
   it. Count discards; if you are discarding often, the lane is not
   benchmarkable right now and the honest output is "contended", not a
   number.

Our clean suite passed 12 of 12 windows under this screen. The earlier
unscreened suite on the same lane and config is the 41 to 77 tok/s figure
above, and it was nearly published as a checkpoint comparison.

**The fix.** Screen every window, publish only screened numbers, and state
the screen next to the number. If you cannot screen (no metrics endpoint, no
authority to quiesce), say the endpoint was shared and treat the result as a
floor, not a measurement.

**Found.** 2026-08-03, when a checkpoint A/B produced numbers 3x apart and
the diff between the two runs turned out to be somebody else's traffic.

**Attribution.** Blackwellboy.

**Related.**
[Trap 54](54-run-order-and-warm-cache-artifacts.md) (order, cache and drift
confounds in sequential comparisons),
[trap 95](../runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md)
(the co-tenancy null this entry scopes),
[trap 111](111-greedy-spec-decode-medians-are-a-content-lottery.md)
(the variance that remains after screening).
