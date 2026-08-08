# Trap 112: process liveness is not authenticated model readiness

**Found by scottleimroth.**

**Status: contributor-measured, conditions as reported.** Conditions as reported in issue #21. Not
independently reproduced here as a first-party measurement campaign.

**Symptom.** Two complementary lies on the same box:

1. **False positive.** Container status remains Up, wrapper or process still
   present, and ordinary health surfaces may answer, but EngineCore has died
   after a CUDA device-side assert and completion requests fail.
2. **False negative.** Unauthenticated `/v1/models` returns HTTP 401.
   `curl -f` turns that valid response into a non-zero exit, and polling logic
   concludes the host or server is down while the service is alive.

**Mechanism.** Operators collapse several independent surfaces into one ready
boolean. Process presence, transport response, authentication interpretation,
model-list success, model identity, and actual generation are different claims.
HTTP 401 proves an HTTP server answered; it does not prove the host is down.
HTTP 200 on `/health` proves only that handler answered. Docker Up proves only
container state.

This is adjacent to [trap 53](53-config-edit-never-took-effect.md) (stale
process after a restart that reported success) but is not the same owner:
trap 53 is about restart or bind collision with a retained old process. Trap
112 is about readiness hierarchy and authentication misinterpretation under a
live or partially live stack.

**Stacks and builds bitten.** OpenAI-compatible serving behind a container
health surface, as reported. The class is general to any stack that equates
process presence or unauthenticated HTTP with model readiness.

**The check.** Do not treat container status, unauthenticated 401, or bare
`/health` alone as readiness. Prefer authenticated model list plus a bounded
generation. Offline adjudicator:
`checks/endpoint_readiness_hierarchy_probe.py`.

Required readiness hierarchy: transport response; authentication interpretation;
authenticated model-list response; expected served-model identity; minimal real
generation; required capability probe.

Machine-readable states: NO_RESPONSE, AUTH_REQUIRED, AUTH_FAILED, WRONG_MODEL,
MODEL_LIST_OK, WRAPPER_HEALTH_ONLY, GENERATION_FAILED, GENERATION_OK,
CAPABILITY_FAILED, CAPABILITY_OK, INCONCLUSIVE.

**The fix.** Separate polling outcomes: 401 is auth-required or alive, not down.
Require generation or capability before declaring ready.

**Found.** Issue #21, reported by scottleimroth.

**Attribution.** Found and reported by @scottleimroth.

## Addendum 2026-08-08: readiness is a ladder, not a single green light

**Status: contributor-measured, conditions as reported** (distributed
multi-rank serving bring-up; sanitized). Extends the same owner: do not
collapse independent surfaces into one "ready" boolean.

The original entry separates process/wrapper health from model generation.
The same discipline applies **up and down the distributed lifecycle**:

| Green surface | Does **not** prove |
|---------------|--------------------|
| Protocol / CPU suite / synthetic rank checks | Real weights resident on device |
| Rank load / "loaded ok" / LoadReady-style control signals | First forward works on the loaded representation |
| First forward step | Multi-token generation completes |
| Generation output and throughput metrics printed | Clean multi-rank teardown and process exit 0 |

Concrete class observations (sanitized multi-rank campaign):

1. **Ready before resource.** A control-plane ready signal can fire (or
   re-fire) before the load it claims has completed; a suite that does not
   dwell in production phase duration can miss that re-entrancy.
2. **Metrics before lifecycle completion.** A run can emit accepted token
   counts and decode metrics, then hang in coordinator `finish` while workers
   return to an idle wait — so "generation succeeded" and "process exited
   cleanly" are different claims.
3. **Fix shape.** Sequencing load-before-ready / one-shot ready, and explicit
   finish acknowledgement between ranks, clear those classes without making
   HTTP health sufficient.

**Mutation warning.** Do not promote NCCL green, load green, or token metrics
alone into "serving ready" or "qualification complete" without the next
ladder rung you actually need (forward, generate, clean exit).

**Related.** [114](114-hardcoded-rdma-gid-index-is-not-portable.md) (lower
transport gate), [115](../evaluation/115-exit-137-is-not-oom-killer-proof.md)
(do not invent causes), [16](../evaluation/16-finish-reason-is-not-a-failure-signal.md)
(field misread).
