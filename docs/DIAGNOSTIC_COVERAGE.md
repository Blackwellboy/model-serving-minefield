# Diagnostic coverage

The registry contains every documented canonical finding. The endpoint doctor
directly probes only the subset that can be checked safely and conclusively
through bounded requests. Static inspection, contextual log analysis, guided
experiments, and human/agent comparison cover additional traps without
pretending they were endpoint-tested.

Run `minefield coverage --json` for exact, generated counts. The modality
figures overlap and are not combined into one percentage.

A possible match is not a reproduced diagnosis. A contributor-measured finding
can still save hours when its conditions and confirmation check match; it
retains that evidence label. “Not documented” is not “safe,” and a clean
doctor result says nothing about traps it did not execute.

Per-trap requirements, clean capability, confirmation/refutation criteria, and
limitations are generated in `registry/diagnostic_coverage.json`.

