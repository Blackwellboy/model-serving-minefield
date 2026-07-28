# Trap 101: transformers minor version bump silently removes kwarg and breaks model

**Found by Nemo (@NemoSMF).**

**Status: contributor-measured, conditions as reported** (reproduced on a single
gfx1151 machine during image model deployment; the fix is a version pin).

**Symptom.** A model that loaded and ran fine on `transformers==5.5.0` fails
after a minor version upgrade to 5.6.0+ (or 5.14.1). The model loads without
error, then crashes at inference with an `unexpected keyword argument` error for
`input_embeds`, or a `create_causal_mask` import failure. The error points at
the model code, not at the library version — so you debug the model when the
library silently changed its API under you.

**Mechanism.** `transformers` 5.6.0 changed the `create_causal_mask` API and
removed the `input_embeds` kwarg from the forward pass. Models that use either
— including custom attention implementations and some multimodal text encoders
— break at inference time, not at import time. The model loads fine because the
class hierarchy and tokenizer interfaces are unchanged; the break is in the
attention/mask construction path that only runs when a forward pass executes.

**Stacks and builds bitten.** `transformers==5.5.0` → `transformers==5.6.0`
and `transformers==5.14.1`, on a Qwen3-VL text encoder used in an image
generation pipeline (Mage-Flow). gfx1151 (Radeon 8060S), TheRock PyTorch
2.12.0+rocm7.15.0a. The failure was 100% on 5.6.0+ and 0% on 5.5.0.

**The check.**

```bash
python3 -c "import transformers; print(transformers.__version__)"
# If this is >= 5.6.0 and your model uses create_causal_mask or input_embeds,
# you are likely affected.

# Quick probe — does the model's forward pass execute?
python3 -c "
from transformers import AutoModelForCausalLM
import torch
model = AutoModelForCausalLM.from_pretrained('<your-model>', torch_dtype=torch.bfloat16)
# A model that loads but fails here is this trap, not a model bug:
try:
    input_ids = torch.tensor([[1, 2, 3]])
    out = model(input_ids)
    print('forward pass: OK')
except TypeError as e:
    if 'input_embeds' in str(e) or 'create_causal_mask' in str(e):
        print(f'API break: {e}')
    else:
        raise
"
```

**The fix.** Pin `transformers==5.5.0` if your model code uses
`create_causal_mask` or `input_embeds`. Do not let the version float on a
deployment that was tested against a specific version. If you must upgrade,
audit the model code for both kwarg names before proceeding.

```bash
pip install transformers==5.5.0
```

**Found.** 2026-07-22, during Mage-Flow deployment on gfx1151. The model loaded
cleanly and the error surfaced only at the first inference call, initially
appearing to be a model bug.

**Attribution.** Nemo (@NemoSMF). Documented in the
[NemoKnowledgebase gfx1151-gpu-fixes skill](https://github.com/smfworks/NemoKnowledgebase/tree/main/skills/gfx1151-gpu-fixes).