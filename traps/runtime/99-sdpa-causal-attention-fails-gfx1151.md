# Trap 99: SDPA causal attention fails silently on gfx1151 with async error

**Found by Nemo ([@smfworks](https://github.com/smfworks)).**

**Status: contributor-measured, conditions as reported** (full shape test
matrix and patched attention backend published in the
[gfx1151-gpu-fixes skill](https://github.com/smfworks/NemoKnowledgebase/tree/main/skills/gfx1151-gpu-fixes)).

**Symptom.** A model using `F.scaled_dot_product_attention` with
`is_causal=True` fails with `hipErrorInvalidValue` on gfx1151 (Radeon 8060S /
Strix Halo). The failure is **asynchronous**: the error is reported at the next
GPU operation (typically `torch.cat` or `torch.stack`), not at the SDPA call
itself. The traceback points at the wrong line, so you debug the concatenation
when the actual failure was in attention. Once any kernel fails, all subsequent
GPU operations fail until the process is restarted.

Non-causal SDPA also fails for certain shapes: 16+ heads with head_dim=128, any
shape with head_dim=256, and all fp32 inputs. The `EFFICIENT_ATTENTION` backend
works for small shapes but fails for larger ones. The `MATH` backend fails for
causal but works for non-causal.

**Mechanism.** ROCm's flash attention kernel for gfx1151 does not support causal
attention for any tested shape. This is a kernel coverage gap, not a model
problem — the same model code runs correctly on CUDA. The async error reporting
is a ROCm runtime behavior: the kernel launch returns immediately, the error
surfaces when the next operation synchronizes. This makes the failure look like
a downstream bug rather than an attention kernel issue.

**Stacks and builds bitten.** PyTorch 2.12.0+rocm7.15.0a (TheRock wheels),
gfx1151 (AMD Ryzen AI MAX+ 395 / Radeon 8060S), mainline Linux kernel
7.1.4-070104-generic. Tested shapes and results:

| Shape (b, h, s, d) | dtype | Causal | Result |
|---|---|---|---|
| (1, 8, 32, 64) | bf16 | False | OK |
| (1, 8, 32, 64) | bf16 | True | FAIL |
| (1, 8, 128, 128) | bf16 | True | FAIL |
| (1, 16, 512, 128) | bf16 | False | FAIL |
| (1, 32, 128, 128) | bf16 | False | FAIL |
| (1, 8, 32, 64) | fp32 | False | FAIL |
| head_dim=256 | bf16 | either | FAIL |

The pattern: causal always fails; non-causal fails for large head counts or
head_dim=256; fp32 always fails.

**The check.** Run this on the target GPU — it takes seconds and will tell you
whether SDPA works for causal attention:

```python
import torch, torch.nn.functional as F
torch.cuda.set_device(0)
q = torch.randn(1, 8, 128, 128, device='cuda', dtype=torch.bfloat16)
k = torch.randn(1, 8, 128, 128, device='cuda', dtype=torch.bfloat16)
v = torch.randn(1, 8, 128, 128, device='cuda', dtype=torch.bfloat16)
try:
    out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
    torch.cuda.synchronize()  # CRITICAL: force sync to catch async errors
    print("SDPA causal: OK")
except Exception as e:
    print(f"SDPA causal: FAIL — {e}")
    # The error may not mention SDPA. If it says hipErrorInvalidValue
    # on the synchronize() line, this trap is live on your stack.
```

**The fix.** Replace SDPA with a manual bmm implementation:

```python
import math
def manual_attention(q, k, v, causal=False, scale=None):
    # q, k, v: (seq_len, n_heads, head_dim) — varlen packed format
    q_h = q.transpose(0, 1)  # (h, s, d)
    k_h = k.transpose(0, 1)
    v_h = v.transpose(0, 1)
    if q_h.shape[0] != k_h.shape[0]:  # GQA expansion
        repeat = q_h.shape[0] // k_h.shape[0]
        k_h = k_h.repeat_interleave(repeat, dim=0)
        v_h = v_h.repeat_interleave(repeat, dim=0)
    if scale is None:
        scale = 1.0 / math.sqrt(q_h.shape[-1])
    attn = torch.bmm(q_h, k_h.transpose(1, 2)) * scale
    if causal:
        s_q, s_k = attn.shape[-2], attn.shape[-1]
        mask = torch.triu(torch.ones(s_q, s_k, device=attn.device, dtype=torch.bool), diagonal=1)
        attn = attn.masked_fill(mask, float('-inf'))
    attn = torch.softmax(attn, dim=-1)
    out = torch.bmm(attn, v_h).to(q.dtype)
    return out.transpose(0, 1).contiguous()
```

Keep attention in bfloat16 — float32 upcast doubles memory and causes OOM at
>=1536x1536 resolution on 48 GB UMA.

**Found.** 2026-07-22, during Mage-Flow (image generation model) deployment on
gfx1151.

**Attribution.** Nemo ([@smfworks](https://github.com/smfworks)). Full shape test matrix and the patched
`_sdpa_wrapper` function are published in the
[NemoKnowledgebase gfx1151-gpu-fixes skill](https://github.com/smfworks/NemoKnowledgebase/tree/main/skills/gfx1151-gpu-fixes).
The fix was validated on a 33-test image generation suite.