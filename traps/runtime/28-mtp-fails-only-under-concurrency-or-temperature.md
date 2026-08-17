# Trap 28: MTP speculative decoding passes your bench and fails only under concurrency or temperature

**Found by @jasl, @baonudesifeizhai, and @yongfuFang (upstream issues).**

**Status: reported by others** (three upstream issues on distinct failure
modes, one verified fixed on main by its reporter); not independently
reproduced here.

**Symptom.** The MTP lane is green: it loads, single-stream benches run,
temperature-0 probes answer correctly. Then production traffic arrives
and the server hangs at concurrency above 1, or crashes with a KeyError
when temperature sits between 0 and 1, or dies with CUDA invalid argument
on a parallel layout the smoke test never used. It looks like flaky
hardware or a flaky model; it is a speculative path that was never
exercised on the axes production actually uses.

**Mechanism.** The MTP speculative path has scheduling and sampling edge
cases that single-stream, greedy, default-layout testing cannot reach:
concurrent batch scheduling
([vllm #41402](https://github.com/vllm-project/vllm/issues/41402),
DeepSeek-V4-Flash MTP hang at `vllm bench serve` concurrency > 1 on
v0.20.0, 4x B200 with tensor parallel and `num_speculative_tokens=2`, reporter later verified fixed on main). **That one has a signature worth
recognising, because a reader arrives holding the log line rather than the
title:** the server logs `No available shared memory broadcast block found in
60 seconds` on repeat, throughput falls to near zero with requests still marked
running, and there is no Python exception and no CUDA traceback at all. A hang
with no traceback reads as dead hardware or a wedged interconnect. It was a
scheduling path., sampling-parameter
handling in the (0, 1) temperature range under data-parallel serving
([vllm-ascend #8724](https://github.com/vllm-project/vllm-ascend/issues/8724),
KeyError, triaged upstream), and parallel-layout initialization
([vllm #45099](https://github.com/vllm-project/vllm/issues/45099), CUDA
invalid argument during profile_run with DP4 + EP). Different bugs, one
lesson: speculative acceptance is multi-axis, and every axis you did not
test is unverified.

**Stacks and builds bitten.** DeepSeek-V4-Flash with MTP on vLLM v0.20.0
(hang; fixed on later main) and on vllm-ascend w8a8 MTP under DP
concurrent serving (KeyError); DP4 + EP layouts (CUDA invalid argument).
Version- and layout-scoped throughout.

**The check.** Before trusting any MTP lane, a twenty-minute matrix:
concurrency {1, 8} crossed with temperature {0, 0.7} on short prompts,
plus one run in the exact parallel layout production will use. A lane is
not "up" until the cell your users will actually hit is green.

**The fix.** Pin the engine version that passes your matrix, re-run the
matrix on every upgrade, and record the tested cells next to any MTP
throughput number. [Trap 11](11-speculative-depth-peak-and-collapse.md)
already requires sweeping speculative depth; this entry adds that depth
is not the only axis, and that single-stream greedy is the least
representative cell in the space.

**Found.** 2026-07-27 (mined from upstream).

**Attribution.** @jasl
([vllm #41402](https://github.com/vllm-project/vllm/issues/41402)),
@baonudesifeizhai
([vllm #45099](https://github.com/vllm-project/vllm/issues/45099)),
@yongfuFang
([vllm-ascend #8724](https://github.com/vllm-project/vllm-ascend/issues/8724)).
Related entries:
[trap 11](11-speculative-depth-peak-and-collapse.md) (the depth axis),
[trap 14](../versioning/14-finetune-reupload-not-drop-in.md) (drafter
artifacts differ across re-uploads).
[trap 122](122-full-cuda-graph-corrupts-qwen38-mtp-verification.md) is a distinct
single-stream Qwen3.8/vLLM 0.27.1 failure: its discriminator is FULL versus
PIECEWISE CUDA-graph mode, not concurrency, temperature, or parallel layout.
