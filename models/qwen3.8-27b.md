# Qwen3.8-27B — RTX 5090 and DGX Spark notes

First-party serving coverage collected on 2026-08-14/15 across RTX 5090 and
DGX Spark GB10 systems. This page is intentionally **symptom-first**: it tells
you what failed, what turned out not to be a model failure, and what to check
before changing weights or blaming Qwen.

Full sanitized evidence note:
[2026-08-15 Qwen3.8-27B 5090/Spark audit](../mining/2026-08-15-qwen38-27b-5090-spark.md).

## What was actually exercised

| path | measured state |
|---|---|
| `unsloth/Qwen3.8-27B-GGUF` Q4_K_M, llama.cpp `9402`, RTX 5090 | live generation exercised; one decimal canary failed then passed on immediate repeat |
| `Qwen/Qwen3.8-27B` BF16, aeon-vLLM `0.25.0+aeon.sm121a.dflash`, DGX Spark | full recovered 2-hour mixed-workload soak: 512/512 requests, zero server restarts, zero canary failures |
| `Qwen/Qwen3.8-27B-FP8`, same aeon runtime, DGX Spark | serving campaign progressed through the Spark lane; do not read stage bookkeeping as a blanket quality score |
| `unsloth/Qwen3.8-27B-NVFP4`, same aeon runtime, DGX Spark | live serving exercised; campaign classified the aeon MTP stage as unsupported |
| same NVFP4 revision, Drowzeys vLLM development image, DGX Spark | model loaded with `FlashInferCutlassNvFp4LinearKernel`; MTP-off and MTP1 canaries passed in the captured early reproduction |
| SGLang nightly arm64 image, DGX Spark | runtime preflight only; Qwen3.5-family/NVFP4 code was present but exact weights were not staged, so **no inference claim** |

## Qwen3.8-27B troubleshooting leads

These are deliberately L-series leads rather than invented canonical claims.
They are public because they can save somebody time now; the evidence label
tells you how much certainty to attach to them.

| Lead | If you see this | First check |
|---|---|---|
| **L043 — MTP support is runtime/build-specific** | one Qwen3.8 runtime says MTP unsupported | pin the exact image/build and inspect its Qwen MTP implementation before declaring the model unsupported |
| **L044 — amd64 benchmark image on arm64 Spark** | benchmark dies with `exec format error` before the endpoint is touched | compare host architecture with every helper/benchmark image |
| **L045 — Docker ID differs after save/load** | transferred runtime image appears to have a different local image ID | compare immutable layer/config fingerprints, not local `.Id` equality alone |
| **L046 — image ENTRYPOINT eats `/model` as a subcommand** | container prints `Usage: serve ... No such command '/model'` | inspect `Entrypoint`, `Cmd`, `--help`, and the final argv passed by your launcher |
| **L047 — telemetry thread crashes at join** | long soak serves requests but worker dies during teardown | inspect harness thread lifecycle before calling endpoint instability |
| **L048 — one decimal canary flips on immediate repeat** | a single simple correctness probe fails on Q4 | capture exact sampling/request payload and repeat before calling quant corruption |

## The most important Qwen3.8-specific lesson so far

**Do not turn a runtime capability result into a model capability result.**

The same NVFP4 checkpoint revision was labelled `MTP_UNSUPPORTED` by the aeon
Spark lane, while a different pinned vLLM development image exposed the
Qwen-family MTP implementation and passed the depth-1 canary. That does not
prove every MTP depth or build works. It does prove that “Qwen3.8 cannot do
MTP” would have been the wrong conclusion.

This is the same general class of mistake as:

- [trap 09 — image choice changes the outcome](../traps/runtime/09-image-choice-changes-outcome.md),
- [trap 10 — quant label is not the kernel path](../traps/quantization/10-quant-label-is-not-the-kernel-path.md),
- [trap 52 — speed measured on a broken config](../traps/evaluation/52-speed-measured-on-a-broken-config.md), and
- [trap 112 — process liveness is not model readiness](../traps/runtime/112-process-liveness-is-not-model-readiness.md).

## Canonical RTX 5090 MTP/CUDA-graph trap (contributor-measured)

A separate public contribution from **ayayalar (A Y)** adds canonical
[Trap 122](../traps/runtime/122-full-cuda-graph-corrupts-qwen38-mtp-verification.md)
for `unsloth/Qwen3.8-27B-NVFP4` on one RTX 5090 with vLLM 0.27.1. This is not a
Blackwellboy reproduction and should retain its published status:
**contributor-measured, conditions as reported**.

The important discriminator is graph mode. Static MTP under FULL capture silently
collapsed output while keeping HTTP 200 / normal finish reasons; keeping MTP on
but forcing PIECEWISE via dynamic speculative decoding restored correct output.
The contributor also reproduced the FULL-graph collapse with fp8 KV, so the
canonical owner is the graph-mode/spec-verify interaction, not "4-bit KV is
broken". Use the three-arm FULL / PIECEWISE / no-spec check in Trap 122 before
attributing a similar symptom to this mechanism.

## A useful non-result: vision

The campaign repeatedly marked vision stages unsupported on text baselines.
That is **not a trap** and should not be presented as a Qwen failure. If your
chosen Qwen3.8 artifact is text-only or has no mounted/projector path, a vision
probe is non-applicable. Check the exact checkpoint and modality artifacts
rather than treating an unsupported stage as a regression.

## A useful research-stack result: the 2-hour BF16 soak

One BF16 Spark soak crashed because the Python telemetry thread subclass used
`self._stop` for a `threading.Event`, shadowing the inherited
`threading.Thread._stop()` method. That failure occurred in the harness teardown
path. After renaming it to `_stop_event`, the recovered run completed roughly
two hours with:

- 512 requests / 512 successes;
- zero recorded server restarts;
- zero failures in the periodic exact canaries;
- reported VRAM 17,465 MiB at both start and end.

The point is not the number. The point is that **a benchmark worker can fail
while the served model remains healthy**. Preserve server/request evidence
separately from harness exit status.

## Before reporting a new Qwen3.8 issue

Record all of these together:

- exact model repo and revision;
- quantization/format;
- GPU/device class and architecture;
- runtime/image digest and runtime revision;
- effective kernel/backend for the relevant path;
- exact provider-bound request and sampling settings;
- whether failure happened before model load, at load, first forward, prefill,
  decode, benchmark scoring, or harness teardown;
- one bounded confirmation and one bounded refutation check.

A failure before the endpoint is reached is not a model failure. A failure in
one runtime does not automatically generalize to another. And one bad canary
is evidence of a bad response, not automatically evidence of a broken quant.

## Reasoning-template configuration traps (2026-08-15)

Independently reproduced by Blackwellboy on
`RadixArk/Qwen3.8-27B-NVFP4@52d1adc` (template SHA `c3cf9e34…`). Prior
public lead: TheTom/offlabel.

| if you see this | first check | entry |
|---|---|---|
| “default thinking” numbers look like max effort | dump rendered prompt; unset effort may be **xhigh** | [trap 03](../traps/reasoning/03-enable-thinking-default-drift.md) |
| `reasoning_effort=medium` “works” but depth looks wrong | medium has **no** instruction branch on this pin | [trap 07](../traps/reasoning/07-reasoning-effort-silently-ignored.md) |
| multi-turn prompt tokens explode when replaying assistant history | `preserve_thinking` defaults **true** and replays `reasoning_content` | [trap 04](../traps/template/04-history-reasoning-stripping.md) |
| empty `<think></think>` pairs in history | content-only priors still wrap empty think blocks under default preserve | [trap 25](../traps/template/25-empty-think-blocks-poison-prefix-cache.md) |

Offline check:
[`checks/reproduce_qwen38_reasoning_config_traps.py`](../checks/reproduce_qwen38_reasoning_config_traps.py).

Mining note:
[2026-08-15 Qwen3.8 reasoning-config traps](../mining/2026-08-15-qwen38-reasoning-config-traps.md).
