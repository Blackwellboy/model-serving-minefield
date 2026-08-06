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

## Update 2026-07-28: R2-29 is no longer blocked

Nemotron weights reached a lane, both members named by the candidate were
served, and R2-29 was tested. It is
[refuted as worded and reframed](2026-07-28-r2-29-tool-calls-refuted-as-worded.md):
the leaked format is nested XML rather than JSON, and on vLLM the ordinary path
is protected by a hard HTTP 400 when the tool-parser flags are missing, so the
plain claim is unreachable there. The other three candidates on this page remain
blocked for the reasons stated above.

## Correction 2026-07-28: R2-23 is not a vLLM defect, and this page implied it was

This page records the VL reranker candidate as blocked for want of reranker
weights, with the test being to "score fixed pairs against Transformers". That
test is written to confirm a serving defect, and **the upstream thread does not
report one.**

The issue was read in full during the
[round-2 classification pass](2026-07-28-r2-queue-classified-upstream-tier.md).
It closes with the **reporter** stating that the scores were correct once the
chat template was supplied, the model had been served without one, and that a
**hand-copied** Jinja file still misbehaved where a **downloaded** one did not.
No maintainer ever confirmed a scoring bug, because the resolution arrived
first.

The candidate was ranked seventh of fifty on the strength of a summary line
nobody had checked against the thread. It stayed that way for months.

What is real here is a usage trap with a silent-wrong signature, and it is
published as
[U10](../upstream/U10-vllm-vl-reranker-without-chat-template.md): a scoring
path has no natural correctness signal, so a reranker assembled with the wrong
prompt returns confident, well-formed, near-reversed numbers. The
weights-blocked status is unchanged, we still hold none, but the thing to
test is now the template arms, not vLLM against Transformers.

## Correction 2026-07-28: R2-27's blocker was worded wrongly

This page recorded the Mistral tokenizer-mode candidate as blocked for want of
Mistral weights. That is not the blocker, and stating it that way implied the
candidate would unblock the moment a Mistral checkpoint appeared. It would not.

Two independent reasons, established on llama.cpp `b9878`:

1. **The flag is hard-rejected.** llama.cpp exits with an invalid-argument error
   on the tokenizer-mode flag. There is no code path to exercise, with or
   without weights.
2. **A GGUF is the wrong artifact regardless.** Conversion to GGUF discards the
   native tokenizer that the flag exists to select, so even a Mistral GGUF could
   not test the thing the candidate is about.

The candidate is therefore **llama.cpp-inapplicable**, not weight-blocked. It
remains open against a stack that implements the flag, which is vLLM with the
original safetensors checkpoint, and a Mistral GGUF arriving does not change
that. Recorded during the fourth-stack coverage pass, which served exactly such
a GGUF and could not have tested it.
