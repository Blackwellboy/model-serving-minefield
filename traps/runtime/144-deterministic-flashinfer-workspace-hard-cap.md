# Trap 144: deterministic FlashInfer can hard-cap prefill workspace and kill long prompts

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #87](https://github.com/Blackwellboy/model-serving-minefield/issues/87)). The runtime failure was measured by the contributor; the exact historical source side effect is independently inspectable at SGLang commit `5f55db35e`.

**Symptom.** A SGLang serve passes short benchmarks and then the whole process dies on a sufficiently long fresh prompt with a FlashInfer allocation error. Increasing `SGLANG_FLASHINFER_WORKSPACE_SIZE` appears ineffective.

**Mechanism.** On the reported build, deterministic mode sets fixed split sizes and executes `SGLANG_FLASHINFER_WORKSPACE_SIZE.set(2048 * 1024 * 1024)`, overriding the environment value. Long-prefill workspace demand can exceed that fixed 2 GiB. The threshold depends on model geometry and batching; it is not a universal token count.

**Stacks and builds bitten.** SGLang `0.0.0.dev1+g5f55db35e` / commit `5f55db35e`, FlashInfer attention, Qwen3.8-27B NVFP4 family, DGX Spark GB10. Current SGLang no longer carries this exact 2 GiB setter, so this is a historical/version-scoped trap.

**The check.** Pin the serving build, inspect the deterministic branch for a workspace-size setter, then compare matched deterministic-on/off long-prefill requests while recording the required workspace bytes. Do not infer safety from short prompts.

**The fix.** On the affected build, remove the deterministic FlashInfer path or use a deterministic backend/path that does not hard-set this workspace. Verify long prompts after the change. Do not treat the reported ~7.3k-token boundary as portable.

**Found.** 2026-09, production long-prompt failures and source follow-up.

**Attribution.** @scottleimroth. Maintainer source pinning and version-boundary adjudication: Blackwellboy.
