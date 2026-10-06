# Trap 148: two engines can serialize identical tool JSON into different prompt tokens

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #156](https://github.com/Blackwellboy/model-serving-minefield/issues/156)).

**Symptom.** Two engines receive byte-identical OpenAI chat requests but report different prompt-token counts, and borderline greedy long-context outcomes diverge between them.

**Mechanism.** On the measured lanes, one rendering path preserved non-ASCII characters in tool JSON while another matched `json.dumps(..., ensure_ascii=True)`. Ninety non-ASCII characters expanded into Unicode escapes and added about 394 prompt tokens. The request was identical on the wire; the model input was not.

**Stacks and builds bitten.** TensorFold 0.3.6.3 and a vendor SGLang v0.5.17-era lane, Qwen3.8-27B-family NVFP4, long agent prompts with 36 tool schemas. The exact escaping layer in stock SGLang was not established, so do not generalize the engine attribution.

**The check.** Render the checkpoint template locally with the served tokenizer, compare verbatim and `ensure_ascii=True` tool serialization counts, then compare both with each engine's reported prompt tokens. Include an ASCII-only control.

**The fix.** Treat rendered prompt identity as part of an engine A/B. Normalize or pin tool serialization when comparing engines, and never infer equivalence from request-body equality alone.

**Found.** 2026-09, cross-engine long-context qualification.

**Attribution.** @scottleimroth.
