# U37: ModelOpt NVFP4 can emit invalid byte-token sequences while a compressed-tensors control stays clean

**Reported by @shing100.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: none.**

**Issue state: open.**

**Primary source.** https://github.com/vllm-project/vllm/issues/54150 , read on 2026-09-13.

**Symptom.** The public report describes replacement characters in generated multilingual text on two ModelOpt NVFP4 checkpoint families while a compressed-tensors NVFP4 control of the same model stayed clean under the matched serving lane. Offline decoding of returned token IDs showed the same corruption, so the report is not limited to client text rendering.

**Mechanism boundary.** The source does not settle whether the converted weights are damaged or the ModelOpt loading/runtime path is responsible. This entry preserves that uncertainty and does not claim a universal ModelOpt defect.

**Reported conditions.** GLM-5.3-Flash on Blackwell-class hardware, TP4, vLLM development build `0.1.dev20051+g487ecf187`, with the matched control described in the source issue.

**What we have not done.** We have not reproduced this on Blackwellboy infrastructure and have not independently localized the responsible component.

## If you have this stack

Run one pinned ModelOpt NVFP4 conversion and one pinned compressed-tensors NVFP4 conversion of the same base model under matched server and prompt settings. Compare API text and an offline decode of returned token IDs.

**CONFIRM.** The ModelOpt arm repeatedly shows the invalid byte-token sequence while the matched compressed-tensors control stays clean, including in offline token-ID decoding.

**REFUTE.** The corruption disappears on the same pinned ModelOpt arm, follows only the client renderer, or reproduces equally on the matched control.

## Attribution

Reported and measured publicly by **@shing100** in vLLM issue #54150. The registry has not independently reproduced it.
