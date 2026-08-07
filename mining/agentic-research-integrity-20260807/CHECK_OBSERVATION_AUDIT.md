# Check observation / empty-set audit (2026-08-07)

Invariant:

> A check must not PASS when it observed zero relevant objects unless the
> check explicitly defines zero objects as the valid test condition.

## Existing contract (already strong)

`checks/tests/test_check_contract.py` requires every check to declare:

- `NEGATIVE_CONTROLS` - must not return exit 0
- `EMPTY_SET_CONTROL` - must not return exit 0

Exit **3** = inspected nothing (NOT a pass). Documented in CONTRIBUTING and
checks/README.

## Per-check snapshot (main @ 600b7472 + this branch)

| Check | Empty-set / zero-obs defence | Migration need |
|-------|------------------------------|----------------|
| preflight_template.py | Exit 3 NO_RENDER_PATH | none |
| dequant_fidelity.py | Exit 3 zero tensors | none |
| tool_args_dialect_probe.py | Controls + sentinel | none |
| reasoning_budget_probe.py | Controls | none |
| cache_hit_probe.py | Inconclusive not finding | none |
| latency_reconciliation.py | Declines bad server totals | none |
| tokenized_length_assert.py | Controls | none |
| hidden_state_align.py | Controls | none |
| util_vs_power_tell.sh | Exit 3 N/A power | sidecar controls |
| vllm_environ_registration_probe.py | Controls | none |
| endpoint_readiness_hierarchy_probe.py | Empty → INCONCLUSIVE/3 | none |
| **evidence_packet_preflight.py** (new) | Empty packet → not PASS; observed_count | n/a |
| **upstream_change_triage.py** (new) | Empty list → exit 3 | n/a |

## Optional field `observed_count`

- Required on Evidence Packet `execution.observed_count`.
- Preflight report includes `observed_count`.
- Historical checks **not** mass-migrated; contract already enforces empty-set.
- Future migration: emit `observed_count` in JSON reports where natural.

## Cannot use contract

- Pure documentation playbooks
- Human-only manual procedures without executable surface

## Future migration count

`EXISTING_CHECKS_REQUIRING_FUTURE_MIGRATION` for optional JSON `observed_count`
field: **11** historical checks (all already have EMPTY_SET_CONTROL).
