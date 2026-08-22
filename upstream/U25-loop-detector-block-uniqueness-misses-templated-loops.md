# U25: a naive uniqueness metric can call a reasoning loop fresh text

**Reported by @Capicua25x.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The source repository merged the revised loop detector in PR #29.

**Issue state: closed, fixed.** The stated block/window measurement defect is corrected in the merged detector; fragmented loops remain an explicit limitation.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #29](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/29), read on 2026-08-21.

**Symptom.** A reasoning trace is visibly stuck recycling the same ideas, but a "percent unique" detector says the output is mostly fresh and classifies the run as a healthy heavy tail. Increasing `max_tokens` then burns a larger budget on a loop instead of helping a genuinely long thought finish.

**Mechanism.** The source's runaways were templated rather than byte-for-byte repeats: stock phrases were recombined with small varying elements. On the same three captured loops, non-overlapping 120-character block uniqueness read 22% / 92% / 66%, while unique word 8-grams were only 3.4% / 4.0% / 2.8%. One trace therefore looked 92% unique at block granularity while being about 96% recycled at phrase level.

The revised detector tokenizes once, windows over the **word sequence**, measures novelty of word 8-grams against everything seen earlier, and calls a loop only when novelty collapses below a threshold for multiple windows and stays collapsed to the end. This also avoids a second artifact: character-window boundaries can split repeated tokens differently and manufacture apparent novelty in short-period English or CJK loops.

The source explicitly records a limitation from @brianmswheart: fragmented loops interrupted by tools or novel filler can stay above the window threshold. That shape needs an additional repeated-sentence/recycled-mass tier and is not claimed solved here.

**What we have not done.** We have not run the detector against the source traces or our own reasoning captures. The reported numeric thresholds are calibration for those traces, not a universal loop definition.

## If you have this stack

Take raw reasoning traces labeled independently as (a) known loop, (b) long but genuinely novel heavy tail, and (c) a long verbatim re-quote that later recovers. Compute the old fixed-block uniqueness metric and the word-sequence n-gram novelty metric on the same text. Include at least one templated loop and one CJK/short-period loop.

**CONFIRM.** A known loop scores misleadingly high under the naive block/window metric while phrase-level novelty collapses and remains low; healthy varied controls do not show persistent collapse.

**REFUTE.** The allegedly misleading metric cleanly separates all known loops from heavy-tail controls on the same corpus, or the proposed n-gram detector collapses equally on healthy varied reasoning.

## Attribution

Reported and calibrated by @Capicua25x in PR #29; the fragmented-loop limitation and field report are credited there to @brianmswheart. The registry has not independently reproduced either dataset.
