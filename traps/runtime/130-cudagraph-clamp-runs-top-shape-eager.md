# Trap 130: the CUDA-graph capture-size clamp silently runs your largest decode shape eager

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Measured on the
finder's private 2x DGX Spark (GB10) lane on 2026-08-12 during a spec-depth
A/B. Blackwellboy has not independently reproduced this lane. Counts and
conditions below; raw logs are private.

**Symptom.** The startup log says CUDA graphs captured FULL, yet the
full-concurrency decode shape behaves like eager: the biggest batch pays
capture, launch and scheduling overhead with no graph. A one-token change in
speculative depth (or a one-request change in `max_num_seqs`) flips the
behavior with no error anywhere. The flag you set is not the number that
governs.

**Mechanism.** vLLM caps CUDA-graph capture at a fixed size list (on this
build `[1, 2, 4, 8, 16, 24]`) and truncates the effective maximum to the
largest list entry at or below the requested value. Many serve lines compute
the requested value as `max_num_seqs x (spec_tokens + 1)`. When that product
exceeds the clamp, the full-batch decode shape is never captured and runs
eager while smaller shapes get graphs. The effective list is printed once, at
startup, and never again.

**Stacks and builds bitten.** vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), tensor parallel 2, two DGX Spark
(GB10) nodes, stock DeepSeek-V4-Flash-0731, DSpark speculative decoding.
Measured: with `--max-num-seqs 4` and 6 draft tokens the requested capture
size is 28, and the engine clamps to 24 (`cudagraph_capture_sizes:
[1,2,4,8,16,24]`), so the 4-way decode shape runs eager; with 5 draft tokens
the product is `4 x 6 = 24`, lands exactly on the clamp, and FULL capture
completes. The resulting spec-depth A/B on code generation: k=6 to k=5 moved
steps/s +7.4% (14.52 to 15.60), tokens/step -9.9% (5.596 to 5.040), net tok/s
81.3 to 78.6 (-3.4%), with per-component spreads non-overlapping across five
runs per arm, so the step-rate gain was graph coverage and the token yield
loss was the dropped draft position.

**The check.** Grep the startup log for "Capturing CUDA graphs" and the
effective `cudagraph_capture_sizes` list. Compare the largest list entry
against the value passed to the capture-size flag (or recompute it as the
serve line does). If the flag value exceeds the last list entry, your largest
decode shape is eager, and no later log line will tell you.

**The fix.** Choose the spec depth (or `max_num_seqs`) so
`max_num_seqs x (spec_tokens + 1)` lands exactly on the clamp, and verify
from the log, not from the flag you set. Do not tune the two independently:
capture size is their product, and a `max_num_seqs` change silently retrades
draft depth for graph coverage.

**Found.** 2026-08-12, while running the spec-depth A/B the recipe's own
numbers had motivated.

**Attribution.** @sethforprivacy. This is the clamp mechanism, and is distinct
from [122](122-full-cuda-graph-corrupts-qwen38-mtp-verification.md), where
FULL capture corrupts the speculative verification on another build.

**Related.** [122](122-full-cuda-graph-corrupts-qwen38-mtp-verification.md), [11](11-speculative-depth-peak-and-collapse.md), [28](28-mtp-fails-only-under-concurrency-or-temperature.md), [46](../versioning/46-stale-build-missing-arch-kernel.md).
