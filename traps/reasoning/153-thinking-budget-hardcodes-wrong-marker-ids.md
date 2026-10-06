# Trap 153: a thinking-budget processor can silently no-op when its marker IDs belong to another tokenizer

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #166](https://github.com/Blackwellboy/model-serving-minefield/issues/166)). Public source and tokenizer files make the mismatch independently checkable; live budget behavior on Qwen3.8 was not claimed.

**Symptom.** A request carries a thinking budget, is accepted, and receives no error or warning, yet the custom processor never finds the expected think marker and therefore applies no cap.

**Mechanism.** SGLang's `Qwen3ThinkingBudgetLogitProcessor` hard-codes Qwen3 marker IDs 151667/151668. The inspected Qwen3.5/3.8-family tokenizer uses different think IDs (248068/248069). The processor scans for the hard-coded open marker; when none is found it silently continues without enforcing the budget. An older helper variant also mixes historical prompt markers with current output when deciding whether a budget is complete.

**Stacks and builds bitten.** SGLang v0.5.17/main custom-logit-processor route; Qwen3.5/3.8-family tokenizers. This does not claim the newer strict-thinking route is affected.

**The check.** Assert the processor's start/end/newline IDs against the served tokenizer before relying on it, then run a bounded-thinking behavioral witness on both fresh and preserved multi-turn/tool histories.

**The fix.** Use marker IDs from the actual tokenizer, or a serving path whose budget implementation is family-aware and validated for the model. Scope counting to the current generated turn.

**Found.** 2026-10, source/tokenizer audit.

**Attribution.** @scottleimroth.
