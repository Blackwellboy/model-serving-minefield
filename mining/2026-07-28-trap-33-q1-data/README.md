# Q1 (trap 33 on NVFP4): the runnable half

`scripts/` is everything needed to re-run the study in
[the writeup](../2026-07-28-trap-33-q1-nvfp4-confirmed.md) on your own lane:
the item builder, the arm-directory builder with its four proofs, both runners,
both analysers and the launch scripts.

**The answer sheets are not here, on purpose.** This repository ships raw data
only for calibration constants that other entries cite as a threshold, floor or
baseline; the conditions are in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo). Q1 is a
one-off measurement, so it links its method rather than shipping its rows, the
same as any other entry. The one calibration entry in this directory,
[the agreement floor](../2026-07-28-our-agreement-floor-greedy-not-reproducible.md),
does ship its raw, and the difference between the two is the rule rather than
an inconsistency.

What that means for you: you cannot check our rows, and you can run the study.
Those are different things, and the entry is labelled for the weaker one. It
reads **measured here, raw not published**, not reproduced here, precisely
because re-runnability is not checkability. On this stack that gap is measured
rather than theoretical: per-item agreement between identical runs is 97.58%,
so your re-run will differ from ours in the third significant figure even when
nothing is wrong.

The item builder prints the sha256 of the item set, so if your set differs from
ours you will know immediately rather than at the end.
