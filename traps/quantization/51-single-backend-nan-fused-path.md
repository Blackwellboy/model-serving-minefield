# Trap 51: single-backend NaN is a backend bug, not a quantization-quality result

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Symptom.** Perplexity comes back **NaN** for a 4-bit quantized model on one backend, and is clean
on the others with the **same file**. The natural conclusion. "this quant format doesn't work on
this architecture", kills a format that in fact works.

**Mechanism.** The Metal backend used a **fused "rotate-activation" matmul**: it forward-rotates
activations in place (randomized Hadamard), dequantizes weights **without** the inverse rotation,
and
un-rotates afterwards. That path NaNs on a **squared-ReLU FFN**, while `Q8_0` on Metal with
identical
activations is clean, so it is the fused path, not generic fp16 overflow. The CPU path
(dequant-to-float with inverse RHT) and the CUDA path (warp-cooperative dequant-to-float-with-WHT)
are safe by construction.

**Stacks and builds bitten.** A TurboQuant fork of llama.cpp (`ggml-metal-ops.cpp` fused TQ matmul),
`TQ4_1S` weights, `Nemotron-H-8B-Base-8K` (Mamba-2 hybrid with a squared-ReLU FFN). Transformer
models with GELU/SwiGLU FFNs on the same path are unaffected, which is why it survived so long.

**The check.** Run perplexity on **every backend you have** before drawing a conclusion about a
quant
format, and bisect by tensor group rather than by guess:

```bash
# 1. all three backends, same file
llama-perplexity -m out.gguf -f ppl_small.txt -c 512 -ngl 0                 # CPU
TQ_NO_ROTATE=1 llama-perplexity -m out.gguf -f ppl_small.txt -c 512         # Metal, toggle on
llama-perplexity -m out.gguf -f ppl_small.txt -c 512                        # CUDA

# 2. bisect: hold one tensor group high-precision at quantize time
llama-quantize in.gguf probe.gguf TQ4_1S --tensor-type ssm=q8_0
```

Holding the SSM tensors at `Q8_0` **still NaN'd**, which ruled out the SSM and pointed at the FFN.

| backend | PPL (wikitext, ctx 512) |
|---|---|
| CPU | 7.0190 |
| Metal, default | **NaN** |
| Metal, `TQ_NO_ROTATE=1` | 7.0072 |
| CUDA sm_121, default | 7.0037 |
| `Q8_0` baseline | 6.8211 |

Three-backend agreement to ~2 decimal places is the pass condition. The real result: **+2.9% PPL for
a 40% smaller file** (8.0 GB to 4.8 GB; bf16 was 16.2 GB), a good outcome that a single-backend run
would have reported as a total failure.

**The fix.** A guarded, opt-in env toggle. `TQ_NO_ROTATE=1`: forcing the standard
with-inverse-rotation `mul_mm` on that backend. No default behavior change, so Transformer models on
the fast fused path are untouched. Use it on Metal; the default is correct on CPU and CUDA.

**Pipeline traps found alongside**, each of which silently produces a *wrong file* rather than an
error:

- The converter that supports the architecture may not live in the checkout that has the quant
  format. Convert with one, quantize with the other; reversing this yields a file that loads and is
  wrong.
- **Stock `gguf-py` cannot read the exotic type**: the reader throws on the unknown type in
  `_build_tensors`. Expected; validate with the fork's own `llama-*` binaries, not `gguf-py`.
- `dyld: Symbol not found: common_init_from_params` means your binaries are stale relative to the
  library. Rebuild the targets; do not debug the model.

**Found.** 2026-07-02, on the first application of this quant recipe to a Mamba-2 hybrid.

**Attribution.** TheTom.
