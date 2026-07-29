# Methodology note: false-healthy failures inside the tooling built to detect false-healthy

**Status: METHODOLOGY NOTE, not a trap.** Written 2026-07-29 from defects in
the `dsv4-long-soak` harness of 2026-07-28, and from the pattern recurring
across several unrelated sessions on this fleet the same day.

## Why this is a mining note and not a trap entry

A trap is something in somebody else's serving stack that will bite them. Every
defect below is **in our own harness**, not in vLLM, not in a checkpoint, not in
a driver. Nobody can hit these by running a model; they can only hit them by
writing measurement code the way we did.

Filing them under `traps/` would be a category error and would dilute a
directory whose entries are claims about serving stacks. But they are not
disposable either: the same failure *shape* has now produced a false CLEAN, a
false PROBLEM, a green watchdog over a blocked service, and - below - a guard
that checked nothing while reporting success. It is a recurring class in the
measurement layer, and the measurement layer is what every entry in the registry
ultimately rests on.

So: methodology, kept, and pointed at from the entries whose credibility depends
on it.

## The class

**A check that cannot fail is indistinguishable from a check that passes.**

Every instance has the same shape. Something is built to detect a bad state. It
is never verified against a bad state. It then reports the good state forever,
including when the bad state arrives.

## The six defects, and which two are the class

From one 2,400-request soak harness:

1. **Delta counted as token.** One SSE delta carries 2.2-3.5 tokens under MTP
   K=3. Reporting delta counts as "reasoning tokens" would have been wrong by
   ~3x. *Caught in smoke by cross-checking against `usage`.*
2. **Garble scanner false positive** on ordinary code indentation. The first fix
   passed a unit test and still failed live - the lookahead matched a later
   non-space on the same line rather than inside the repeated unit. *A unit test
   that agreed with a broken fix.*
3. **Spurious close-marker at position 0** on every non-thinking turn,
   conflating "no reasoning emitted" with "reasoning closed immediately".
4. **Negative time-to-first-token**, 9 values of 2,400, from `time.time()` under
   an actively-syncing NTP clock. Magnitude up to -0.8 s against a p50 of
   0.41 s, i.e. the clock step exceeded the signal.
5. **A memory sampler that dropped failed samples silently.** It recorded a node
   only when the reply parsed; a truncated SSH reply vanished with no trace. The
   burn detector took `min(available)` across *recorded* nodes, so losing a node
   silently degraded it to single-node coverage **while still reporting
   healthy**.
6. **A readiness loop whose memory guard evaluated empty strings.** Nested
   quoting through `wsl -> ssh -> bash -lc` broke the `awk` that produced the
   numbers, so the guard compared empty against its threshold and passed. It
   "checked" memory 30 times, on a node that had been swap-killed earlier the
   same day, and checked nothing.

**5 and 6 are the class.** 1-4 are ordinary bugs, caught by ordinary means. 5
and 6 are guards that reported success while inspecting nothing - the same shape
as a watchdog returning 200 for a service that cannot accept work.

## Why this class specifically recurs

It survives review because **the healthy output of a broken detector is
identical to the healthy output of a working one.** Nothing looks wrong. There
is no error, no exception, no alert. The only way to tell them apart is to
present a bad state and require the detector to notice.

It is also cheap to introduce and expensive to spot: defect 6 is a quoting bug
three shells deep, and its symptom was thirty consecutive lines of reassuring
output.

## The discipline that catches it

**Verify capability, not status.** A detector is not commissioned until it has
been shown failing.

Concretely, and all of these were applied in the same session:

- **Mutation-test every scanner.** Plant one canary per class, require the
  scanner to fire, remove the canary, require it to go quiet, and check the
  **exit codes**, not just the printed verdict. Our sanitizer was run clean ->
  canary -> clean with exits 0/1/0. Before that test it had two false-positive
  sources; after it, zero.
- **Give every null a positive control.** A cross-model null in this session
  (13/13 clean) was worthless until the same harness was pointed at a lane where
  the failure was known to occur and reported it. That control also revealed
  the scorer was too lenient and would have scored a real failure as clean -
  found only because the control was run.
- **Make detectors prove they can read non-zero.** A foreign-inference counter
  read 0 across 39 windows. That was only meaningful once window 40 read
  **exactly 2** against exactly 2 injected requests.
- **Record failures explicitly; never drop them.** A sample that could not be
  taken must be stored as a failure with a reason, not omitted. The replacement
  sampler recorded 5 failures in 291 probes - all SSH timeouts to one node -
  which the original design would have shown as 286 healthy samples.
- **Assert the assumption your derivation rests on.** Deriving per-request
  acceptance from decode steps is only valid while `tokens_per_step <= K+1`;
  assert it every request, because a reasoning parser that batches deltas
  breaks it silently (see
  [trap 80](../traps/runtime/80-reasoning-parser-batches-sse-deltas.md)).
- **Never let a guard evaluate an empty variable as a pass.** Defect 6 would
  have been caught by failing closed on an unparseable reading.

## Standing rule this argues for

**No harness result is reportable until the harness has been shown failing on a
known-bad input.** Applied to scanners, guards, detectors, scorers and health
checks alike. The cost is one deliberate broken run per instrument. The
alternative is what this class keeps producing: confident green output from
something that stopped looking.

**Attribution.** Blackwellboy.
