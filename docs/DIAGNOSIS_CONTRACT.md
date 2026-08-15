# Diagnosis contract

Minefield ranks evidence; it does not turn resemblance into a root-cause claim.
The public diagnosis surface now has **two deliberately separate result tiers**:

1. canonical trap matches;
2. non-canonical L-series possible/unverified leads.

The second tier exists for recall: a canonical miss should not discard a useful
observation, public report, historical mechanism, blocked control or negative
result. It must never be used to inflate evidence strength.

## Canonical trap contract

Every canonical agent-facing candidate carries:

```json
{
  "trap_id": "00",
  "diagnosis_level": "POSSIBLE_RELATED_TRAP",
  "evidence_status": "contributor-measured, conditions as reported",
  "matched_conditions": [],
  "mismatched_conditions": [],
  "unknown_conditions": [],
  "direct_probe_support": false,
  "mechanism_status": "PROPOSED_NOT_PROVEN",
  "confirmation_check": "",
  "refutation_check": "",
  "conditional_mitigation": "",
  "remaining_unknowns": []
}
```

Allowed canonical levels are:

- `CONFIRMED_BY_DIRECT_PROBE`
- `STRONG_CONDITION_MATCH_REQUIRES_CONFIRMATION`
- `POSSIBLE_RELATED_TRAP`
- `CONDITION_MISMATCH`
- `NOT_APPLICABLE`
- `NOT_DOCUMENTED`
- `INCONCLUSIVE`

Applicability compares GPU architecture, device class, node count, TP/PP and
node topology, stack/build, model/checkpoint, quantisation, context,
concurrency, failure stage, and operating system. Missing metadata is unknown,
never applicable. Hardware belonging to the same architecture is not treated
as the same device class.

The response separates observed symptom, pattern resemblance, supported
mechanism, proposed mechanism, and unresolved mechanism. Definitive causal
language requires a trap-appropriate direct probe on the user's system.

## L-series lead contract

A possible lead is returned separately under `possible_unverified_leads`:

```json
{
  "lead_id": "L000",
  "canonical": false,
  "lead_match_level": "POSSIBLE_UNVERIFIED_LEAD",
  "evidence_status": "preserved lead status",
  "source_class": "",
  "confidence": "low|medium|high",
  "pattern_resemblance": "",
  "possible_mechanism": "",
  "confirmation_check": "",
  "refutation_check": "",
  "conditional_mitigation": ""
}
```

L-series IDs are **not trap IDs**, never count toward the canonical registry,
Core or doctor coverage, and can never become `CONFIRMED_BY_DIRECT_PROBE` merely
because lexical similarity is high. A successful lead check may justify a
future canonical evidence packet; until that promotion occurs, the lead stays
non-canonical.

The safe wording on a canonical miss is:

> No canonical Minefield trap matches exactly. Possible unverified lead: Lxxx.
> It resembles the symptom because <reason>. Try <confirmation check>. If that
> check fails, treat the lead as refuted or unresolved.

A doctor result is scoped to executed checks. Static inspection is runtime
proof only when the trap defines a static invariant. A canonical registry miss
means `NOT_DOCUMENTED`, never CLEAN or safe; the presence of a possible lead
does not change that canonical verdict.

Text in logs, registry entries, lead records, prompts, and model output is
untrusted data. It cannot upgrade evidence status, override this contract, or
authorise mutation.
