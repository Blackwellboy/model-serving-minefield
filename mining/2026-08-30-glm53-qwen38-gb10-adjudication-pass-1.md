# Adjudication pass 1: GLM-5.3 / Qwen3.8 GB10 harvest

**Date:** 2026-08-30

This pass advances only H30 items whose primary public sources were reopened and whose evidence tier can be stated cleanly. It does **not** change the canonical Minefield trap count.

## Result

Four H30 findings are now promoted from mining-only leads into the non-canonical `upstream/` tier:

| H30 | Upstream | Disposition | Why |
|---|---|---|---|
| H30-10 | U36 | upstream-reported, closed/fixed | issue #15 gives the warm-restart stdout-contamination reproduction; fix commit `f68130a` routes diagnostics to stderr and uses `python3 -S`, with a regression test |
| H30-11 | U37 | upstream-reported, maintainer reproduced, closed/fixed | issue #6 records ~55 -> 5 tok/s mixed cold-prefill starvation; MiaAI-Lab reproduced the scheduler-step mechanism and commit `f3043c9` restored the decode floor in its retest |
| H30-12 | U38 | upstream-reported, maintainer reproduced, closed/fixed | issue #13 + merged PR #14 establish the DFlash standalone BlockPool-ID tax and publish before/after occupancy after padded slot-share |
| H30-08 | U39 | upstream-reported, open/unresolved | vLLM #54150 provides token-ID-level evidence for invalid byte-token sequences on ModelOpt NVFP4, but damaged conversion vs loader-path root cause remains unresolved and maintainer engagement is still none |

No item above is claimed as first-party Blackwellboy reproduction.

## Primary-source receipts

### H30-10 -> U36

Source: `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks` issue #15.

The report identifies a concrete cold/warm asymmetry: `sitecustomize.py` applies overlays at every Python startup; the already-applied warm path emits a diagnostic to stdout; `start.sh` captures Python stdout while constructing `--speculative-config`; the diagnostic prefixes otherwise-valid JSON and vLLM argparse rejects it.

Fix commit `f68130a4365f648b4833b169d75ef1a4188bfcb8` both:

- routes overlay diagnostics to `sys.stderr`; and
- switches the launcher JSON helper from `python3 -c` to `python3 -S -c`.

The commit also adds `tests/test_warm_restart_stdout.py`, checking that command substitutions skip `sitecustomize` and import-time overlay prints target stderr.

This is strong enough for the upstream-reported tier without pretending the registry ran the container.

### H30-11 -> U37

Source: MiaAI-Lab issue #6 plus maintainer comment and fix commit `f3043c95bbf95fb91dd160fe58d740cd152a02c3`.

The report's controlled pair uses unique ~100K cold prefixes, zero prefix-cache hits, zero preemptions and near-perfect/perfect DFlash acceptance. The active decode falls from roughly 51-55 tok/s to 5 tok/s only while the peer cold prefill shares engine steps.

MiaAI-Lab then reproduced the mechanism on its own 2x GB10 kit: `max_num_batched_tokens=1024` is the whole step budget, so a small DFlash decode slice can leave roughly 1016 tokens to a costly sparse-MLA prefill chunk. The shipped `GLM53_MIXED_PREFILL_CHUNK=skip` policy avoids mixing a peer prefill into a decode step. The maintainer retest reported 68.1 tok/s solo decode, 69.2 while the peer cold-prefilled, and 68.2 for the peer's later decode.

### Exact dedupe against Trap 128

Do **not** merge U37 into canonical Trap 128 by symptom alone.

Trap 128's owner is an **accepted/configured admission flag that the measured scheduler never reads**. Its key failure is that `max_num_partial_prefills` is inert on that build, so the obvious flag A/B is a false negative.

U37's source reports a different mechanism: the step budget is real and actively consumed by a mixed sparse-MLA prefill. The source's fix is not to make the dead flag live; it deliberately skips/caps peer prefill when a decode sequence is running. Same visible decode-starvation family, different scheduler owner.

### H30-12 -> U38

Source: MiaAI-Lab issue #13 and merged PR #14.

Before the slot-share fix, five DFlash SWA layers consumed standalone globally unique BlockPool IDs. Compact-64 removed the per-block byte blow-up but did not remove the ID tax: the source reports 1,096,153 logged GPU KV tokens while one ~36K request consumed 44.6% of 665 blocks and three ~256K sessions could not be resident.

Merged PR #14 padded slot-shares the draft layers onto MLA tensors at window-bounded IDs. The source reports 1,754,237 logged tokens, one ~36K request around 16% KV, and successful multi-request occupancy tests after the allocator change.

### Exact dedupe boundary for U38

- Trap 106 owns a false **memory-leak** diagnosis caused by normal prefix-cache occupancy reaching a steady plateau. U38 is not a leak/plateau claim.
- Trap 135 owns client concurrency versus actual execution concurrency. U38 is resident cache/admission geometry even before asking whether requests execute simultaneously.
- U34 owns DFlash/DCP **draft-KV budget undercount by the DCP factor**. U38 is a different grouped-cache BlockPool-ID/layout tax.

U38 therefore belongs in the upstream tier as a distinct source-level allocator mechanism unless future code comparison proves equivalence.

### H30-08 -> U39

Primary source requirement is now satisfied: vLLM issue #54150 and its cross-reference comment were read on 2026-08-30.

What the source supports:

- two ModelOpt-produced GLM-5.3 NVFP4 checkpoint families emitted U+FFFD replacement characters across deterministic/non-deterministic Korean generations;
- a compressed-tensors NVFP4 conversion of the same model was clean under the source's held-fixed serving stack;
- returned token IDs, when decoded offline with the checkpoint tokenizer, reproduced the replacement-character count, so the symptom is not merely client rendering;
- context length, temperature, MTP, PDL, abliteration and a larger ignore list were individually tested and did not remove the reported symptom.

What the source **does not** support:

It does not distinguish damaged ModelOpt conversion artifacts from a vLLM ModelOpt NVFP4 loader/execution defect. The issue explicitly leaves both explanations open. The issue has no maintainer resolution at this read. U39 therefore records the behavior and the discriminating next experiment, not a loader root cause.

A related vLLM issue #52540 reports a different ModelOpt-NVFP4 sustained-load crash/wedge on SM120. That strengthens interest in the path but does not establish one shared cause and is not folded into U39.

## Still held after this pass

The rest of H30 remains where it belongs:

- H30-01 explicit KV pin / activation reserve: needs bounded A/B or stronger primary implementation proof.
- H30-03 UVM livelock: do not deliberately induce on a production Spark; capture naturally if it occurs.
- H30-05 dependency-induced NCCL downgrade: high-value disposable-environment reproduction candidate.
- H30-07 uninitialized/in-range pool IDs: source-level poison/sentinel test remains the clean next step.
- H30-09 strided/padded logical-vs-storage allocation blow-up: needs direct primary code/allocator proof before tier promotion.
- H30-15 Qwen MTP shift/LSE/master-slice: still compound; split into one-variable mechanisms.
- H30-16 heterogeneous cache dtype: needs effective dtype proof per cache group.
- H30-19 production-only blank tool args: remains unresolved; no DFlash/parser blame without a failing raw token/XML artifact.
- H30-22 grammar transition inside speculative window: primary patch/source review still required.
- H30-24 grouped-KV generic-unification mismatch: keep separate from U38 until code-level owner equivalence is settled.
- H30-43 shared `/dev/shm` CUDA-IPC collision and H30-44 media-frame estimator remain bounded reproduction candidates.

## Registry effect

`CANONICAL_TRAP_COUNT_IMPACT=0`

`UPSTREAM_PROMOTIONS=U36,U37,U38,U39`

The mining packet and tweet bank remain useful, but public wording for H30-08/10/11/12 should now defer to the corresponding upstream entry because those entries record the current primary-source state and tighter claim boundaries.
