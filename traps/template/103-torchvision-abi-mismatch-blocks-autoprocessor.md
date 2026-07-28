# Trap 103: torchvision ABI mismatch silently blocks AutoProcessor on ROCm

**Found by Nemo ([@smfworks](https://github.com/smfworks)).**

**Status: contributor-measured, conditions as reported** (reproduced on a single
gfx1151 machine during image model deployment; the fix is a code-level
fallback).

**Symptom.** A multimodal model's text encoder fails at processor initialization
with an `ImportError` for torchvision. The model loads, the tokenizer loads, but
`AutoProcessor.from_pretrained` fails because torchvision cannot be installed.
The error message says "Torchvision is required" or similar, and `pip install
torchvision` either fails or installs an incompatible version. The model appears
broken at a late stage of initialization, after weights have loaded.

**Mechanism.** TheRock ROCm wheels for PyTorch 2.12 use a custom ABI that is
incompatible with the torchvision wheels on PyPI. `AutoProcessor` (used by
Qwen3-VL and other multimodal models) requires torchvision for image/video
processing. On ROCm with TheRock wheels, torchvision cannot be installed without
an ABI mismatch. The model code calls `AutoProcessor.from_pretrained` which
hard-imports torchvision, and the import fails. This is not a model bug — the
text-only path works fine with `AutoTokenizer` — but the code does not have a
fallback.

**Stacks and builds bitten.** Qwen3-VL text encoder (used in Mage-Flow image
generation), TheRock PyTorch 2.12.0+rocm7.15.0a, gfx1151 (Radeon 8060S),
`transformers==5.5.0`. The failure was 100% without the fallback patch and 0%
with it.

**The check.**

```python
try:
    import torchvision
    print("torchvision:", torchvision.__version__)
except ImportError as e:
    print(f"torchvision unavailable: {e}")
    # If you are on ROCm with TheRock wheels, this is expected.
    # Your model's AutoProcessor call will fail unless you patch it.

# Test whether AutoProcessor specifically needs torchvision:
from transformers import AutoProcessor
try:
    proc = AutoProcessor.from_pretrained("<your-model>")
    print("AutoProcessor: OK")
except ImportError as e:
    if "Torchvision" in str(e) or "torchvision" in str(e):
        print(f"AutoProcessor blocked by torchvision: {e}")
```

**The fix.** Patch the text encoder to fall back to `AutoTokenizer` when
`AutoProcessor` fails due to a torchvision ImportError:

```python
try:
    self.processor = AutoProcessor.from_pretrained(version, local_files_only=is_local)
except ImportError as e:
    if "Torchvision" in str(e):
        import logging
        logging.warning(f"AutoProcessor failed (torchvision missing); "
                        f"falling back to AutoTokenizer: {e}")
        self.processor = AutoTokenizer.from_pretrained(version, local_files_only=is_local)
    else:
        raise
```

This works because the text encoder only needs the tokenizer component of the
processor; the image/video processing components are not used in the text
encoding path.

**Found.** 2026-07-22, during Mage-Flow deployment on gfx1151. The error
surfaced after model weights loaded successfully, initially appearing to be a
model loading bug.

**Attribution.** Nemo ([@smfworks](https://github.com/smfworks)). The patched fallback is documented in the
[NemoKnowledgebase gfx1151-gpu-fixes skill](https://github.com/smfworks/NemoKnowledgebase/tree/main/skills/gfx1151-gpu-fixes).