# Trap 126: Ling `thinking:false` can keep reasoning enabled and spill the trace into `content`

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #58](https://github.com/Blackwellboy/model-serving-minefield/issues/58)). The contributor measured the free-text and structured-output controls on DGX Spark; Blackwellboy has not independently reproduced this lane.

**Symptom.** Setting `chat_template_kwargs: {"thinking": false}` on a Ling-3.0-flash free-text request does not produce the expected faster/non-reasoning path. Token cost stays essentially unchanged, while the reasoning trace is delivered at the front of `content` and a stray `</think>` separates it from the user-facing answer. The same toggle behaves differently when the request asks for structured JSON output.

**Mechanism.** On the reported Ling serving path, `thinking:false` in ordinary free-text does not suppress the model's reasoning work; it changes where the generated trace is separated. The contributor's short control measured 81 completion tokens with thinking on versus 80 with thinking off for the same task, while the off response contained the combined reasoning-plus-answer text in `content`. Under `response_format: {"type": "json_object"}`, the same flag did suppress the extra reasoning work and reduced the measured completion from 33 tokens to 12. The important boundary is therefore response-shape dependent on this stack: a toggle accepted by the API is not one stable semantic contract across free text and structured output.

**Stacks and builds bitten.** `inclusionAI/Ling-3.0-flash-int4` on inclusionAI's `vllm-ling-v3` fork (reported branch `ling_3_0`, Ling-3 reasoning parser), NVIDIA DGX Spark / GB10, aarch64, served using the DGX-Spark Ling recipe referenced by the contributor. The contributor also notes that stock vLLM is not a valid control for this model family because that route silently produces incorrect output; this entry is scoped to the working inclusionAI fork path they measured.

**The check.** Send the same small free-text prompt twice with every other request field frozen: once with thinking enabled and once with `thinking:false`. Compare completion tokens and inspect both `content` and the reasoning field. A failing lane shows near-equal token work while the off arm moves reasoning text into `content` with a dangling close tag. Then repeat the same pair under `response_format: {"type": "json_object"}`. If the structured arm becomes materially cheaper/clean while free text does not, the toggle is response-shape dependent rather than globally broken.

**The fix.** On the measured free-text path, do not use `thinking:false` as a latency/cost optimization and do not assume it guarantees clean answer-only `content`. Prefer the working reasoning-on separation for ordinary text, or use the structured-output path when its semantics fit the application and its off behavior has been verified. If a client must consume the broken free-text off path, treat the visible reasoning prefix/`</think>` as a parser defect to fail or sanitize, not as model answer content.

**Found.** 2026-08-23 while benchmarking Ling-3.0-flash on DGX Spark.

**Attribution.** @scottleimroth. Original measured report and controls: [issue #58](https://github.com/Blackwellboy/model-serving-minefield/issues/58). Related: [Trap 02](../template/02-orphaned-think-close-tag.md) for the close-tag symptom, [Trap 29](29-server-reasoning-off-is-not-an-off-switch.md) for a different off-switch contract failure, and [Trap 64](64-answer-lands-in-reasoning-on-toggle-conflict.md) for the opposite field-placement failure.
