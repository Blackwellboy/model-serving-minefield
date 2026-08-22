# U19: sharing JIT caches across nodes can turn compile races into bad binaries

**Reported by @antoniohlc; integrated by @tonyd2wild.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The source recipe changed its default cache layout in merged PR #28.

**Issue state: closed, fixed.** The source recipe now keeps JIT/workspace caches node-local.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #28](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/28), read on 2026-08-21; the merged change credits issue #27 / @antoniohlc.

**Symptom.** A multi-node deployment with weights on NFS produces apparently unrelated startup or runtime failures: a `torch.compile` directory-creation race, DeepGEMM `runtime != nullptr` from a half-written cubin, or one rank loading a FlashInfer binary built by the other rank. The error messages do not point at the shared cache as the common cause.

**Mechanism.** The deployment placed seven JIT/workspace cache paths under the Hugging Face cache tree. Sharing `HF_CACHE` over NFS is sensible for large model weights, but it also made both ranks compile into the same writable directories. Concurrent or version-divergent writes can expose partially-written or ABI-incompatible artifacts to the peer. The source report calls out an especially opaque case where `FLASHINFER_DISABLE_VERSION_CHECK=1` allows an ABI-mismatched `sampling.so` to load without the normal version guard.

The source fix separates weights from generated code: weights may remain shared, while the JIT tree moves to a node-local `JIT_CACHE_DIR` / volume on every rank.

**What we have not done.** We have not reproduced the race on our fleet or established that every network filesystem behaves identically. The claim is specifically about writable generated-code/workspace caches shared by multiple compiler processes, not read-only weight sharing.

## If you have this stack

On a disposable two-node lane, record every compiler/JIT cache path and inode/mount backing it. Run a clean simultaneous warm-up with those paths shared and save compile logs and hashes of generated binaries. Repeat after moving only generated-code/workspace caches to node-local storage while leaving model weights shared. Do not reuse artifacts between arms.

**CONFIRM.** The shared-JIT arm exhibits cross-rank write races, partial artifacts, or rank-to-rank binary/ABI contamination that disappears when generated caches are node-local while the shared weights remain unchanged.

**REFUTE.** The supposedly affected stack uses per-node cache paths already, or repeated clean shared-cache builds produce atomic, identical artifacts with no cross-rank race or load failure.

## Attribution

Reported by @antoniohlc and incorporated by @tonyd2wild in merged PR #28. The registry has not independently reproduced the behavior.
