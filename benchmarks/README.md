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

**Reported cases.** The written questions above are what we imagine a user
typing. 25 more cases carry a `source` issue and use the reporter's own words
from that issue, trimmed to the symptom and joined from at most two sentences
of the same report: the closed trap reports and the corroboration issues whose
maintainer disposition names one owning trap (issues closed with no canonical
trap, or split between two, are left out). They are split 13 tune / 12
holdout, one case per issue, and the two traps with two reports (12 and 119)
have one in each split. They are counted in the split totals and also
reported on their own, because they measure something the written set cannot:
how a person who actually hit the trap described it. Some reports became the
entry they point at, so a reporter's words can overlap the entry's own text;
that inflates these numbers, if anything.

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

Holdout split: 143 written queries, then the 12 reported cases, then both
together; 20 off-domain negatives.

| matcher | written top1 | written top5 | reported top1 | reported top5 | all top1 | all top5 | false alarms |
|---|---|---|---|---|---|---|---|
| 0.2.0 (before) | 70.6% | 86.0% | | | | | 70% |
| 0.2.1, part 1 | 83.2% | 92.3% | 33.3% | 58.3% | 79.4% | 89.7% | 0% |
| 0.2.1 | **88.8%** | **92.3%** | **50.0%** | **58.3%** | **85.8%** | **89.7%** | **0%** |

The reported column is the honest headline for people with a real problem:
on reporters' own words the right trap is first half the time and in the top
five 7 times in 12. The written set overstates that. n is 12, so one case is
8.3 points; read it as a direction, not a rate.

The last change (tuned on `tune`, as always) fixed two tokenizer defects the
reported tune cases exposed. Sentence punctuation stuck to the last word of a
sentence, so "ranking." never met "ranking"; only the edges of a token are now
trimmed, so llama.cpp and 0.26 stay whole. And compound identifiers were
opaque: `--tool-call-parser` or `reasoning_tokens` could not meet "tool call
parser" or "reasoning tokens". Their parts now join the identifier's own
concept, so a compound still counts once. On tune this moved three cases
into the top five (one reported, two written) and none out; the reported cases
that exposed the defects still miss, for vocabulary the entries do not use. On written holdout it moved two queries into the top
five and two out of it (traps 16 and 57), which is why top5 did not move.

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

### Pasted error lines

People paste error text more often than they describe it. A question or
`--log` excerpt is now checked against the same log signatures `minefield
scan` uses, and a trap whose signature is present is admitted and ranked
first, labelled `log line match` with the reason. It stays a lead: a
signature says the line is there, not that the trap caused it. Pasted text is
also checked with its line breaks joined, because terminals and issue editors
wrap long lines.

`pasted_lines` holds 6 log lines copied verbatim from reports (wrapping kept),
scored on their own and not split. 2 are ranked first and 3 are in the top
five, the same as before signatures were used: the two lines that have a
signature (traps 117 and 119) were already found by their words, and the other
four have no signature at all, so the gap there is missing signatures, not
routing. On the 12 signature lines in the detector fixtures the right trap is
now first 12 times, up from 8; those lines were written with the rules, so
that shows the routing works, not how often a real paste will match.

### Tried and not kept: indexing reporters' phrasings

We indexed each trap's issue titles and report sentences beside its entry
text (48 phrasings from 26 issues) and scored it leave-one-out, so no report
was matched against its own words. Reported holdout did not move, tune gained
one case and lost one, and three written tune queries fell from first to
second as neighbouring traps picked up shared words ("memory", "decode
speed"). Halving the weight of phrasing-only words kept the losses and lost
the gain. Most traps have one report, and leave-one-out removes it, so this
benchmark cannot show a benefit until more traps have two or more reports. It
may still help when a second person pastes the same error line, but that is
not measured, so it is not shipped.

`tests/test_symptom_benchmark.py` fails CI if the numbers fall below a floor
just under the current results, including a separate floor on the reported
cases. Raise the floor when the matcher improves.

## Adding queries

Add phrasings you have actually seen people use, one per split, and keep the
splits balanced. A query copied from the entry's own text measures nothing.

A reported case needs `"source": "issue #N"`, the reporter's own words, and a
trap the maintainer's disposition names as the owner. One case per issue;
alternate splits so tune and holdout stay within one of each other.
