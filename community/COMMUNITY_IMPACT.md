# Community impact

Adoptions, contributor discoveries and independently verifiable outcomes.
Generated from `community/impact.json`. Do not hand-edit this file as authority.

| impact_id | date | type | person_or_project | evidence | source |
|---|---|---|---|---|---|
| `impact-20260731-issue18-zerollama-adoption` | 2026-07-31 | ADOPTION | @odilitime / zerollama | PUBLIC_PRIMARY | https://github.com/Blackwellboy/model-serving-minefield/issues/18 |
| `impact-20260801-issue19-unvalidated-config-surface` | 2026-08-01 | CONTRIBUTOR_DISCOVERY | @scottleimroth | PUBLIC_PRIMARY | https://github.com/Blackwellboy/model-serving-minefield/issues/19 |

## Records

### impact-20260731-issue18-zerollama-adoption

- **Type:** ADOPTION
- **Person/project:** @odilitime / zerollama
- **Summary:** zerollama doctor maps Minefield traps; public thanks issue closed as completed adoption signal.
- **Minefield role:** Trap catalog used by external doctor/tooling
- **Blackwellboy role:** Maintainer; closed issue after verification
- **Evidence:** PUBLIC_PRIMARY
- **Guardrail:** Do not invent user counts or saved-hours; cite the closed issue only.
- **Follow-up:** closed_completed
- **Last verified:** 2026-08-01

### impact-20260801-issue19-unvalidated-config-surface

- **Type:** CONTRIBUTOR_DISCOVERY
- **Person/project:** @scottleimroth
- **Summary:** Contributor measured that VLLM_FLASHINFER_MOE_BACKEND is logged unknown while vLLM 0.26 still starts healthy; real control is --moe-backend.
- **Minefield role:** Intake document mining/2026-08-01-issue-19-unvalidated-config-surface.md; trap number not yet assigned
- **Blackwellboy role:** Diagnostic help and registry framing (credited per reporter)
- **Evidence:** PUBLIC_PRIMARY
- **Guardrail:** MEASURED_ON_THIS_BUILD (vLLM 0.26 / GB10 report). NOT a general CUTLASS all-clear. Do not publish ~70 tok/s without n=1 and reasoning-token caveats.
- **Follow-up:** final_auto_with_variable_removed_control_pending_not_blocking
- **Last verified:** 2026-08-01

