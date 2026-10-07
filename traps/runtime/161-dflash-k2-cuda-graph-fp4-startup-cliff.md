# Trap 161: a lower DFlash draft budget can be a hard startup failure, not a safer operating point

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #105](https://github.com/Blackwellboy/model-serving-minefield/issues/105)).

**Symptom.** A downward speculative-depth sweep looks healthy at draft budgets 8, 6 and 4, then budget 2 never reaches health at all. The failure happens during startup CUDA-graph capture and the traceback points at FP4 quantization / tensor contiguity, which makes the checkpoint or quantization path look guilty.

**Mechanism.** On the reported SGLang DFlash2 + NVFP4 lane, budget 2 failed **8/8** attempts during the draft worker's decode CUDA-graph initialization with `self must be contiguous` from the FP4 quantization path. The matched controls at budgets 4, 6 and 8 reached health and completed **24/24** arms. The only deliberately varied setting was `--speculative-num-draft-tokens`.

That proves a build-scoped **k=2 startup cliff**. It does **not** prove why depth 2 produces a non-contiguous input. The traceback establishes where the failure surfaces, not the tensor-shape transition that owns it. Current-source inspection also found no universal validation that forbids k=2 and no global `.contiguous()` repair before FP4 quantization.

**Stacks and builds bitten.** Contributor report: SGLang dev build with DFlash2 support, CUDA 13, aarch64/sm121, NVFP4 27B target and NVFP4 five-layer DFlash2 drafter on GB10. Contemporaneous reports from the same public DFlash2 lane identify SGLang `0.0.0.dev1+g5f55db35e` / image `lmsysorg/sglang:dev-cu13-qwen38-27b-dflash2`; issue #105 itself did not preserve an immutable failing-container digest, so treat that identity as supporting context rather than proof of the exact failing image.

**The check.** Treat startup as a measured cell. For each candidate draft budget, launch a fresh serve and require it to reach `/health` before running any benchmark. Preserve the full startup traceback and record **DID NOT COME UP** as its own outcome. Do not coerce that cell to zero throughput or silently drop it from a curve.

**The fix.** On the affected lane, do not use draft budget 2. Use a budget that passes startup and then benchmark quality/performance normally. If root-cause work is needed, instrument the tensor immediately before the failing FP4 call with shape, stride and `is_contiguous()` under matched k=2 and k=4 arms.

**Boundary.** This is not a general claim that DFlash budget 2 is invalid, nor that FP4 checkpoints are broken. It is a deterministic startup cliff on the reported build/model/drafter combination. The depth-to-layout mechanism remains unproven.

**Found.** 2026-09, speculative-depth sweep.

**Attribution.** @scottleimroth.
