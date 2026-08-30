# U39: ModelOpt NVFP4 checkpoints can emit invalid byte-token sequences while HTTP and throughput stay healthy

**Reported by @shing100.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: none.** The vLLM issue is open and currently has no maintainer resolution.

**Issue state: open.** The report explicitly leaves the causal boundary unresolved.

**Primary source.** [vLLM issue #54150](https://github.com/vllm-project/vllm/issues/54150), including its cross-reference comment, read on 2026-08-30.

**Symptom.** On RTX PRO 6000 Blackwell / SM120, two ModelOpt-produced GLM-5.3 NVFP4 conversions reportedly emit invalid UTF-8 byte-token sequences during generation while the server returns HTTP 200, throughput looks normal and ordinary English can remain mostly readable. The reporter exposed the failure with Korean text and counted U+FFFD replacement characters.

The report checked returned token IDs directly: decoding those IDs offline with the checkpoint tokenizer reproduced the same replacement-character count, so the observed symptom was not only an API/client detokenization artifact. In the reported six-run rows, two ModelOpt checkpoint families showed replacement characters while a compressed-tensors NVFP4 conversion of the same model stayed clean under the same image, kernel, KV layout, TP and sampling controls.

**Causal boundary.** The issue does **not** establish that vLLM's ModelOpt loader is the root cause. The two checkpoint families differ in both conversion artifact and loader path, so the report leaves two live explanations: the ModelOpt conversions may carry damaged weights, or the vLLM ModelOpt NVFP4 path may be wrong for this case. The issue also records separate sustained-load instability on ModelOpt NVFP4 in #52540, but that is a different symptom and cannot be merged into this entry without a shared cause.

**What we have not done.** We have not reproduced the invalid token-ID behavior on Blackwellboy infrastructure, and we have not performed the dequantized-tensor comparison needed to distinguish damaged weights from loader execution.

## If you have this stack

Pin the exact vLLM image/build and one ModelOpt NVFP4 checkpoint plus a matched compressed-tensors control. Use deterministic multi-byte-language prompts, request returned token IDs where available, and decode those IDs offline with each checkpoint's own tokenizer. Hold attention backend, KV layout, TP, MTP, sampling and prompt constant. Then compare representative dequantized tensors or logits across loader paths if the artifact provenance permits it.

**CONFIRM.** The ModelOpt arm repeatedly emits token-ID sequences that decode to invalid UTF-8/replacement characters while the matched compressed-tensors arm is clean, and the bad sequence is present in returned token IDs rather than introduced by client rendering.

**REFUTE.** The pinned ModelOpt checkpoint remains clean across the same deterministic probes, or the apparent corruption disappears when the same returned IDs are decoded offline.

A loader-root-cause claim requires an additional control: the same underlying quantized tensor content must differ only by loader execution, or a tensor/logit comparison must localize the divergence to the loader path.

## Attribution

Reported by @shing100 in vLLM issue #54150. The registry has not independently reproduced the measurement and does not choose between damaged-checkpoint and loader-path explanations.
