# Playbook: Agentic research integrity

Minefield is about **serving failures and measurement integrity**. This playbook
covers a related class: failures of the **research stack** (agents, harnesses,
scorers, evidence packaging) that investigates those systems.

It is not a generic agent framework, bounty platform, or claim that private
security findings are “validated.” It keeps TARGET BUG and RESEARCH-STACK BUG
distinct.

## Lifecycle

```
DISCOVERY → TRIAGE → REPRODUCTION → EVIDENCE PREFLIGHT
  → FALSIFICATION → ADJUDICATION → PROMOTION
```

| Stage | Must not |
|-------|----------|
| DISCOVERY / TRIAGE | Promote evidence or allocate trap numbers |
| REPRODUCTION | Rely on narrative alone; leave identities unpinned |
| EVIDENCE PREFLIGHT | Treat `UNKNOWN` as `PASS` |
| FALSIFICATION | Be anchored by proposer confidence/verdict |
| ADJUDICATION | Certify without raw evidence |
| PROMOTION | Silently strengthen the claim |

## Roles (conceptual)

| Role | May | Must not |
|------|-----|----------|
| SCOUT | Discover candidates | Promote |
| REPRODUCER | Pin identities; preserve raw artifacts | Skip hashing |
| FALSIFIER | Run controls / alternatives | Need proposer confidence |
| ADJUDICATOR | Set evidence status + claim boundary (Minefield vocabulary) | Use summary only |
| PUBLISHER | Registry / generated surfaces under normal governance | Upgrade claims |

One human may hold multiple roles. Solo contribution remains possible via
explicit waiver or “not required for this disposition.”

## Principle

`NO_MODEL_CERTIFIES_ITS_OWN_WORK` for **agent-driven** high-confidence or
numbered promotion. Record one of:

- `INDEPENDENT_REVIEW_PASS`
- `INDEPENDENT_REVIEW_NOT_AVAILABLE` (blocks agent promotion without waiver)
- `INDEPENDENT_REVIEW_WAIVED_WITH_REASON` (reason required)
- `INDEPENDENT_REVIEW_NOT_REQUIRED_FOR_THIS_DISPOSITION`

## Existing vocabularies (do not replace)

| Concern | Source |
|---------|--------|
| Evidence status | `skills/.../evidence-status.md` |
| Diagnosis levels | `docs/DIAGNOSIS_CONTRACT.md` |
| Failure cause codes | `docs/failure-cause-taxonomy.md` |
| Readiness states | trap 112 + endpoint readiness probe |

Preflight terminal states `PASS`/`HOLD`/`FAIL`/`UNKNOWN` are **packet
validation** outcomes only, not evidence status.

## Commands

```bash
python3 checks/evidence_packet_preflight.py --packet packet.json
python3 -m minefield evidence-preflight --packet packet.json
python3 -m minefield blind-review --packet full.json --out blind.json
python3 -m minefield promotion-receipt --receipt receipt.json
python3 -m minefield upstream-triage --changes changed-paths.txt
```

Schema: `docs/evidence-packet.schema.json`.  
No trap number is promised for a contribution; dispositions include
corroboration, extension, check, mining, draft, upstream-tier, reject.
