# Minefield eval-suite roadmap

The registry is useful because it names failure mechanisms. The next step is to make those mechanisms executable wherever the evidence allows it.

## Goal

Move toward a framework-neutral eval suite where every numbered trap has four explicit fields:

1. **Reproduction** — the smallest controlled setup that can make the trap appear.
2. **Expected symptom** — the observable failure signature, separated from the inferred mechanism.
3. **Detection logic** — the assertion that distinguishes this trap from adjacent failure classes.
4. **Regression check** — the negative control that must stay green once a fix lands.

This is not a promise that every trap can become an endpoint probe. Some entries require hardware, runtime source inspection, multi-host state, long soaks, or an agent trajectory. Those should still expose a machine-readable test contract even when Minefield cannot execute it automatically.

## Layers

The suite should stay framework-independent. Runtime or agent integrations are adapters, not the registry itself.

- **Lite preflight** — a tiny bounded set of high-value probes selected by model/runtime fingerprint.
- **Doctor** — deliberate read-only live testing with explicit coverage and request budgets.
- **Incident analysis** — post-failure analysis over sanitized traces, tool calls, logs and configuration; separate model, runtime, client and agent-orchestration causes.
- **Contribute** — generate a sanitized evidence packet with reproduction, expected symptom, detection logic, negative control and provenance for maintainer adjudication.

A reusable core API should converge on operations equivalent to `plan`, `run`, and `summarize`: select applicable probes, execute only the permitted ones, and return evidence-bounded verdicts. A clean result must always state what was not exercised.

## Machine-readable contract

A future per-trap manifest should be able to represent at least:

```text
trap_id
applicability
inputs
reproduction
expected_symptom
detection_assertions
negative_control
request_or_runtime_budget
required_capabilities
evidence_level
known_good_fingerprint
```

The manifest must not pretend that a test exists when the current project only has prose. `implemented`, `specified`, and `not-automatable-here` should remain distinguishable states.

## Pilot: agent/tool traps 139-140

Traps 139 and 140 are useful pilots because they require an agent-trajectory surface rather than another OpenAI-endpoint-only request.

### 139 — literal CLI intent drift

- Reproduction: same model/server/tools/user command, vary only assembled system guidance.
- Expected symptom: explicit command is replaced by invented command discovery/config inspection on the first action.
- Detection: first action differs from the literal safe executable supplied by the user without prior evidence it is unavailable.
- Regression: literal-command suite stays direct while a natural-language health request can still reason normally.

### 140 — semantic no-progress loop

- Reproduction: several exact-distinct tool calls in one semantic strategy family receive the same structural rejection with no task-state progress.
- Expected symptom: repeated tool preparation/calls while exact-signature guards remain silent.
- Detection: distinct exact hashes + repeated semantic/rejection class + no progress.
- Regression: repeated failed strategy is bounded while genuinely different progressive commands remain permitted.

## What this is not

- Not a leaderboard.
- Not a claim that one clean Doctor run covers the registry.
- Not a Hermes-specific test suite.
- Not a reason to auto-promote mined leads into numbered traps.

The registry remains the evidence authority. The eval suite is the executable layer that makes more of that evidence mechanically reusable.
