# 2026-08-25 maintainer adjudication: @sethforprivacy PR #61 + Q16/Q17

Source contribution: [PR #61](https://github.com/Blackwellboy/model-serving-minefield/pull/61), authored commit `773e0150bba67d46948a17ee91d6c26d87b7fb01` by **@sethforprivacy**. The maintainer integration preserves that commit in ancestry rather than copying the contribution onto main without git attribution.

## Final PR #61 disposition

| PR number | Disposition | Main owner |
|---|---|---|
| 127 bind-mount shadow drift | PROMOTE | Trap 127 |
| 128 admission flag never read | PROMOTE | Trap 128 |
| 129 hybrid-KV prefix hit minimum | PROMOTE | Trap 129 |
| 130 CUDA-graph top-shape clamp | PROMOTE | Trap 130 |
| 131 parallel loader / UMA wedge | HOLD, unnumbered | this mining note |
| 132 first request pays JIT | FOLD | Trap 54 addendum |
| 133 HF hub refs offline resolution | PROMOTE, renumber | Trap 131 |
| second-lane data on 61 / 71 / 124 | RETAIN | existing entries |

The base number **127 is preserved** for the external contribution. Folding/holding two proposals closes the gap before the final PR61 entry, so its proposed 133 slides to 131. That is the merge-time numbering policy already documented in MAINTAINING.

## Why proposed 131 is held

The observation is valuable: fastsafetensors multi-node load reached ~7/24 shards, then a ~600 s NCCL broadcast watchdog fired; the worker remained reachable at L4 but stopped completing service initialisation and required a physical power cycle; reverting to the default loader restored repeatable load.

What is **not yet isolated** is the proposed root cause, "transient unified-memory staging pressure". The report has stronger NVRM allocation-retry noise and a steady-state/peak warning, but no direct transient-memory trace that owns the broadcast timeout. There are also public distributed-fastsafetensors failure mechanisms on 2x DGX Spark -- for example [vLLM #34180](https://github.com/vllm-project/vllm/issues/34180), where rank-local file ordering produces mismatched broadcasts -- showing that "loader + NCCL timeout" does not uniquely identify UMA pressure.

**CONFIRM:** on the pinned affected loader, capture per-rank shard/tensor order plus transient host/UMA pressure through the failure. Show matching collective sequence across ranks, then make one loader-memory/staging control change that removes the wedge while the distributed work ordering stays identical.

**REFUTE / re-route:** demonstrate rank-order/tensor mismatch, another loader bug, or a clean high-pressure control with the same memory envelope but no timeout. In that case the finding may still become a loader/distributed-order trap, but not the UMA-pressure trap as proposed.

Credit stays with **@sethforprivacy** either way.

## Why proposed 132 folds into Trap 54

Trap 54 already owns cold compile/kernel-cache/graph warm-up plus run-order A/B contamination. Seth's contribution adds a particularly useful DGX/DSpark signature -- GPU busy, request token counters still zero, worker logs actively compiling, first request >10 minutes vs ~22 s warm -- but it is the same mechanism and the same fix discipline. The measurement and credit are retained as a dated Trap 54 addendum rather than inflating the canonical count.

## Public corroboration used in adjudication

- `huggingface_hub` [#4133](https://github.com/huggingface/huggingface_hub/issues/4133): trailing newline in `refs/<revision>` becomes part of the offline-resolved commit string.
- vLLM [#51441](https://github.com/vllm-project/vllm/issues/51441): hybrid sparse-attention prefix-cache misses at specific prompt lengths, adjacent corroboration for the multi-KV-group cache issue.
- Mia's current DeepSeek-V4-Flash launcher documents the same family of scheduler/capture constraints (`LONG_PREFILL_TOKEN_THRESHOLD`, a partial-prefill knob that is a no-op on that fork, and capture sizing tied to `max_num_seqs * (k+1)`). These are corroboration only; Seth's entries remain `contributor-measured, conditions as reported`.

## Q16 / Q17

The two older strong open candidates are promoted in the same final numbering block so the registry remains gapless:

- issue #36 / Q16 -> **Trap 132**, measured by **@tonyd2wild**, with original scheduler-guard root-cause/fix credit preserved for **@Roady001**;
- issue #38 / Q17 -> **Trap 133**, measured by **@tonyd2wild**.

Both remain contributor-measured; this integration does not relabel them as Blackwellboy reproduction.

## Separate correction from PR #60 review

Codex correctly flagged that Trap 10's new AutoRound addendum said behavior/correctness remained green without mentioning the separate **7/8** OBLIT intelligence smoke against **8/8** Frozenlock. The canonical text is corrected in this batch to report the bounded tool-format near-miss and explicitly reject an intelligence-equivalence claim.
