# Candidate mechanism matrix - Agentic Research Integrity 2026-08-07

Candidates only. No trap numbers allocated.

| ID | Candidate | Classification | Rationale |
|----|-----------|----------------|-----------|
| A | PRIMARY_EXPERIMENT_AND_NEGATIVE_CONTROL_SHARE_THE_SAME_BROKEN_HARNESS | **PLAYBOOK_ONLY** + packet `controls.shares_same_harness` | Real risk class; reproducible as trap only with a specific stack defect. Closest existing: evaluation harness traps (05, 37, 42) and 110. Do not number. |
| B | INDEPENDENT_REVIEWER_RECEIVES_THE_PROPOSER_CONCLUSION_BEFORE_ANALYSIS | **PLAYBOOK_ONLY** | Anchoring; mitigated by blind-review tool. Not a serving trap. |
| C | TARGET_REVISION_DRIFT_INVALIDATES_REPRODUCTION | **EXTEND_EXISTING_CHECK** / **CONTROL_PLANE_INVARIANT** | Preflight rejects moving `main`; pin required. Related: doctor hf-revision, inline-system SHA. |
| D | TOOL_EXIT_SUCCESS_DOES_NOT_PROVE_THE_INTENDED_CODE_PATH_WAS_EXERCISED | **EXISTING** via check-contract / “check that did not check” mining | Exit 3 / EMPTY_SET / CLEAN_CONTRACT. Optional future draft if a new serving-specific case appears. |
| E | MODEL_OR_AGENT_SUMMARY_CONFLICTS_WITH_RAW_ARTIFACT | **PLAYBOOK_ONLY** + preflight `summary_only` ban on promotion | Raw artifacts outrank narrative. |
| F | SHARED_WORKSPACE_STATE_LEAKS_BETWEEN_SUPPOSEDLY_INDEPENDENT_RESEARCH_ROLES | **EXISTING_TRAP_OWNER** (54, 89, 110) + playbook isolation identity | Packet requires `isolation_workspace_identity`. |
| G | RECENTLY_CHANGED_TARGET_SELECTED_BUT_STALE_LOCAL_CHECKOUT_TESTED | **PLAYBOOK_ONLY** + upstream-change triage prioritisation | Pair change radar with PIN step; not a new trap without measured case. |

## Counts

| Bucket | Count |
|--------|------:|
| EXISTING_TRAP_OWNER | 2 (F partial, D partial) |
| EXTEND_EXISTING_CHECK | 1 (C) |
| PLAYBOOK_ONLY | 4 (A, B, E, G) |
| CONTROL_PLANE_INVARIANT | 1 (C shared) |
| NEW_UNNUMBERED_DRAFT | 0 |
| MINING_OPEN_QUESTION | 0 |
| DROP | 0 |

**NEW_UNNUMBERED_DRAFTS:** none - no reproducible serving-specific evidence
package was introduced solely to dress architecture opinions as traps.
