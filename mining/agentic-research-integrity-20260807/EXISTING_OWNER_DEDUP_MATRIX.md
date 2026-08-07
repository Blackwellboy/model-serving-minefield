# Existing owner dedup matrix - Agentic Research Integrity 2026-08-07

Base: `origin/main` @ `600b74728ce03732f6bd1983c0aa820175d9f7e7`  
Trap range: **1-113** (count 113). No numbers allocated in this campaign.

| # | Idea | Existing owner | Classification |
|---|------|----------------|----------------|
| 1 | Failure-cause classification | Evaluation traps (05, 16, 37, 42); readiness states trap 112; no single shared enum before this campaign | **EXTEND via docs/failure-cause-taxonomy.md** (vocabulary only; not evidence_status) |
| 2 | Transport/client timeout vs target failure | Trap 16 (finish_reason), 72 (media fetch 5xx), harness vs model distinction in evaluation | **EXISTING_TRAP_OWNER** (+ taxonomy codes `TRANSPORT_ERROR`, `CLIENT_TIMEOUT`) |
| 3 | Authenticated readiness vs HTTP/container health | Trap **112**; `checks/endpoint_readiness_hierarchy_probe.py`; doctor CLEAN contract | **EXISTING_TRAP_OWNER** / **EXISTING_CHECK_OWNER** |
| 4 | Wrong model identity | Trap 112 `WRONG_MODEL`; doctor model selection | **EXISTING_TRAP_OWNER** |
| 5 | Wrong target/repository revision | Inline-system evidence requires 40-char SHA; doctor `--hf-revision` warns `main` mutable | **EXTEND_EXISTING_CHECK** (Evidence Packet preflight rejects moving `main`) |
| 6 | Stale runtime/config identity | Trap **53** (config edit never took effect); versioning 21 | **EXISTING_TRAP_OWNER** |
| 7 | Raw artifact provenance | Evidence repos + SHA256SUMS in trap bodies; support bundles; inline-system schema | **EXISTING** patterns; packet formalises for research flows |
| 8 | Evidence hashes/manifests | Support bundles `SHA256SUMS`; community impact; evidence repos | **EXISTING**; Evidence Packet artifacts[] |
| 9 | Negative controls | `NEGATIVE_CONTROLS` in check contract; doctor CLEAN_CONTRACT | **EXISTING_CHECK_OWNER** / **CONTROL_PLANE_INVARIANT** |
| 10 | Reproducibility requirements | Traps 94, 108, 111; mining agreement-floor notes | **EXISTING_TRAP_OWNER** |
| 11 | Independent review | Diagnosis contract + evidence status preservation; no formal agent role split | **PLAYBOOK_ONLY** (+ review states on packet) |
| 12 | Claim boundaries | Diagnosis contract fields; CONTRIBUTING “name what you cannot claim” | **EXISTING** prose; packet `claim_boundary` field |
| 13 | Check-contract self-testing | `checks/tests/test_check_contract.py`; MANIFEST two-way | **EXISTING_CHECK_OWNER** |
| 14 | Zero-observation / empty-set validation | EMPTY_SET_CONTROL; exit 3 NOTHING_INSPECTED; mining `2026-07-29-the-check-that-did-not-check.md` | **EXISTING_CHECK_OWNER** / **CONTROL_PLANE_INVARIANT** |
| 15 | Harness/scorer defects | Traps 05, 16, 31, 34, 35, 37, 42, 52 | **EXISTING_TRAP_OWNER** |
| 16 | Generated-surface contamination | `integrity/verify_surfaces.py`; `make verify-generated` | **EXISTING_CHECK_OWNER** |
| 17 | Drafts/mining leaking into bundles | Generator from numbered traps; integrity registry | **EXISTING** - audit in CHECK_OBSERVATION / agent-bundle gate |
| 18 | Workspace/state contamination | Trap 54 (warm cache); 89 hardlink shards; 110 shared endpoint | **EXISTING_TRAP_OWNER** |
| 19 | Shared-client/shared-harness contamination | Trap 110; evaluation confounds | **EXISTING_TRAP_OWNER** (+ candidate A playbook/control) |
| 20 | Target-change / upstream-change mining | `upstream/` tier; mining queues; no offline path→surface tool before | **NEW** offline triage check (not a trap) |

## Summary

Most “agentic integrity” mechanisms are **already owned** by traps, the check
contract, doctor verdicts, or integrity generators. This campaign adds
**orchestration doctrine**, a **packet schema**, **preflight**, **blind
review**, **promotion receipt**, **contributor intake**, and **offline
change triage** - without new numbered traps.
