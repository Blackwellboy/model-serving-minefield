# Playbook: Agentic research integrity

Minefield documents **model-serving and measurement failures**. This playbook
covers a related class: failures of the **research stack** that investigates
those systems - agents, harnesses, scorers, evidence pipelines, and human
review.

It does **not** turn Minefield into a generic agent framework. It does not
validate private bounty findings as “true.” It helps detect known
evidence-integrity failure classes so a TARGET BUG and a RESEARCH-STACK BUG
stay distinct.

## Lifecycle

```
DISCOVERY → TRIAGE → REPRODUCTION → EVIDENCE PREFLIGHT
  → FALSIFICATION → ADJUDICATION → PROMOTION
```

| Stage | Purpose | Must not |
|-------|---------|----------|
| DISCOVERY | Collect symptoms and candidate mechanisms | Promote evidence |
| TRIAGE | Map to existing trap/check/mining owner | Allocate trap numbers |
| REPRODUCTION | Controlled repro with pinned identities | Rely on narrative alone |
| EVIDENCE PREFLIGHT | Run `checks/evidence_packet_preflight.py` | Treat UNKNOWN as PASS |
| FALSIFICATION | Alternative explanations + controls | Be anchored by proposer confidence |
| ADJUDICATION | Evidence status, claim boundary, disposition | Certify without raw evidence |
| PROMOTION | Numbering, registry, generated surfaces | Silently strengthen the claim |

## Roles (conceptual)

**SCOUT** - discovers symptoms/candidates; cannot promote evidence.

**REPRODUCER** - runs or reconstructs controlled reproduction; preserves raw
artifacts; pins identities (revision, model, engine, config, workspace).

**FALSIFIER** - attempts alternative explanations and negative controls;
should not receive proposer confidence/verdict when avoidable (see blind
review packet).

**ADJUDICATOR** - determines evidence status (existing Minefield vocabulary),
claim boundary, and disposition; must review **raw** evidence, not summary
alone.

**PUBLISHER** - numbering, generated surfaces, registry integrity, release;
does not silently strengthen claims.

One human may hold multiple roles. Solo contribution remains possible.

## Principle: no model certifies its own work

`NO_MODEL_CERTIFIES_ITS_OWN_WORK`

For **agent-driven** high-confidence or numbered promotion, require one of:

| Review state | Meaning |
|--------------|---------|
| `INDEPENDENT_REVIEW_PASS` | Separate reviewer inspected raw evidence |
| `INDEPENDENT_REVIEW_NOT_AVAILABLE` | Recorded; blocks agent high-confidence promotion without waiver |
| `INDEPENDENT_REVIEW_WAIVED_WITH_REASON` | Human waiver with explicit reason |
| `INDEPENDENT_REVIEW_NOT_REQUIRED_FOR_THIS_DISPOSITION` | e.g. HOLD, mining question, reject duplicate |

Solo **human** contributors may use
`INDEPENDENT_REVIEW_WAIVED_WITH_REASON` or
`INDEPENDENT_REVIEW_NOT_REQUIRED_FOR_THIS_DISPOSITION` rather than being
blocked from contributing.

## Evidence status (do not invent a parallel taxonomy)

Use the existing labels in
[`skills/model-serving-minefield/references/evidence-status.md`](../skills/model-serving-minefield/references/evidence-status.md):

- `reproduced here`
- `contributor-measured, conditions as reported`
- `reported by others`
- `measured here, raw not published`
- `under test`

Diagnosis levels remain in [`docs/DIAGNOSIS_CONTRACT.md`](../docs/DIAGNOSIS_CONTRACT.md).

Failure **causes** (transport vs harness vs model) are separate - see
[`docs/failure-cause-taxonomy.md`](../docs/failure-cause-taxonomy.md).

## Evidence Packet v1

Machine-readable packet: [`docs/evidence-packet.schema.json`](../docs/evidence-packet.schema.json).

Preflight (offline):

```bash
python3 checks/evidence_packet_preflight.py --packet path/to/packet.json
```

Terminal states: `PASS` | `HOLD` | `FAIL` | `UNKNOWN`.  
`UNKNOWN` is never collapsed into `PASS`.  
Missing artifact bytes → `ARTIFACT_HASH_UNVERIFIED`, not PASS.

## Blind falsification packet

```bash
python3 -m minefield blind-review --packet full.json --out blind.json
```

Strips proposer confidence/verdict, recommended trap numbers, final
disposition, and persuasive narrative. Retains hypothesis, identities, raw
artifact refs/hashes, execution facts, controls, expected disproof, unresolved
questions. Records `full_packet_sha256` and `blind_packet_sha256`.

This reduces one obvious source of reviewer contamination. It does **not**
mathematically guarantee independence.

## Promotion receipt

For future promotions (not retroactive for all traps):
[`docs/promotion-receipt.schema.json`](../docs/promotion-receipt.schema.json).

## Related executable surfaces

| Surface | Role |
|---------|------|
| `checks/evidence_packet_preflight.py` | Packet integrity |
| `checks/upstream_change_triage.py` | Offline change prioritisation |
| `checks/endpoint_readiness_hierarchy_probe.py` | Auth/readiness vs health |
| `checks/tests/test_check_contract.py` | Checks must be able to fail |
| Doctor / `minefield evidence-preflight` | Offline integration |

## Disposition without a trap number

A submission may become: existing-trap corroboration, extension, check,
mining question, unnumbered draft, upstream-tier item, good-practice note,
or rejected duplicate. **No trap number is promised.**

## What this playbook is not

- Authority to run live benchmarks or mutate fleet services
- A guarantee that bounty or security research is “validated”
- A second registry of numbered traps for agent roles
