# U29: unified memory + Triton + deterministic inference can mix virtual and physical KV ids

**Reported by @ch-wan.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #33517 is merged.

**Primary source.** [SGLang PR #33517](https://github.com/sgl-project/sglang/pull/33517), read on 2026-08-25.

**Symptom.** `--enable-unified-memory` plus Triton attention plus deterministic inference can produce garbage/NaN logits. Any two of the three conditions are clean. With async assertions armed the failure aborts; without them the upstream report says the run can complete locally, making the corruption much easier to miss.

**Mechanism.** The deterministic one-stage Triton extend kernel read the prefix from translated physical KV locations but the just-written extend half from untranslated virtual locations. The merged fix reuses the already-computed physical translation for the extend read.

**What we have not done.** We have not reproduced this three-way SGLang configuration on Blackwellboy infrastructure.

## If you have this stack

Pin the pre-fix build and compare unified vs static pools with deterministic inference and Triton pinned. Then remove one condition at a time. Capture token ids and output logprobs, not only HTTP success.

**CONFIRM.** The pre-fix three-way configuration diverges or produces NaN/garbage while the static-pool control and the one-condition-removed controls remain clean; the fixed build restores parity.

**REFUTE.** The pinned pre-fix unified path is token/logprob-equivalent to the static-pool path under all three reported conditions.

## Attribution

Reported and fixed upstream by @ch-wan in SGLang PR #33517. The registry has not independently reproduced the measurement.