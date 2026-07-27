# R2-27 / R2-23 / R2-10 / R2-29: not testable on current lanes

**Date:** 2026-07-27. Availability verified read-only on both test nodes
(disk listings plus python import checks). No downloads, no new serve
processes, per session rules. Recorded so anyone with the missing piece can
run the test.

| Candidate | Needs | Missing here | To test it |
|-----------|-------|--------------|------------|
| R2-27 Mistral tools need tokenizer-mode mistral | vLLM plus any Mistral checkpoint | No Mistral weights anywhere on the test nodes | Download a small Mistral (e.g. Small 3.x) and serve twice, with and without --tokenizer-mode mistral |
| R2-23 VL reranker wrong scores | vLLM plus Qwen3-VL-Reranker plus a Transformers baseline env | No reranker weights, no VL model on either node | Download reranker, serve once, score fixed pairs against Transformers |
| R2-10 SGLang reasoning parser forces null content | SGLang install plus small Qwen | SGLang not installed on either test node (ModuleNotFoundError both) | pip/uv install sglang in a scratch env, serve a small Qwen with and without --reasoning-parser qwen3 |
| R2-29 Nemotron NVFP4 tools raw JSON | Nemotron-3-Super NVFP4 served on DGX Spark class hardware | No Nemotron weights on either node | Fetch NVFP4 build, serve with and without --enable-auto-tool-choice plus parser flags |

Adjacent data point for R2-10 recorded in passing: on both vLLM test lanes
the reasoning parser puts reasoning in reasoning_content and keeps content
populated or tool_calls structured (see the
[R2-39 note](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md)).
The null-content symptom is claimed for SGLang specifically and remains
untested.
