# 2026-08-25 - FlashRDMA portable serving: transport attribution harvest

Public sanitized disposition note. No private hostnames, addresses, or
internal topology. Upstream collaboration used focused PRs into the public
FlashRDMA project; the latest wired depth cell used clean upstream `main`
with **no local library delta**.

## Disposition table

| Finding | Disposition |
|---|---|
| Link-up / interface green ≠ workload path (multi-homed path mis-attribution) | **New canonical trap** [134](../traps/evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md) |
| Character-count / repeated-text fixture labels understate tokenizer depth | **Extend** [trap 49](../traps/evaluation/49-prompt-not-tokenized-to-target.md) (addendum; fixtures 61 / 1015 / 4019 / 8004) |
| Model / serving-engine / transport / end-to-end tok/s attribution | **Playbook + offline preflight** (`playbooks/before-you-publish-an-ab.md` §11; `checks/benchmark_attribution_preflight.py`) |
| Large send-window (W32) isolated win vs sustained NAK/PSN desync risk | **Under test** - wired settling still pending; keep as mining, not a new trap |
| Native RoCE / GPUDirect | **Not proven** - documentation/claim-boundary only; do not invent a positive mechanism from negative evidence |
| Late ACK `_responses` leak; stale `_read_ctx`; timeout map cleanup | **Fixed upstream engineering bugs** (merged focused PR); not public traps |
| Localhost segmented UDP flake hardening | **Engineering hardening** for CI/loopback loss - not a physical-fabric failure trap |

## Why attribution mattered

Across two campaign stages, observed end-to-end 8K median decode throughput
moved dramatically:

| Arm | Prior Wi-Fi session (tok/s) | Later wired session (tok/s) |
|---|---:|---:|
| Flash portable | 1.479 | 7.339 |
| TCP twin | 3.465 | 7.631 |

The later run changed more than physical path: Spark endpoint identity and
upstream FlashRDMA revision also moved. Classify that **cross-session** pair as
**`END_TO_END_COMPOSITE_ONLY`**. Do not cite it as a pure `TRANSPORT`, `MODEL`,
or `SERVING_ENGINE` speedup. A plausible Wi-Fi-versus-wired story is not enough
when multiple layers changed.

Preserve the later **within-session** wired TCP-versus-Flash cell separately:
same wired execution environment, same upstream revision, tokenizer-exact
fixtures, path proof present (8K medians TCP 7.631 vs Flash 7.339). That held
A/B may support a transport-implementation comparison; the composite table
above must not borrow its claim class.

The offline preflight exists so a missing path proof, changed endpoint/host
identity, or other unheld lower layer cannot be published as `MODEL` /
`SERVING_ENGINE` / `TRANSPORT` by accident.

## What stays private / unfinished

- Raw counter dumps and fleet identity stay private.
- W32 reliability on wired remains an open settling test.
- Remaining private serving/protocol candidates from the campaign are not
  auto-promoted by this harvest.

## Related public surfaces

- [Trap 134](../traps/evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md)
- [Trap 49 addendum](../traps/evaluation/49-prompt-not-tokenized-to-target.md)
- [Before you publish an A/B - §11](../playbooks/before-you-publish-an-ab.md)
- [`checks/benchmark_attribution_preflight.py`](../checks/benchmark_attribution_preflight.py)
