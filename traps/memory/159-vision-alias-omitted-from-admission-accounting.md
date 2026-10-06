# Trap 159: a vision namespace alias can be loaded correctly but omitted from admission byte accounting

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #178](https://github.com/Blackwellboy/model-serving-minefield/issues/178)). The missing-byte behavior is reproducible with a CPU/synthetic control; no live OOM or image-quality claim is made.

**Symptom.** A compatibility patch that removes an NVFP4+vision guard can make startup admission undercount the retained vision tower even though the loader later recognizes and loads that tower namespace.

**Mechanism.** TensorFold Python 0.6.0's vision reader accepts both `vision_tower.*` and original `model.visual.*` aliases, but the resident-tower byte transform counted only `vision_tower.*`. The NVFP4 language transform separately excludes `model.visual.*`. Under the original namespace, the composed accounting therefore returns zero resident tower bytes.

**Stacks and builds bitten.** TensorFold Python 0.6.0 commit `c464617...`, dense NVFP4 Qwen-family compatibility work. Stock 0.6.0 separately rejects the combination; this entry is about guard-removal compatibility patches, not released-stock admission behavior.

**The check.** Feed identical synthetic shapes through the byte transform under both aliases and require equal nonzero accounting. Also verify a complete synthetic tower and keep a control for the renamed namespace.

**The fix.** Reuse the loader's existing shared vision-key alias predicate in the resident-byte transform, preserving rank/enabled checks. Later TensorFold 0.6.5 already recognizes the aliases.

**Found.** 2026-10, source-preserving vision compatibility audit.

**Attribution.** @scottleimroth.
