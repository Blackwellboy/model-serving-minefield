# Implementation plan - Agentic Research Integrity v1

## Scope

Local implementation only on branch
`grok/agentic-research-integrity-20260807`.
`TRAP_COUNT_DELTA=0`. No public GitHub mutation.

## Deliverables

1. Playbooks: agentic research integrity lifecycle; repro loop.
2. Evidence Packet schema + 3 examples + `minefield.evidence_packet` preflight.
3. Failure-cause taxonomy doc reusing readiness/eval vocabulary.
4. Checks: `evidence_packet_preflight`, `upstream_change_triage` + MANIFEST.
5. Blind review + promotion receipt modules + CLI.
6. Contributor intake issue template + CONTRIBUTING pointer.
7. Agent-bundle reviewed-knowledge audit (integrity note / test).
8. Doctor/CLI offline integration (no live probe changes required).
9. Tests + full integrity battery.
10. Desktop consolidated report only.

## Non-goals

- Numbered traps
- Live inference / fleet mutation
- Online crawlers
- Competing evidence-status taxonomy
- Generic multi-agent runtime
