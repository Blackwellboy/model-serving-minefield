# Product baseline — 2026-07-30

This baseline was recorded before product implementation on branch
`feat/agent-ready-minefield`.

## Authority

- Repository: `Blackwellboy/model-serving-minefield`
- Remote: `https://github.com/Blackwellboy/model-serving-minefield.git`
- Remote `main`: `48ac850a5f535721ff0308251a79165ac52deb3a`
- Starting local HEAD: `48ac850a5f535721ff0308251a79165ac52deb3a`
- Working tree before mutation: clean
- Canonical enumeration: files matching `traps/<category>/NN-*.md`, as
  implemented by `integrity.registry_integrity.collect_entries`
- Canonical traps: 107
- Root redirect stubs: 7, excluded from the canonical count
- Doctor-covered IDs: 19, derived from `doctor.minefield_doctor.TRAP_PATHS`
- Core entries: 12

## Existing test and integrity commands

The existing CI contract is `.github/workflows/integrity.yml`:

```bash
python3 integrity/registry_integrity.py --github
python3 integrity/reference_integrity.py --github
python3 integrity/upstream_integrity.py --github
python3 integrity/claim_propagation.py --github --repo minefield=.
python3 integrity/do_not_cite.py --github --base origin/main
python3 -m unittest discover -s integrity/tests -t integrity/tests
python3 -m unittest discover -s doctor/tests -t doctor/tests
python3 checks/tests/test_check_contract.py
python3 checks/tests/test_preflight_kwargs.py
python3 integrity/verify_surfaces.py --peer-mode defer
```

`integrity/run_checks.py` passed from the starting tree. Direct execution of
`registry_integrity.py`, `reference_integrity.py`, the two doctor test files,
and the two check-contract files passed. On this Windows checkout, unittest
discovery and `upstream_integrity.py` did not terminate within their bounded
local windows; this is recorded as a platform execution limitation, not a
pass. Linux CI remains authoritative for those commands.

## Existing product surfaces

- Human registry: 107 canonical Markdown trap files in seven categories.
- First-read surfaces: `README.md`, `CORE.md`, and `llms.txt`.
- Stack pages: 11 stack pages plus `stacks/README.md`.
- Model pages: `models/README.md` and one dedicated model page.
- Playbooks: five playbooks plus `playbooks/README.md`.
- Endpoint doctor: one standard-library Python script with Markdown and JSON
  output; 19 mapped trap IDs.
- Standalone checks: eight scripts declared in `checks/MANIFEST.json`.
- Machine-readable data: integrity ledgers/configuration only
  (`integrity/*.json`); no public canonical JSON registry.
- Generated product surfaces: none.
- Packaging: no Python package, wheel, agent bundle, support ZIP, MCP server,
  or product release pack.

## CI, release, and external surfaces

- CI workflows: `integrity.yml` on pushes/PRs and `surfaces.yml` hourly.
- Release process: documented branch/PR flow; no release-artifact workflow.
- Public Pages is generated in the separate
  `Blackwellboy/Blackwellboy.github.io` repository. This implementation will
  not modify that repository.
- `llms.txt` is a count-free routing contract and must stay compact.
- The pre-push sanitizer is private by design and is not represented as a CI
  pass.

## Open pull-request overlap

PR #14, “Trap 98: speculative-decode K x seqs product OOMs on unified memory
(revised),” is open against `main`. It adds trap 98 and would move the
canonical total from 107 to 108; it also touches count-bearing human surfaces.
This product branch does not copy or alter that contributor entry. Generated
counts are derived from the canonical tree so a future rebase can absorb it
without restoring stale literals or losing attribution.

