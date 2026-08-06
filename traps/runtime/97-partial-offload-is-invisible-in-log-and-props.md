# Trap 97: partial GPU offload costs 22 to 31 times decode, and neither the server log nor `/props` names the split

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, llama.cpp `b9878-2da668617` serving a
Mistral-family Q8_0 GGUF of unstated provenance, `-c 8192 -np 1 -fa on --jinja`,
on one consumer GPU with ample free VRAM at every setting.

**Evidence pointer.** Three lanes differing only in `-ngl`, plus a grep of each
lane's own log.

**Symptom.** A lane is slow. Nothing in the server's output says why. The model
gets blamed, or the quantisation, or the card.

## Measured

Median server-reported throughput, n=4 requests each, `cache_prompt: false`:

| `-ngl` | decode tok/s | prefill tok/s | decode vs full | GPU memory used |
|---|---|---|---|---|
| 999 (full) | 83.34 | 2447.5 | 1.00x | 20364 MiB |
| 16 | 3.81 | 180.1 | **0.046x (21.9x slower)** | 16102 MiB |
| 8 | 2.71 | 127.6 | **0.033x (30.8x slower)** | 14078 MiB |

A 22 to 31-fold decode regression, from one flag, with no failure and no
warning.

## The part that makes it a trap

**No introspection surface on this build names the offload split.**

- **The server log does not.** Grepping each lane's own log for
  `offload|layer|CPU|CUDA|buffer|ggml` returned **zero** matching lines, at the
  default verbosity, which reports itself as 3. A direct foreground run with
  stderr captured also returned zero. The entire ggml-level load report that
  upstream llama.cpp has historically printed, meaning layers offloaded,
  per-device buffer sizes and the device table, is absent from this build's
  output. The device banner does appear from `--version`, so the information
  exists in the binary; it is not reaching the server's log stream.
- **`/props` does not.** Checked for `n_gpu_layers`, `gpu_layers`, `ngl`,
  `device`, `offload`, `n_layer`, `split`: **none present.** The full top-level
  key set is `bos_token, build_info, chat_template, chat_template_caps,
  cors_proxy_enabled, default_generation_settings, endpoint_metrics,
  endpoint_props, endpoint_slots, eos_token, is_sleeping, media_marker,
  modalities, model_alias, model_path, total_slots, ui, ui_settings`, and
  `default_generation_settings` carries only `n_ctx` and `params`.

So a lane can be running 3% of its achievable decode rate and report nothing
anomalous through any endpoint it offers. The claim this refines is usually
worded as users "not noticing" partial offload. On this build it is stronger
than that: **there is nothing to notice.**

## Memory used is not a usable proxy either

The tempting check is to compare GPU memory against the file size. It does not
work. The file is 7.3 GiB, and the `-ngl 8` lane, with almost the entire model
on the CPU, still occupied **14078 MiB**, because KV cache and compute buffers
dominate at this context size. Memory occupancy stayed within 31% across a
31-fold performance range. A monitor keyed on "is VRAM use roughly model size"
passes all three of these lanes.

## What actually detects it

Decode throughput itself, compared against a known-good full-offload figure for
the same file and flags. That requires having recorded such a figure, which is
the practical recommendation: **capture decode tok/s at full offload once, per
file per lane, and treat it as the reference.** Absent that reference there is
no signal on this build, which is the finding.

If the launch command is reachable, read `-ngl` off the process arguments rather
than asking the server: it is the only place the value is reliably visible.

## Scope

llama.cpp `b9878-2da668617`, one Mistral-family Q8_0 GGUF of unstated
provenance, one consumer GPU, `-c 8192 -np 1`. The absent logging and the absent
`/props` fields are server-build properties, not model properties; the
multipliers are specific to this file, this context size, and this hardware, and
are quoted to show the order of magnitude rather than as a portable constant.
Other builds may well print the offload report, so the check to run is the grep
above, not an assumption either way. No capability claims, no comparison of
models.

**Related.** [Trap 87](87-llamacpp-props-reports-per-slot-context.md) is the
other half of what `/props` will and will not tell you on this build.
[Trap 52](../evaluation/52-speed-measured-on-a-broken-config.md) is the mirror
case, where the configuration was fast because it was wrong rather than slow
because it was misconfigured.

**Found.** 2026-07-28, second coverage pass on this file.
