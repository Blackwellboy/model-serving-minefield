# Trap 170: retrying capped thinking answers at double the token budget mostly buys a second loop, and the score drop was loop rate, not accuracy

**Found by Blackwellboy.**

**Status: measured here, raw not published.** One first-party run, single
pass; the per-item log is not published. The check below needs only your own
run's per-item records.

**Symptom.** A reasoning model's MMLU-Pro or IFEval score looks several points
worse than its peers. A noticeable share of items hit the token cap. You rerun
those at double the budget expecting the score to recover, and the rerun takes
hours: most of the retried items hit the new cap too.

**Mechanism.** At high reasoning effort some items do not need more tokens;
they never converge. The model repeats itself or restarts its reasoning until
the cap stops it. A bigger cap moves where it stops and multiplies the
wall-clock cost, because a looping item always runs to the full budget and a
retry queue is usually run one stream at a time. Meanwhile the headline score
counts every capped item as wrong, so it blends two different properties: how
often the model loops at this effort, and how accurate it is when it finishes.
[Trap 12](12-empty-content-at-token-ceiling.md) covers budgets that are simply
too small; this entry is the case where the budget is not the problem.

**Stacks and builds bitten.** llama.cpp b12600, a Q4_K_M quant of Inkling 2
Mini, flash attention off, RTX 5090 at 450 W, 2 parallel slots, reasoning
effort high, 2026-11-21:

- 627 items at a 16,384-token cap: 63 hit it (GSM8K 1, MMLU-Pro 37 of 200,
  IFEval 25).
- The 32,768-token retry ran one stream at about 70 to 80 tok/s, so a looping
  item cost up to about 7 minutes. In a 90-minute budget it reached 29 items;
  19 MMLU-Pro items hit 32,768 again.
- MMLU-Pro scored 72.5% with unresolved items counted wrong, and 84.7% on the
  items that finished. IFEval scored 80.3% and 87.4% respectively.
- GSM8K's single capped item resolved, and that score (98.5%) is valid.

A second lane is consistent but not settled: on a DeepSeek-V4.1-Flash EXL3
checkpoint under TensorFold TP=2 with the loop guard off, temperature 0 looped
verbatim on 8 of 10 previously capped MMLU and GSM8K items out to 64K tokens,
and temperature 1 on 0 of 12 (2026-10-24, measured here, raw not published,
stock comparison not run).

**The check.** For every item that hits the cap, look at the tail before
retrying. Compress or n-gram the last few thousand tokens: if fewer than about
2% of 8-grams in consecutive 1,024-token windows are new, it is a loop, not an
unfinished answer. Then retry a small sample (5 to 10 items) at double the
budget before committing to the full rerun. Confirmed when most of the sample
hits the bigger cap again and the tails are loops.

**The fix.** Report three numbers, never one: the score with loops counted as
failures, the accuracy on finished items, and the loop rate (items that hit
the cap and still loop at the larger budget). Set a wall-clock budget for the
retry and record anything unresolved as a loop failure. Mark any arm with a
meaningful cap-hit share as invalid for comparison rather than publishing its
headline score. Try the model's recommended sampling temperature before
concluding the model is worse; greedy decoding can be the trigger.

**Found.** 2026-11-21, qualifying a new model on a production card with a
fixed pause budget.

**Attribution.** Blackwellboy.

**Related.** [12](12-empty-content-at-token-ceiling.md),
[36](36-token-cap-is-an-arm-level-handicap.md),
[16](16-finish-reason-is-not-a-failure-signal.md),
[149](149-thinking-on-json-schema-can-runaway.md).
