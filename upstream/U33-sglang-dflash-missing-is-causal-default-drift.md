# U33: missing DFlash causality metadata can change draft semantics after a runtime update

**Reported by @mmangkad.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The compatibility fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #34524 is merged.

**Primary source.** [SGLang PR #34524](https://github.com/sgl-project/sglang/pull/34524), read on 2026-08-25.

**Symptom.** An unchanged DFlash checkpoint can lose speculative acceptance after a runtime update. In the upstream Gemma-4 case, average accept length moved from about 5.62 to about 5.27-5.30 even though the checkpoint itself did not change.

**Mechanism.** The checkpoint did not declare `is_causal`. A runtime change altered the default interpretation of DFlash sliding-attention layers, changing their semantics without a checkpoint edit. The merged fix restores historical layer-specific defaults when metadata is absent while continuing to honor explicit `is_causal=True/False`.

**What we have not done.** We have not reproduced the affected checkpoint/runtime pair on Blackwellboy infrastructure.

## If you have this stack

Pin the affected checkpoint and compare the pre-regression, regressed and fixed runtime behavior. Inspect the resolved attention type for every DFlash draft layer and record acceptance on the same prompts.

**CONFIRM.** The checkpoint omits `is_causal`, the regressed runtime resolves different layer semantics than the historical/fixed control, and acceptance moves with that semantic change.

**REFUTE.** The allegedly affected runtime resolves the same attention semantics as the historical control and the acceptance difference persists for another reason.

## Attribution

Reported and fixed upstream by @mmangkad in SGLang PR #34524. The registry has not independently reproduced the measurement.