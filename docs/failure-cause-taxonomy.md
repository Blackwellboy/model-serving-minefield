# Failure-cause taxonomy (research / measurement integrity)

This document **names** failure-cause classes used when attributing an
experiment outcome. It is **not** a second evidence-status taxonomy.

Evidence status for published traps remains the vocabulary in
[`skills/model-serving-minefield/references/evidence-status.md`](../skills/model-serving-minefield/references/evidence-status.md)
(`reproduced here`, `contributor-measured, conditions as reported`, …).

Diagnosis levels remain those in [`docs/DIAGNOSIS_CONTRACT.md`](DIAGNOSIS_CONTRACT.md).

Readiness states for live endpoints remain those owned by trap
[112](../traps/runtime/112-process-liveness-is-not-model-readiness.md) and
[`checks/endpoint_readiness_hierarchy_probe.py`](../checks/endpoint_readiness_hierarchy_probe.py)
(`AUTH_REQUIRED`, `AUTH_FAILED`, `WRONG_MODEL`, `WRAPPER_HEALTH_ONLY`, …).

## Required invariant

**No infrastructure or harness failure may be silently classified as a target
negative.**

`UNKNOWN_UNADJUDICATED` is distinct from a genuine negative finding on the
unit under test.

## Canonical cause codes (v1)

Used by Evidence Packet `execution.failure_cause` and related tools.

| Code | Meaning | Target-negative? |
|------|---------|------------------|
| `NONE` | Completed without a classified failure (success path or non-failure disposition). | n/a |
| `MODEL_REFUSAL` | Model refused the request under policy/safety. | possible target |
| `MODEL_INVALID_OUTPUT` | Model produced output that is well-formed transport but invalid for the claim. | possible target |
| `PARSER_REJECTED` | Parser/tool parser rejected model or template output. | possible target or stack |
| `SERVER_ERROR` | Serving stack returned 5xx or internal error attributable to the server. | stack, not model score |
| `TRANSPORT_ERROR` | Network/TLS/connection failure before a usable application response. | infrastructure |
| `CLIENT_TIMEOUT` | Client-side timeout; target may still have been healthy. | infrastructure / harness |
| `HARNESS_ERROR` | Scorer, driver, fixture, or experiment harness defect. | harness, not target |
| `TOOL_EXECUTION_ERROR` | Tool/runtime used by the research stack failed (not the served model). | research stack |
| `AUTH_REQUIRED` | Authenticated surface required credentials (from trap 112 vocabulary). | readiness, not model quality |
| `AUTH_FAILED` | Credentials presented and rejected. | readiness |
| `WRONG_MODEL_IDENTITY` | Served or reported model id ≠ claimed identity. | identity / config |
| `WRONG_TARGET_REVISION` | Experiment did not pin or match the claimed revision. | reproducibility |
| `ENVIRONMENT_CONTAMINATION` | Shared workspace, cache, env, or prior-run state polluted independence. | research stack |
| `UNKNOWN_UNADJUDICATED` | Outcome observed but cause not yet classified. **Not** a negative finding. | none yet |

## Mapping notes

- HTTP 200 / container Up / `/health` alone never upgrades a cause to a model
  capability claim (trap 112; doctor CLEAN contract).
- Harness scorer defects belong under `HARNESS_ERROR` (see evaluation traps
  such as 05, 16, 37, 42), not under model invalid output, unless a direct
  probe separates them.
- Moving branch names such as `main` without a commit SHA are not exact
  target revisions; treat as `WRONG_TARGET_REVISION` when a claim requires
  pin, or refuse promotion.

## Extension policy

Add a code only when an existing trap/check owner does not already name the
class and when Evidence Packet preflight needs a machine-readable value.
Do not invent trap numbers from a new cause code.
