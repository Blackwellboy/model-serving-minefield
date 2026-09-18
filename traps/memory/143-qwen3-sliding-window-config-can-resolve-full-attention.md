# Trap 143: a Qwen3 config can declare a sliding window while every layer resolves to full attention

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported.** The contributor found the mismatch while exporting a five-layer DFlash draft. Blackwellboy independently reproduced the core config-class mechanism without GPU execution against `transformers==5.12.1`; the same two gates were also source-confirmed on current Transformers during adjudication.

**Symptom.** A Qwen3-family `config.json` visibly contains a numeric `sliding_window`, yet the effective reconstructed model configuration can resolve every layer to `full_attention`. Small draft models are particularly easy to hit because the default window-transition layer can sit beyond the end of the model. Nothing has to raise or warn.

**Mechanism.** `Qwen3Config` has two independent gates.

First, the effective numeric window is nulled unless sliding-window use is enabled:

```text
sliding_window = sliding_window if use_sliding_window else None
```

`use_sliding_window` defaults to false on the pinned implementation. A config that only declares `sliding_window=2048` therefore loses the effective window.

Second, when explicit `layer_types` are absent, the pinned derivation assigns `sliding_attention` only when the layer index is at or beyond `max_window_layers`. That value defaults to 28. A five-layer model has indices 0 through 4, so even with `use_sliding_window=true`, leaving `max_window_layers=28` resolves all five layers to `full_attention`.

A declared config key is therefore not proof of the per-layer architecture the runtime reconstructs.

**Stacks and builds bitten.** Independently reproduced on the configuration-only path with `transformers==5.12.1`, Python 3.11 on Ubuntu 24.04, with PyTorch intentionally absent. The contributor encountered the same class while exporting a five-layer Qwen3.8-family DFlash draft. This entry promotes the Transformers config-class mechanism; a separate NVIDIA ModelOpt exporter gating observation is corroborating context, not required for this canonical claim.

**The check.** Reconstruct the config and inspect the effective per-layer types rather than reading the raw `sliding_window` key.

For a small positive/negative fixture:

```python
from transformers import Qwen3Config

bad1 = Qwen3Config(num_hidden_layers=5, sliding_window=2048)
bad2 = Qwen3Config(num_hidden_layers=5, sliding_window=2048, use_sliding_window=True)
good1 = Qwen3Config(num_hidden_layers=5, sliding_window=2048, use_sliding_window=True, max_window_layers=0)
good2 = Qwen3Config(num_hidden_layers=5, sliding_window=2048, use_sliding_window=True, layer_types=["sliding_attention"] * 5)
```

On the pinned implementation, both `bad1` and `bad2` resolve all five layers to `full_attention`; `good1` and `good2` provide all-sliding positive controls.

**TRAP PRESENT:** the serialized/raw configuration appears to request sliding-window attention but reconstructed effective `sliding_window` / `layer_types` do not match the intended architecture.

**TRAP ABSENT:** reconstruction produces the intended per-layer attention types/window pattern, and an assertion verifies that pattern before export or serving.

**The fix.** Encode the effective architecture explicitly and assert it after reconstruction. For an all-sliding five-layer model on the pinned derivation, `max_window_layers=0` works; explicit `layer_types` is safer when the intended architecture is known. Hybrid models should use their actual transition index or explicit per-layer list.

Do **not** use `max_window_layers=num_hidden_layers` as a generic all-sliding fix. On a five-layer model, `max_window_layers=5` leaves indices 0 through 4 below the threshold, so every layer still resolves to full attention.

**Claim boundary.** May claim that the two structural Qwen3 config gates are independently reproducible on Transformers 5.12.1 and can silently turn a declared sliding-window config into all-full-attention on a small model. Must not claim that every Qwen3-family checkpoint is misconfigured, that a specific served checkpoint suffers a quality regression without checking its resolved configuration, or that the separate ModelOpt exporter path is required for this mechanism.

**Attribution.** Discovery/export-path finding: **@scottleimroth**. Independent T0 config reproduction, correction and registry framing: Blackwellboy. Public report: [issue #107](https://github.com/Blackwellboy/model-serving-minefield/issues/107).
