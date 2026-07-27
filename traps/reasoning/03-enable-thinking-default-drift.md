# Trap 03: `enable_thinking` default drifts between revisions

**Found by Blackwellboy and TheTom.**

**Status: reproduced here**, reconciled across three independently run stacks.

**Symptom.** Two testers say "same model" and get materially different
behavior, then spend a week reconciling numbers that were never comparable.
Bug reports land against the model that are really config drift.

**Mechanism.** The same model family ships templates whose default for the
thinking kwarg differs by revision and by upload. One checkpoint defaults it
to `true`; another tester's pin documents `false`. Separately, some servers
supply the kwarg themselves, so the template's `| default(...)` branch never
runs and **omitting the kwarg is not the same as passing its default**. On
one llama.cpp path, absent renders byte-identical to `true`; on a vLLM path
with a different revision, absent lands wherever the template default points.

**Stacks and builds bitten.** Laguna S 2.1 across three independently run
stacks (vLLM/NVFP4, llama.cpp/Q4_K_M, and an EXL3-tail container). Revision
`0761412` (NVFP4 upload) defaults `enable_thinking` to `true`; another pinned
fork documented `false`. Reconciling the three stacks took days and produced the
corrected kwarg model now documented upstream: explicit `false` is the one
structural off-switch, explicit `true` fires, and which arm "absent" lands in
is revision-dependent and server-dependent.

The landing map for an absent thinking kwarg, measured across lanes
(2026-07-27 sweep): Laguna rev 0761412 templates default it ON (both vLLM
lanes); Qwen3.6-27B and Qwen3.5-9B on llama.cpp landed OFF (absent produced
no reasoning while explicit true fired, b9193/b9066); and on a llama.cpp
Laguna path the server supplies the kwarg so absent renders identical to
true (per the upstream #5 correction). Same request, three different arms,
depending on family, revision, and server. Send it explicitly, always.

**The check.** Never reason about thinking from a template's default. Render
your own prompt through the serving path and confirm which branch you landed
in. Record the checkpoint revision hash next to every published number.

**The fix.** Send the kwarg **explicitly** on every request, both in
production and in every measurement arm. Pin the revision and state it.

**Found.** 2026-07-25 to 2026-07-26, reconciling three independent stacks.

**Attribution.** Blackwellboy, TheTom, and the offlabel issue threads where
the kwarg model was corrected. Context:
[laguna-s21-lab README](https://github.com/Blackwellboy/laguna-s21-lab#cross-validation--related-work).
