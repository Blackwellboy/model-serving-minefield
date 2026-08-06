# Trap 31: a leftover oracle re-ranker turns a failing retrieval eval into a passing one, and the inflated number outlives the script that made it

**Found by Blackwellboy.**

**Status: measured here, raw not published.** One harness, one frozen
100-item gold suite with 65 content-scored items, one committed engine,
single deterministic run, no RNG; numbers are scoped to this corpus. The
gold suite and the metrics both live in a private return and the corpus
cannot be published, so no number here is checkable by a reader, and this
entry ships no runnable check either. Read it as a pattern to look for in
your own harness, not as a verified measurement.

## The trap

While debugging a retrieval evaluation, someone drops a quick repair
script into a temp directory. To "check whether the expected document is
even reachable," the script subtracts a huge constant from a candidate
score whenever the candidate id appears in the expected-answer set, or
looks candidates up directly by the expected answer file name stem. The
script is throwaway. The metric it prints is not: it lands in a metrics
JSON with no runner attached, gets quoted in status docs, and later
nobody can say which engine produced it. Meanwhile the honest engine
still fails the gate.

The structure is the trap; the numbers below only calibrate its size on
one corpus. Arms B and C are reconstructed mechanisms: the original
leftover script was never recovered, so both inflation paths were rebuilt
from the contamination signatures in the historical metrics and run in
one labelled harness next to the honest arm. On this corpus, same
engine, same suite, same run:

* honest top-3: 0.6615 (43/65), top-1 0.5077
* expected-id boost variant (reconstructed): top-3 0.8615 (56/65). The
  ceiling equals the fraction of items whose expected document entered
  the candidate pool at all, because the boost can only promote what was
  already retrieved.
* answer-derived name-stem variant (reconstructed): top-3 1.0000
  (65/65), top-1 0.9846. This one saturates the suite, because the stem
  is looked up from the answer key itself; the query never mattered.

So two different leftover mechanisms inflate the same honest 0.66 to
0.86 or 1.00 on this corpus. Any historical score in the high band is
unquotable unless the exact runner is recovered and shown clean.

## What you see

* An eval score in a metrics file that nobody can regenerate, sitting
  well above what the current committed engine produces.
* Two or more "same" metrics that differ by tens of points across
  sessions with no engine change in the log.
* A diagnostic-only field (a score with a note like "not for gate") that
  later gets quoted as if it were the gate number.
* Fingerprint of an expected-id re-ranker: top-1 equals top-3 exactly in
  that arm, because promotion-to-front boosting puts the expected
  document at rank 1 whenever it is present at all; organic ranking
  almost never does this.
* Fingerprint of an answer-derived path mechanism: the metric saturates
  at exactly 1.0 (or its candidate-pool ceiling) on a suite the honest
  engine fails, because the lookup key comes from the answer, not the
  query.

## The check that catches it (copyable no-oracle negative control)

Run this in the same process as the eval, every run, and fail the run if
it fails:

1. Take one gold item. Retrieve with the engine as-is; record the top
   ids.
2. Make a copy of the item with the expected-answer fields injected
   under obvious names (for example "__expected_document_id", and
   "__expected_path" set to a sentinel like "SHOULD_NOT_HELP"). Retrieve
   again. The top ids must be identical. If injected answer metadata
   changes the ranking, the engine reads answer fields.
3. Grep the ranking source (everything above the test itself) for boost
   patterns keyed on expected ids or answer paths, for example: "if
   doc_id in expected_ids", "score -= 1000", or candidate lookup by the
   expected file name stem. Any match fails.
4. Record the pass/fail and the engine source hash next to the metric. A
   number without an attached engine hash and a passing control is a
   claim, not a measurement.

Also report, per run: candidate-pool hit rate for expected documents
(the expected-id boost ceiling), and whether any ranking feature is
derived from the answer key rather than the query.

## Fix

* Never let a diagnostic oracle write to the same metrics namespace as
  the honest eval. If you must measure an oracle, run all arms in one
  harness in one run and label every arm.
* Delete or quarantine temp-directory eval scripts the moment the
  session ends; their outputs should carry the script hash or be treated
  as unquotable.
* One before/after number fused from two different mechanisms is
  worthless; report arms separately with n and the pass counts.

**Found.** 2026-07-27, while auditing historical retrieval scores that
the committed engine could not regenerate; engine and harness hashes
recorded alongside the raw metrics in the private return, single run,
deterministic.

**Attribution.** Blackwellboy. Related:
[trap 05](05-scorer-normalization-verdict-flip.md) (the scorer, not the
model, decides the verdict) and
[trap 16](16-finish-reason-is-not-a-failure-signal.md) (metrics that
mean something other than what they are quoted as).
