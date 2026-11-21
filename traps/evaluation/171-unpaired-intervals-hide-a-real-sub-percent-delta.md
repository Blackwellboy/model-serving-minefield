# Trap 171: unpaired confidence intervals hide a real sub-percent quality delta that a paired per-document comparison finds

**Found by Blackwellboy.**

**Status: measured here, raw not published.** One first-party evaluation; the
per-document scores are not published. The check is a few lines of code over
your own per-document numbers.

**Symptom.** You compare a base model with a fine-tuned, merged, edited or
re-quantized derivative on bits per byte or perplexity. The two confidence
intervals overlap, so you call it "no measurable difference". Or the reverse:
a 4-point gap on a 200-question benchmark subset is read as real damage.

**Mechanism.** Both arms score the same documents, and document difficulty
varies far more than the difference between arms. Unpaired intervals carry all
of that document-to-document spread, so a small, consistent shift sits inside
them. Pairing removes it: the per-document difference is nearly constant, and
its interval is narrow. The opposite failure comes from small n: on 200
multiple-choice items at about 70% accuracy, one arm's standard error is
already about 3.2 points, so a 4-point gap between two unpaired arms is within
noise.

**Stacks and builds bitten.** ExLlamaV3 1.6.1, BF16, Qwen3.8-27B and three
community derivatives of it, 315 fresh documents (208,807 tokens) plus a
control set, 2026-11-21:

- Base 0.6396 bits per byte; a repeat run was bit-identical, so the scorer
  itself adds no noise.
- One derivative scored 0.6415: +0.0020 (+0.31%), paired 95% interval
  [+0.0015, +0.0025], KL 0.0051, top-1 agreement 97.3%. The unpaired intervals
  almost completely overlapped.
- A second derivative was +0.76%, paired interval [+0.0043, +0.0055].
- A third was +0.19% on fresh text with a paired interval crossing zero, but
  the worst on the control set (+3.66%, KL 0.069), which is an overfitting
  signal the fresh-text number alone would have hidden.
- The derivative with the real +0.31% delta also scored 4 points lower on a
  200-question MMLU-Pro subset (67.5% against 71.5%). That gap is inside
  unpaired noise at this n and is not explained by the bits-per-byte delta.

**The check.** Score both arms on the same documents, keep per-document
results, and bootstrap the mean of the per-document differences. Compare that
interval with the two unpaired intervals. Confirmed when the paired interval
excludes zero while the unpaired intervals overlap. For accuracy benchmarks,
use a paired test on per-item correctness (McNemar or a paired bootstrap)
before calling a gap real, and run the scorer twice to prove it is
deterministic.

**The fix.** Report paired deltas with their interval, plus KL and top-1
agreement, for any derivative-versus-base comparison. Keep a control set the
derivative may have seen alongside fresh text the derivative cannot have seen;
fresh minus control is a cheap overfit check. Do not read small-n benchmark
gaps without a paired test.

**Found.** 2026-11-21, checking whether a derivative's benchmark drop was lost
knowledge or changed behaviour.

**Attribution.** Blackwellboy.

**Related.** [35](35-identical-weights-do-not-score-identically.md),
[34](34-baseline-you-degraded-yourself.md),
[17](17-per-arm-recommended-sampling-confound.md).
