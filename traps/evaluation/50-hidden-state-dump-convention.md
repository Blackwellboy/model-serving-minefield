# Trap 50: hidden-state dump conventions differ, manufacturing a "final-layer norm explosion"

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Symptom.** A per-layer parity harness reports, for a 52-layer model:

> *L51 cosine 0.747; our norm 552 vs reference 124; we are ~4.5x off, the final norm is broken.*

A real bug report gets filed against a correct implementation.

**Mechanism.** Two convention mismatches stacked, and neither is documented anywhere but the source.

1. **Off-by-one layer index.** The shipped custom modeling file appends hidden states at the **top**
   of the layer loop (`all_hidden_states += (hidden_states,)` before each block runs; the post-block
   append is commented out). So `hs[0]` is the embedding, `hs[i]` for i=1..51 is the *input* to
layer
   i, i.e. the **output of layer i-1**: and `hs[51]` is appended after the loop. Our dump emits
   output-of-layer-`l`. Therefore **ours `layerL`  maps to  reference `layer(L+1)`**.
2. **Pre-norm vs post-norm.** The reference's final entry is **post** final-norm; our last layer
dump
   is **pre** final-norm. Comparing them is meaningless.

The "explosion" was entirely an artifact of comparing a pre-norm state against a post-norm one at
the
wrong index.

**Stacks and builds bitten.** HuggingFace `trust_remote_code` custom modeling files, where
`output_hidden_states` semantics are set by the shipped file rather than by stock transformers.
Observed on a Nemotron-H hybrid; the pattern applies to any model whose modeling file was written by
hand.

**The check.** Three, cheapest first:

1. **Count the dumps.** The reference produced **53** entries for **52** layers. That mismatch alone
   is the tell, and it costs nothing to check.
2. **Check norms against theory.** RMSNorm maps any input to about `||weight||`. Here
   `||norm_f.weight|| = 124.99`, so *every* post-norm state lands at ~125 **by construction**. The
   reference's dramatic 567 to 124 "drop" is just the norm being applied. If a "collapse" lands
   exactly on `||weight||`, it is not a collapse.
3. **Apply your own final norm before comparing.** Ours: raw L51 = 552.1; after applying `norm_f` =
   **120.7**, against the reference's 123.7 (on a *different prompt*).

After fixing the offset, the two implementations tracked **within ~3%** across the whole stack:

| backbone layer output | reference | ours |
|---|---|---|
| 49 | 452.5 | 452.3 |
| 50 | 566.8 | 582.3 |
| post-final-norm | **123.7** | **120.7** |

match, tries both index alignments, and reports which one is consistent.

**The fix.** Fix the **harness**, not the model: align `ours[L]` to `ref[L+1]`, and apply the final
norm to your last layer before comparing it to the reference's final entry (or dump a post-norm
state as an extra entry).

**Second-order trap in the same investigation.** The remaining final-logits cosine of **0.9297**
against a **bf16** reference is also not a defect. bf16 is imprecise for RMSNorm over outlier
activations; our forward was f32 and therefore *closer to ground truth*, so cosine-vs-bf16
**penalizes accuracy**. Better gates, in order:

1. Run the reference in **f32**: the only valid per-layer parity check.
2. **Top-k logit overlap** (token + index agreement), matters more than cosine.
3. **Softmax KL divergence**: distribution shape despite value shift.
4. Downstream task metric, if the f32 path beats bf16 on task, the "divergence" is a win.

**Found.** 2026-06-12.

**Attribution.** TheTom.

**Check script.** The runnable version of this check is in review separately: every check in this repo must declare the negative and empty-set controls described in [the check contract](../../checks/README.md), and this one does not yet. The assertion above is the check; the script is a convenience wrapper for it.
