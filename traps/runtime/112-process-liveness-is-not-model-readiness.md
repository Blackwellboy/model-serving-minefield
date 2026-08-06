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
