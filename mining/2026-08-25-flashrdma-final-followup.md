# 2026-08-25 - FlashRDMA final wired characterisation follow-up

Public sanitized disposition note for the small Minefield follow-up after the
final wired characterisation campaign. No private hostnames, addresses, or
internal topology. No FlashRDMA library code changes.

## Disposition table

| Finding | Disposition |
|---|---|
| Controlled same-endpoint / same-pin / path-only wired-vs-Wi-Fi with path proof; attribution preflight → `TRANSPORT` | **Extend** [trap 134](../traps/evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md) (dated addendum; status unchanged) + playbook §11 contrast |
| Concurrent HTTP clients with flat aggregate tok/s and batch wall ~scaling with C | **New canonical trap** [135](../traps/evaluation/135-concurrent-http-clients-are-not-concurrent-model-execution.md) |
| Flash `transport_s` near-zero while request wall was path-sensitive | **Engineering / instrumentation only** - timer coverage boundary; not a public trap |
| W32 wired clean but no speedup vs W16 | Mining only / keep W16 default - not promoted |
| Finished-task TCP 4.228s vs Flash 5.609s on the 1Gb portable path | Historical measurement note only - do not invert into a Flash-wins claim |

## Why the Trap 134 addendum

The original entry documents the negative: link-up is not path proof. The
final characterisation supplies the positive half of the same rule: when
endpoint, code, model, and serve state are held and path proof is present, a
path-only delta can honestly be labelled `TRANSPORT`. The earlier cross-session
Wi-Fi→wired table remains `END_TO_END_COMPOSITE_ONLY` because endpoint and
revision also moved. Same narrative, two claim classes.

## What stays private

- Raw counter dumps and fleet identity.
- The Flash `transport_s` instrumentation mismatch detail beyond the
  engineering note above.
