# Possible / unverified issue leads

Minefield keeps the canonical trap registry strict, but a canonical miss is not the same thing as "we have no useful lead."

This directory is the **non-canonical troubleshooting lead layer**. It preserves first-party observations that are not ready for a trap number, historical mechanisms whose raw packets still need reconciliation, public-source reports that Blackwellboy has not reproduced, negative/replay-clean observations, and hypotheses worth checking when the symptom fits.

## How to use this layer

Search in this order:

1. **Canonical traps** — strongest registry ownership and normal Minefield evidence rules.
2. **Upstream-reported records** — public issue-tracker evidence, explicitly not reproduced here.
3. **Possible leads in `LEADS.json`** — useful hypotheses/checks that must not be promoted by wording alone.

When only a lead matches, say this plainly:

> No canonical Minefield trap matches exactly. Possible unverified lead: `Lxxx` — <title>. It resembles the symptom because <reason>. Try <confirmation check>. If that check fails, treat the lead as refuted or still unresolved.

A lead match is **never** permission to say "root cause", "confirmed", or "your system has this." The lead exists so a person is not left with an empty answer when there is relevant but weaker evidence.

## Status vocabulary

- `FIRST_PARTY_OBSERVED_UNPROMOTED` — observed in Blackwellboy-owned work, but not promoted to a canonical trap.
- `HISTORICAL_FIRST_PARTY_NEEDS_RECONCILIATION` — historical first-party evidence exists, but later bookkeeping/raw-artifact reconciliation is still required.
- `PUBLIC_SOURCE_UNREPRODUCED` — a public source describes or exposes the lead; Blackwellboy has not reproduced it.
- `PUBLIC_SOURCE_VERIFIED_RUNTIME_UNTESTED` — source/code behavior was checked, but the runtime failure has not been reproduced.
- `EXISTING_TRAP_EXTENSION` — useful extra symptom/condition for an existing canonical family rather than a new owner.
- `REPLAY_DID_NOT_REPRODUCE` — an event happened historically, but a later reconstruction/replay stayed clean.
- `BLOCKED_PENDING_CONTROL` — plausible and useful, but the decisive control is still missing.
- `HYPOTHESIS_ONLY` — lowest-confidence idea; use only to choose a bounded check.

## Publication boundary

`LEADS.json` contains only public-safe summaries. Permission-limited third-party/private-share material is **not copied here**. That material remains in the private evidence holding system as a private overlay/research queue until it is independently reproduced, supported by a public primary source, or publication permission exists.

The canonical trap count is unchanged by this directory.

## Search

Simple local search:

```bash
python3 leads/search.py "request waits before prefill"
python3 leads/search.py "wrong endpoint benchmark" --limit 5
```

The search is deliberately simple and transparent. It ranks token overlap across title, symptom, possible mechanism, stack and notes. It does not convert resemblance into confirmation.

## Machine-readable contract

`LEADS.json` is the authority for this public-safe lead layer. Every record carries:

- stable `L###` ID;
- evidence/status class;
- symptom and possible mechanism;
- confirmation and refutation checks;
- conditional mitigation;
- related canonical traps;
- affected stacks;
- source references;
- confidence and notes.

`tests/test_leads_catalog.py` protects the basic contract: unique IDs, required fields, status vocabulary, no canonical-count impact, and no accidentally empty confirm/refute checks.

## Current scope

The catalogue covers public-safe leads across tool-history persistence, SM120/JIT, KV/admission, endpoint identity, stale harness context, schema enforcement, transfer geometry, 200G fabric, lifecycle/memory/speculation, blocked negative observations, public Keys/Inkling source mining, configured-vs-effective vLLM reporting, historical evaluator hypotheses, Kimi-K3 served-render verification, and newer Qwen3.8 runtime/backend observations. The machine-readable `LEADS.json` is the authority for the current set; this README deliberately carries no hand-maintained lead count.

This layer is intentionally broader than "things already proven enough to publish as a trap." That is the point.
