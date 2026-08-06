# Trap 40: your contamination screen is mostly firing on boilerplate

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-11 entries; and
[reports/campaign_v3ja_v2/MT_SETA_POSTMORTEM_20260726.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/reports/campaign_v3ja_v2/MT_SETA_POSTMORTEM_20260726.md)
section F2).**

**Status: reported by others.**

**Symptom.** You run an n-gram decontamination gate over your training corpus
against your eval sets and it reports an alarming overlap. A third of the
corpus is "contaminated". You either throw the data away, or you conclude
your benchmark numbers are worthless, and either way you have made a decision
about a model on the basis of a number nobody opened.

The finder's first run removed **638,541 of 2,015,157 rows (31.7%)**. After
inspection, the correct figure was **143,487 (7.1%)**. The 31.7% was almost
entirely an artifact.

**Mechanism.** Two different failure modes, kept separate here because they
have different causes and different fixes.

**1. Boilerplate that is common to both sides.** Of the 31.7% removed,
**95.2% (about 608k rows)** matched the BFCL eval set alone, and inspection
showed the match was a **single 8-gram**:

```
type object properties required type function function name
```

That is JSON tool-schema boilerplate. It appears in every OpenAI-format
function definition in the corpus and in every one in the eval set, and it
carries no information about leakage whatsoever. The gate was measuring the
prevalence of a serialization format. The finder's later multi-turn campaign
hit the same class twice more: generic function-doc phrases ("this tool
belongs to ...") colliding with ordinary coding data, and lorem-ipsum-style
placeholder bodies inside ground-truth long-context material colliding with
unrelated text.

**2. The gram is too short for the alphabet.** On Japanese data the matcher
tokenized CJK one character per token, so an 8-gram was **8 characters** and
the entropy per window was far too low. Hit rates reached **84.8%** on one
Japanese source and **76.7%** on another, on windows that turned out to be
everyday phrases. Even the longest consecutive run, 11, was ordinary prose.
None of it was leakage.

The contrast that makes the point: in the same audit, English code sources
produced hit rates of **8.8%** and **3.5%**, and those were **real**. The
tell was the distribution of run lengths, not the rate. Genuine
transcription showed a bimodal pattern, sporadic runs of 1 to 5 alongside a
cluster at 11 to 18, and a run of 11 corresponded to 18 consecutive matching
words of a HumanEval solution. Boilerplate produces one gram, everywhere.
Transcription produces long contiguous runs, in a few places.

**Stacks and builds bitten.** A word-level normalized 8-gram matcher run over
a 2,015,157-row mixed corpus (Toucan and ToolMind subsets) against six eval
sets (MMLU, GSM8K, HumanEval, JMMLU, BFCL, M-IFEval). The class is
tool-independent and bites hardest on tool-calling and structured-output
corpora, where a large fraction of every row is schema, and on any
non-whitespace-delimited language.

**The check.** Never accept a removal rate without opening the removals.
Three concrete steps:

1. **Print the top matching grams by frequency.** If one gram explains most
   of your hits, it is boilerplate. This alone caught 95.2% of the finder's
   false positives.
2. **Look at the run-length distribution, not just the hit count.** Long
   contiguous runs are transcription; isolated single-gram hits are format.
3. **Run a positive control.** Verify the matcher still catches real
   leakage after you tighten it, or you have replaced a noisy detector with a
   dead one. The finder checked that verbatim BFCL question transcriptions
   were still caught: **19/20 retained**.

**The fix.** Two filters, both measured by the finder:

- **Document-frequency filter on the eval side** (`--max-df 2`): drop any
  gram appearing in 3 or more rows of the eval set itself, as formulaic. On
  BFCL this removed **40,441 of 147,811 grams (27%)** as boilerplate, while
  the 64% of grams appearing exactly once carried the actual detection power.
- **Require at least 2 distinct matching grams per row** (`min_hits=2`),
  which kills asymmetric boilerplate that is rare in the eval set but
  universal in the corpus, the case the DF filter alone misses.

Together these took the removal rate from 31.7% to 7.1% while retaining
19/20 true detections; on one shard, removals fell from 56% to 3.0%. For the
CJK case, calibrate the gram length to the alphabet, or switch to a
run-length criterion, rather than reusing the English window size. For
tool-calling data, protect **user utterances** as the matched leaf and do not
treat full tool schemas or placeholder document bodies as protected text.

State the residual limit out loud, as the finder does: all of this is
lexical, so recall against paraphrased or semantically reconstructed
contamination is close to zero. A clean n-gram audit is evidence about
copying, not about leakage in general.

**Found.** 2026-07-11, when a 31.7% removal rate looked wrong enough to
inspect, and again 2026-07-26 on a multi-turn gate.

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
whose rule is the transferable part: **make the removal rate itself an object
of inspection.** Having removed something is not proof of cleanliness until
you have read the removals one row at a time.
