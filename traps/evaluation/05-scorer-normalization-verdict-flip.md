# Trap 05: a scoring detail silently flips a verdict

**Status: reported by others** (caught and corrected by the upstream checker author); the fix pattern is documented here.

Traps 01 through 04 corrupt what the model *receives* or what you *read
back*. This one corrupts what your scorer *decides*, which is worse in one
specific way: it leaves no trace in the raw logs at all. The transcript is
fine. The number is wrong.

**Symptom.** Verdicts that flip on characters nobody looked at. A clean
refusal scored as compliance, or a fold scored as a hold. The tell is that
the classifier's counts do not survive a hand-read of the same transcripts,
and the disagreements cluster on responses that "look fine" to a human
reader. Because the underlying text is unchanged, no amount of re-reading the
raw logs shows you anything wrong.

**Mechanism.** A scoring or parsing detail that normalizes differently from
the text it is scoring. Unicode punctuation is the common one: a matcher
written with a straight apostrophe (`'`) does not match a model that emitted
a curly one. Same class: smart quotes, non-breaking spaces, collapsed
whitespace, dash variants, and any regex assuming ASCII against a model that
emits typographic characters.

**Stacks and builds bitten.** An upstream behavioral checker, in exactly the
way that makes the point: a response reading "I can't omit the PII" used a
curly apostrophe, the checker matched only the straight one, and a clean hold
was briefly scored as a silent fold. The detail that matters is that this
happened **inside a script written specifically to catch an earlier
classifier failure**. The tool built to catch the bug had the bug. Caught and
corrected by its author before the numbers were published.

**The check.** Two parts, and the second is not optional:

1. **Normalize before matching.** `unicodedata.normalize("NFKC", text)` plus
   an explicit fold of typographic punctuation to ASCII, applied to both the
   pattern and the text. Assume any model can emit smart quotes, because they
   do.
2. **Hand-read a sample of every borderline verdict**, especially the
   `UNCLEAR` and near-threshold bucket. A classifier's agreement with itself
   proves nothing. This is the same lesson as Trap 04 from a different
   direction: the check that cannot fail is not a check.

If a scored result is going to be published, the hand-read step is the
difference between a number and a claim.

**The fix.** Normalization applied on both sides of every matcher, plus a
standing hand-read sample in the scoring protocol.

**Found.** 2026-07-27, during a cross-checked fold-count correction.

**Attribution.** Caught and corrected by the checker's own author upstream;
documented here with the fix pattern. Related raw data:
[spine-probes/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/spine-probes).
