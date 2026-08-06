# SGLang on aarch64 + GB10 (sm_121) + CUDA 13: feasibility, not infeasibility

**Verdict: NOT infeasible, and the packaging layer is clear.** This note exists
because the honest output of the check was the opposite of what was expected,
and a negative that goes the other way is still information.

[CONTRIBUTING](../CONTRIBUTING.md#where-coverage-is-thin) names SGLang as a
stack with no entries at all. The first question anyone asks is whether it can
even run on this hardware class. It can, as far as packaging is concerned.

**Install and serve were deliberately not attempted**, and that is a scope
statement rather than a result: `sglang[all]` resolves to roughly a 10 GB
install with a real risk of a long tail, and the session had other work
committed. What follows is what was established and the exact next step, so the
next person starts from here rather than from zero.

**Target.** aarch64, NVIDIA GB10 (compute capability **12.1**), driver
580.159.03, CUDA **13.0**, Ubuntu 24.04, Python 3.12.

## Established

**1. `sgl-kernel`, the usual binding constraint, ships an aarch64 wheel.**

```
sgl_kernel-0.3.21-cp310-abi3-manylinux2014_aarch64.whl   626.6 MB
```

Downloaded successfully for this exact platform (`pip download --no-deps`, exit
0). `abi3` covers Python 3.12. This is the piece that most often has no arm64
build. It does here.

**2. `sglang[all]` resolves completely.** `pip install --dry-run` exits 0 with a
full plan: `sglang-0.5.16`, `torch-2.11.0`, a complete CUDA 13 wheel set
(`nvidia-cuda-runtime-13.0.96`, `nvidia-cublas-13.1.0.3`, `nvidia-nccl-cu13`,
`nvidia-cudnn-cu13`, `cuda-toolkit-13.0.2`, `nvidia-cuda-nvcc-13.3.73`), plus
`flashinfer-python`, `triton-3.6.0` and `flash-attn-4`. No resolution conflict,
no source-only package, no missing platform tag. It brings its own `nvcc`, so
the absence of a system CUDA toolkit is not a blocker.

## The real open risk, named precisely

**sm_121 is not in the arch list of the torch build this stack pulls.** The
node's working torch reports:

```
torch 2.11.0+cu130   cuda 13.0   arch_list ['sm_80','sm_90','sm_100','sm_110','sm_120']
```

GB10 is **sm_121**, which is absent. That is the same shape as
[trap 76](../traps/runtime/76-device-rejection-log-line-is-not-fatal.md), where
a bundled runner rejects GB10 for exactly this reason and a later one accepts
it, and the same shape as
[trap 08](../traps/runtime/08-image-toolchain-newer-than-driver.md). vLLM serves
fine on this node, so the combination is workable. Whether SGLang's own kernels
are compiled for sm_121, fall back, or fail at JIT is precisely what an install
would answer, and this pass did not.

Second, smaller risk: no checkpoint on the node was known to be SGLang-loadable,
so a test would likely need a different model.

## Exact next step

About an hour and 15 GB of disk:

```bash
python3 -m venv ~/sglang_test && . ~/sglang_test/bin/activate
pip install 'sglang[all]'
python -c "import sgl_kernel, torch; print(torch.cuda.get_arch_list())"
python -m sglang.launch_server --model-path <small-safetensors-model> --port 30000
```

The single question to answer first is whether `sgl_kernel` loads and dispatches
on sm_121, or produces the CUDA-13 PTX-version class of error already documented
for this hardware. That is a five-minute check once installed, and it decides
whether the rest is worth doing.

*Status: measured here, raw not published, and scoped to packaging only. No
SGLang server was started, so nothing here is a claim about SGLang's behaviour.*
