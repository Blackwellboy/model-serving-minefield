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

## Prove the implementation path ran

An agent-written `PASS`, a benchmark table, and a clean reference result do not
prove that the proposed implementation was built or called. Before accepting a
claim about a new kernel, backend, transport, or optimization, require all of:

1. **Build proof** - the build graph and resulting artifact name the target.
2. **Import/load proof** - the test loads that artifact and fails closed if it
   is absent; fallback is not a passing outcome.
3. **Call proof** - instrumentation or an equivalent discriminator shows the
   target function ran for the measured cases.
4. **Output proof** - target output is compared with an independent reference
   under a preregistered tolerance.
5. **Negative control** - disabling, renaming, or deliberately breaking the
   target makes the test fail. If the same `PASS` survives, the test did not
   establish target execution.
6. **Timing identity** - the timed region belongs to the target call, not setup,
   reference computation, fallback, or a different function.

Adjudicate from artifacts and executable controls, not the implementer's prose
verdict. A measured reference-only path can validate the oracle, but it cannot
validate or benchmark an implementation it never invoked.

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


## LLM-judge base rates: a stress test, a classifier and production history are different estimands

A contributor audit in [issue #155](https://github.com/Blackwellboy/model-serving-minefield/issues/155) produced three superficially comparable rates for unrequested agent actions: 71% in an intentionally impossible stress probe, 3.9% from a small-model judge over production history, and 0.08% after every flag was re-read plus an orthogonal operator-objection search.

The gap was not model drift. The three instruments were answering different questions, and the cheap judge also produced structural false positives: empty final replies, interrupted turns, compaction/system notes, scheduled-job sentinels, and batches where it repeated the same rationale without reading the row. It also missed real incidents when the action and the user's objection occurred in different turns.

For agent-history measurement:

- label a stress-test rate as a **stress rate**, never a production base rate;
- hand-review every positive from a cheap judge before publishing a prevalence number;
- explicitly bucket interrupted, empty-final, compaction and sentinel turns rather than forcing them into behavioral labels;
- treat long runs of identical judge rationales as an instrument failure;
- add an orthogonal detector that spans turns, such as operator corrections/objections;
- sample judge-negative rows too, so a clean positive review does not hide false negatives.

An LLM judge is evidence-producing code. Its labels are not ground truth merely because they are structured.

### A model-run code audit: about one finding in ten survived, and the severity label did not predict which

Measured here, raw not published (2026-11-08). A local DeepSeek-V4.1-Flash
EXL3 build was given the host-side Rust of an open-source inference engine,
about 47,000 lines in 60 numbered chunks of roughly 1,200 lines, and asked for
concrete defects as JSON. It returned 181 findings (13 high, 97 medium, 71
low). Every high and medium finding was checked against the source by reading
the code around the cited line and its callers:

| Verdict | High | Medium |
|---|---|---|
| confirmed, with a reachable trigger | 2 | 8 |
| plausible, needs runtime evidence | 1 | 3 |
| real but minor or unreachable (test or mock code, absurd config values, comment mismatches) | 5 | 39 |
| rejected (guarded earlier, misread, or impossible) | 5 | 47 |

So 10 of 110 held up, and "high" was right 2 times in 13. The most serious real
defect, a client request that ends the server process, was labelled medium.
The rejections were mostly the same few shapes: a bounds or overflow claim that
an earlier validation, filter or invariant already rules out; a trigger that
needs a config value the real model or file can never have; mock and test
harness code reported as if it shipped; and a few outputs that contradicted
themselves inside one finding. It did independently rediscover two defects
already found by hand, which is the case for running it at all.

**The checker made the same kind of mistake.** An eleventh finding, confirmed
by a second-pass agent, rested on a compression ratio of 128. The model's real ratios
are 1 and 2, and at those values the defect cannot occur. A spot check against
the model's own constants caught it before anything was filed, and the table
counts it as unreachable. Verify the
verification when it supplies a number.

**The reasoning budget decided whether there was an answer at all.** At medium
reasoning effort with a 24,000-token cap and chunks of about 2,200 lines, 28 of
33 chunks spent the whole budget reasoning and returned no content
(`finish_reason: length`); see
[trap 12](../traps/evaluation/12-empty-content-at-token-ceiling.md). At low
effort, a 40,000-token cap and smaller chunks, 51 of 60 answered. Chunk size
changed at the same time, so this does not isolate effort.

For a model-run audit:

- treat every finding as a lead until someone reads the code at the cited
  line and the path that reaches it;
- check reachability before severity: who can trigger it, a client, an operator
  flag, the model file, or nothing;
- do not rank or triage by the model's severity label;
- bucket test, mock and comment findings separately rather than letting them
  pad the count;
- check any number a checker supplies against the code's own constants;
- report the yield with the count checked, not the count found.
