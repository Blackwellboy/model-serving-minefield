# vLLM, especially with reasoning models

**Measured here:** yes (the primary serving lane here)


**53 entries name vLLM** in their evidence surfaces (see
[how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)),
which makes it the most-covered stack here and also the one where a count is
least meaningful. Below is the shortlist that matters.

## The three checks to run first

**1. Prove you have a render path, and use it.** Almost every entry on this
page is settled by looking at the assembled prompt rather than the response.
`POST /v1/chat/completions/render` returns `token_ids` and `POST /detokenize`
converts them back to text; `POST /tokenize` with `return_token_strs: true`
also works. Then run the marker probe from
[trap 04](../traps/template/04-history-reasoning-stripping.md): a three-turn
conversation whose first assistant message carries a unique reasoning marker,
rendered and grepped. [`checks/preflight_template.py`](../checks/preflight_template.py)
automates it.

**2. Assert one structured tool call.** One request with one tool defined must
return a `tool_calls` array, not prose. If you get prose, the model-specific
`--tool-call-parser` is the first suspect, not the model
([trap 19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md)). And if
reasoning arrives unparsed no matter which `--reasoning-parser` you name, the
parser may ship inside the checkpoint and be bundled with no serving stack
([trap 70](../traps/runtime/70-in-repo-parser-not-bundled.md)).

**3. Find the runtime tell for your kernel path.** Read `config.json`'s quant
schemes rather than the repo name, then confirm against something the engine
did: its backend-selection log, decode throughput against an f16 baseline, or
utilisation against power draw. The manifest establishes the **label**, never
the path
([trap 10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md)).

## The five that bite hardest here

| Entry | What it does to you |
|---|---|
| [04, prior-turn reasoning stripped from history](../traps/template/04-history-reasoning-stripping.md) (**Core**) | Multi-turn measures a model that cannot see its own thinking, and the result is publishable rather than broken. On vLLM the write field that survives is `reasoning` ([trap 20](../traps/reasoning/20-reasoning-write-field-name-diverges.md)) |
| [10, the quant label is not the kernel path](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) (**Core**) | An FP4 checkpoint routes to a weight-only fallback and is far slower than the format promises. Head of a four-entry family with [45](../traps/quantization/45-fa-all-quants-cpu-fallback.md), [46](../traps/versioning/46-stale-build-missing-arch-kernel.md) and [90](../traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md) |
| [63, one correct round-trip shape out of four](../traps/reasoning/63-reasoning-round-trip-one-correct-shape.md) | The preservation gate can be named `truncate_history_thinking`, where **true means discard**, so a pipeline standardised on the other polarity silently no-ops |
| [47, prefix caching silently auto-disabled](../traps/runtime/47-prefix-caching-autodisabled-hybrid.md) | On hybrid and recurrent architectures the engine turns it off and says so once, at startup, and every agent turn re-prefills the whole conversation |
| [61, an advertised window that fails silently](../traps/evaluation/61-advertised-window-fails-silently.md) (**Core**) | Advertised, trained and served context are three numbers; a 1M window over a 64K trained base accepts the prompt, counts it exactly, and answers from nowhere near the start |

## Also worth knowing on this stack

- [08](../traps/runtime/08-image-toolchain-newer-than-driver.md) and
  [09](../traps/runtime/09-image-choice-changes-outcome.md): the container
  image decides the kernel path, and the unit under test is image plus weights
  plus hardware plus build. Pin the digest.
- [62](../traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md):
  a speculative-decode drafter configuration that garbles the markup dialect,
  with the known-good configuration published as a table.
- [122](../traps/runtime/122-full-cuda-graph-corrupts-qwen38-mtp-verification.md):
  on one contributor-measured Qwen3.8 / vLLM 0.27.1 RTX 5090 lane, FULL
  CUDA-graph capture silently corrupts MTP verification while PIECEWISE is
  clean; verify graph mode explicitly before blaming the KV dtype.
- [57](../traps/reasoning/57-thinking-kwarg-truthiness-coercion.md) and
  [58](../traps/reasoning/58-reasoning-effort-injects-hidden-preamble.md): the
  thinking kwarg evaluated for truthiness so `"false"` turns it on, and
  `reasoning_effort` as an undocumented thinking switch that also injects a
  hidden preamble.
- [80](../traps/runtime/80-reasoning-parser-batches-sse-deltas.md): a reasoning
  parser batching the stream, so delta timings describe its flush schedule.
- [67](../traps/template/67-history-rendered-as-object-repr.md) and
  [68](../traps/template/68-multimodal-part-order-discarded.md): message
  content normalised to a list and rendered as its repr, and content-part
  order discarded.

## Full serving paths written up

[DeepSeek-V4-Flash on two DGX Spark nodes](../models/deepseek-v4-flash.md) is
the one end-to-end vLLM serving path with its own page.

The [per-model index](../models/README.md) carries the rest.
