# U27: speculative draft counts above four can silently leave stale DSV4 compressed state

**Reported by @hnyls2002.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #34189 is merged.

**Primary source.** [SGLang PR #34189](https://github.com/sgl-project/sglang/pull/34189), read on 2026-08-25.

**Symptom.** DeepSeek-V4 speculative serving can stay alive with no assertion, illegal access or NaN while the compressed-state ring contains stale positions once the speculative draft count exceeds four. Ordinary end-to-end quality runs may not reliably expose it because the stale read depends on acceptance length, sequence position and compression alignment.

**Mechanism.** The compressed-state write planner used a hard-coded speculative pad of four. With `--speculative-num-draft-tokens > 4`, a verify batch could under-write positions that a later compression still needed. The host planner also omitted the pad term, so CPU and GPU planner paths could disagree. The merged fix derives the pad from ring capacity and rejects unsupported draft counts at startup instead of permitting silent under-write.

**What we have not done.** We have not reproduced the pre-fix SGLang/DeepSeek-V4 path on Blackwellboy infrastructure or established which released builds besides the source revision carry the defect.

## If you have this stack

Pin the pre-fix build from the PR, use DeepSeek-V4 speculative decoding, and sweep draft counts across the old boundary while checking ring residency and CPU/GPU planner agreement across compression residues. Keep a fixed-build control with the same model and settings.

**CONFIRM.** Draft count 5 or higher causes the pre-fix planner to omit committed tail positions or disagree between planner paths, while the fixed build covers the full committed range.

**REFUTE.** The pinned pre-fix planner already retains every committed speculative position and CPU/GPU plans agree for the reported draft counts and residues.

## Attribution

Reported and fixed upstream by @hnyls2002 in SGLang PR #34189. The registry has not independently reproduced the measurement.