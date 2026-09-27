# Diagnostic coverage

The registry contains every documented canonical finding. The endpoint doctor
directly probes only the subset that can be checked safely and conclusively
through bounded requests. Static inspection, contextual log analysis, guided
experiments, and human/agent comparison cover additional traps without
pretending they were endpoint-tested.

The offline checks behind `minefield scan` (and the MCP `scan_files` tool) are
counted under the `static_config` modality and recorded per trap with the
module that implements them:

- `minefield.static_inspector`: launch commands, compose files, env files
- `minefield.template_inspector`: sandboxed chat-template renders
- `minefield.model_inspector`: `config.json`, quant config, cache refs, hard links
- `minefield.results_inspector`: per-item eval/benchmark results
- `minefield.log_inspector` (the `log_scan` modality): concrete failure lines

`any_automated_check` in the summary counts traps with at least one of these or
an endpoint probe.

Run `minefield coverage --json` for exact, generated counts. The modality
figures overlap and are not combined into one percentage.

A possible match is not a reproduced diagnosis. A contributor-measured finding
can still save hours when its conditions and confirmation check match; it
retains that evidence label. “Not documented” is not “safe,” and a clean
doctor result says nothing about traps it did not execute.

Per-trap requirements, clean capability, confirmation/refutation criteria, and
limitations are generated in `registry/diagnostic_coverage.json`.
