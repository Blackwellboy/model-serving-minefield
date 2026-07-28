# U10: a reranker with the wrong template returns confident, near-reversed scores

**Reported by @xl2014.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer responded.** @haosdent diagnosed it and
attempted a reproduction; @noooop, who maintains the tracking issue for this
model family, was drawn in.

**Issue state: closed, resolved as usage.** This is the important label on this
entry and it is not what our own mining queue believed. **The thread does not
establish a vLLM scoring defect.** It establishes a usage trap with a
silent-wrong signature, which is arguably worse.

**Primary source.** [vllm-project/vllm#35412, "Qwen3-VL-Reranker produces
completely wrong relevance scores compared to native
Transformers"](https://github.com/vllm-project/vllm/issues/35412). Read on
2026-07-28: body and all five comments **including the reporter's own closing
comment**, which is where the resolution is.

Context, read the same day:
[#33986](https://github.com/vllm-project/vllm/issues/33986), the maintainer's
tracking index for this model family, and
[#33813](https://github.com/vllm-project/vllm/issues/33813), a separate
batched-scoring report also resolved as an API-shape requirement.

**Symptom.** The reranker runs, returns scores for every pair, and the ranking
is close to **reversed**. The reporter's example: a query for "cat drinking
water" scores an image of a cat drinking low, and irrelevant images high.
Nothing errors, latency is normal, and the scores are well-formed floats in the
expected range. Compared against the same model under native Transformers, the
ordering collapses.

**Mechanism, as the thread resolves it.** Two causes in sequence, and both are
worth knowing.

**First**, the model was served **without `--chat-template`**. @haosdent
identified this from the launch command. A reranker's score depends on how the
query and the document are assembled into a prompt; assemble them differently
from training and the model still produces a number, and the number is
meaningless. There is no error because there is no error condition, the
pooling path returns a score for whatever it was given.

**Second, and this is the part worth the entry.** The reporter then supplied a
template and the scores were *still* wrong. The resolution, in their own words:

> "Previously, I directly copied the original Jinja file, but it didn't work.
> By directly downloading the original Jinja file from VLLM instead of copying
> it, the issue with abnormal scoring was resolved."

A **copied** template and a **downloaded** template produced different scores.
Whatever the copy lost, whitespace, line endings, an escape mangled by a
terminal or an editor, was invisible, silent, and enough to move the output.

**Why we are publishing a resolved-as-usage issue, and correcting ourselves.**

Our own round-2 queue carried this as a well-attested vLLM bug and ranked it
seventh of fifty, and
[our blocked-candidates note](../mining/2026-07-27-r2-blocked-not-testable.md)
recorded it as untestable for want of weights, with a test plan that would have
compared vLLM against Transformers to confirm a defect that is not there. It
sat that way for months. Nobody had opened the thread past the title. That is
the exact failure the
[upstream-reported tier's evidence bar](../CONTRIBUTING.md#the-fourth-tier-upstream-reported)
now exists to prevent, and this entry is here partly as its worked example.

The trap that **is** real is better than the one we thought we had. Scoring and
embedding paths have no natural correctness signal: a classifier returns a
class, a reranker returns an order, and both look completely healthy while
being wrong. Generation at least degenerates visibly. This is trap
[05](../traps/evaluation/05-scorer-normalization-verdict-flip.md) and trap
[37](../traps/evaluation/37-uniform-zero-is-a-harness-verdict.md) in a place
where you have no prose to eyeball.

**What we have not done.** Nobody here has reproduced this. We hold no
reranker or VL-embedding weights, and no entry in this registry has ever
measured a pooling or scoring serving path. That is a whole class of serving
this project has never touched, and it is recorded as such in
[CONTRIBUTING's coverage gaps](../CONTRIBUTING.md#where-coverage-is-thin).

## If you have this stack

vLLM and any reranker or embedding model. Two to three hours, and it needs no
special hardware.

The thing to measure is **rank correlation against a Transformers baseline**,
not absolute scores, which are not comparable across paths.

1. Build a fixed set of 50 query-document pairs where you know the correct
   ordering, including deliberately irrelevant pairs.
2. Baseline: score them with native Transformers.
3. Arm A: serve with vLLM `--runner pooling`, **no** `--chat-template`.
4. Arm B: identical, with the template **downloaded** from the vLLM repository
   rather than copied by hand.
5. Arm C, which is the one nobody has run: the **same** template file, copied
   through an editor or a terminal paste. Then `sha256sum` B and C. If the
   hashes differ, you have the second cause isolated; if they match and the
   scores still differ, the reporter's account needs revisiting.
6. Report Spearman correlation against the baseline for each arm.

**CONFIRM.** Arm A's correlation is near zero or negative while Arm B's is
high, and Arm C differs from Arm B. Report all three correlations and the two
hashes.

**REFUTE.** Arm A tracks the baseline, meaning the template is not load-bearing
for this model, a genuinely useful negative, because it would bound the claim
to the specific checkpoint.

**The highest-value single result here** is Arm C: whether a hand-copied
template can silently change scores. That is a general hazard, it needs one
model and one afternoon, and no one has published it.

## Attribution

Reported by @xl2014, who also ran the comparisons and published the
resolution. Diagnosis by @haosdent. Family tracking by @noooop. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).
