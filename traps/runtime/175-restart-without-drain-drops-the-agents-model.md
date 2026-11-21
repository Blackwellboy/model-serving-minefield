# Trap 175: restarting the model server without draining active agents drops the session's backing model, and it looks like a network fault

**Found by Blackwellboy.**

**Status: measured here, raw not published.** A first-party service timeline,
request dump and post-fix stability runs; the raw evidence is not published.

**Symptom.** An agent is making useful progress, has already written or
tested files, then suddenly gets generic connection errors from its local
model provider. The container or worker around it still looks healthy, so the
error reads as a network fault, an out-of-memory kill or a model crash.

**Mechanism.** The serving process was deliberately replaced to apply a
configuration change while an agent session still depended on it. During the
restart window the endpoint disappears, active and follow-up requests fail,
and the framework's ordinary provider retries hide that this was planned
lifecycle churn. A healthy probe at the start of a task says nothing about
service continuity for the rest of it.

**Stacks and builds bitten.** A first-party local OpenAI-compatible model
service backing a long-lived autonomous coding session, 2026-09-15. The
serving process was restarted inside a container that stayed up. After drain
and lifecycle classification were added, 8 of 8 stability runs completed.

**The check.** During an active multi-turn agent task, record the serving
process ID and start time, endpoint availability and each request's outcome
across a controlled restart. Rule out out-of-memory, watchdog and GPU-reset
causes in the same window. Confirmed when the agent loses its provider during
the planned restart while the host and container stay healthy. Refuted when
the serving layer drains active work or keeps the endpoint available through
the change.

**The fix.** Drain or pause dependent agent work before replacing the serving
process. On a local-provider connection error, probe the endpoint's lifecycle
once and classify it as down or recovering instead of burning ordinary
retries or silently switching models. Keep session state so the task can
resume when the service returns.

**Found.** 2026-09-15, changing serving concurrency during a live autonomous
coding session.

**Attribution.** Blackwellboy.

**Related.** [112](112-process-liveness-is-not-model-readiness.md),
[53](53-config-edit-never-took-effect.md).
