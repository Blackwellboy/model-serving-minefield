# Symptom benchmark

`minefield <symptom>`, `minefield guide`, the MCP `search_symptom` tool and
`minefield.api.match_symptom()` all share one offline matcher. This directory
measures how often it finds the trap a person actually hit.

```bash
python benchmarks/run_symptom_benchmark.py            # summary
python benchmarks/run_symptom_benchmark.py --misses   # every query not in the top 5
```

## The data

[`symptom_queries.json`](symptom_queries.json) holds, for each of the 143
canonical traps, **two plain-language questions written the way a user would
type them** ("streaming shows blank replies"), not copied from the entry text.
One is in the `tune` split and one in `holdout`. There are also 40 off-domain
questions ("how do I bake sourdough bread"), 20 per split, that must return no
trap at all.

Matcher changes are tuned against `tune` only. `holdout` is the number to
report. It is not pristine: it was run to check each change, but no word list,
weight or threshold was chosen by looking at a holdout miss.

## What the numbers mean

| metric | meaning |
|---|---|
| top1 | the right trap is ranked first |
| top5 | the right trap is in the first five |
| found | the right trap is returned at all |
| mrr | mean reciprocal rank of the right trap |
| false alarms | share of off-domain questions that returned any trap |

## Results

Holdout split, 143 queries, 20 off-domain negatives:

| matcher | top1 | top5 | found | false alarms |
|---|---|---|---|---|
| 0.2.0 (before) | 70.6% | 86.0% | 90.2% | 70% |
| 0.2.1 | **83.2%** | **92.3%** | **93.7%** | **0%** |

What changed, in order of effect:

1. **A real stop-word list.** "how", "do", "is", "in", "to" counted as shared
   concepts, so any question with two of them matched something. This alone
   took off-domain false alarms from 65% to 15% on the tune split.
2. **Rarity weighting and light stemming.** A word found in one entry
   ("nvfp4", "orphan") counts for far more than one found in most ("model",
   "server"), and "restarted" now meets "restart".
3. **An on-topic gate.** A question must mention something about model
   serving before resemblance can nominate a trap. "Best running shoes for
   flat feet" shares two rare registry words and nothing else.
4. **Title weighting.** A word matching the entry's own one-line title counts
   1.5x.

`tests/test_symptom_benchmark.py` fails CI if the numbers fall below a floor
just under the current results. Raise the floor when the matcher improves.

## Adding queries

Add phrasings you have actually seen people use, one per split, and keep the
splits balanced. A query copied from the entry's own text measures nothing.
