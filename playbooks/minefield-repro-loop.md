# Playbook: Minefield repro loop

Reusable experiment loop for serving investigations and research-stack
integrity work. **Orchestration doctrine only** - not authority to execute
endpoints, restart services, or run benchmarks.

## Steps

1. **PIN** - exact target/runtime/tool identities (commit SHA, model id,
   engine build, config hash, workspace identity). Prefer immutable pins over
   moving names (`main`, `latest`).
2. **HYPOTHESIZE** - mechanism and **expected disproof**.
3. **MINIMAL REPRO** - smallest experiment capable of triggering the mechanism.
4. **POSITIVE CONTROL** - prove the detector can see expected good behaviour.
5. **NEGATIVE CONTROL** - test an alternative explanation; record whether the
   control shares the same harness/workspace.
6. **ATTRIBUTION** - classify `failure_cause` using
   [`docs/failure-cause-taxonomy.md`](../docs/failure-cause-taxonomy.md). Never
   silently treat infrastructure/harness failure as a target negative.
7. **ARTIFACT** - hash and preserve raw outputs (SHA256). Summaries do not
   replace raw artifacts.
8. **BLIND FALSIFICATION** - derive a blind-review packet when independent
   review is appropriate (`minefield blind-review`).
9. **ADJUDICATION** - select disposition: existing owner / extension / check /
   mining / unnumbered draft / reject. Preserve Minefield evidence status.
10. **PROMOTION** - number only under normal Minefield publication governance;
    record a promotion receipt when promoting.

## Packaging

Fill an Evidence Packet
([`docs/evidence-packet.schema.json`](../docs/evidence-packet.schema.json))
and run:

```bash
python3 checks/evidence_packet_preflight.py --packet packet.json
```

See also [`agentic-research-integrity.md`](agentic-research-integrity.md).
