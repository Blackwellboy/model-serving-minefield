# R2-39: thinking plus tools yields empty output (scoped non-reproduction on vLLM)

**Candidate:** mining round 2, R2-39 (Ollama Qwen3 issue 10976: thinking=true
plus tools together yields empty output; either alone works).

**Verdict here:** DOES NOT REPRODUCE on vLLM. Stack-scoped: the claimed
mechanism is Ollama-side; nothing model-side produces the combo failure.

**Date:** 2026-07-27. Request-level probes only, no serve-config changes.

## Test surface

| Lane | Model | Stack |
|------|-------|-------|
| DGX Spark test lane A | Qwen3.6-35B-A3B-NVFP4 (nvidia upload) | vLLM 0.23.1rc1.dev223+ga346d589f (vllm-openai:nightly), max_model_len 262144 |
| DGX Spark test lane B | laguna-s-2.1-tr3-hybrid | vLLM 0.25.2.dev0+g752a3a504.d20260714 (custom hybrid image), max_model_len 200000 |

## Probe

Full matrix per lane: chat_template_kwargs.enable_thinking in {true,false} x
tools in {present,absent}, n=5 prompts per cell, temperature 0, max_tokens
2048. Tools were a get_time/calculator pair. Empty output defined as: content
empty AND no tool_calls AND reasoning empty.

## Results (counts per 5)

| Lane | Cell | tool_calls fired | empty output |
|------|------|------------------|--------------|
| Qwen3.6-35B | think=on, tools | 5/5 | 0/5 |
| Qwen3.6-35B | think=on, no tools | n/a | 0/5 (one finish=length cap-hit with 5206 chars reasoning: trap 12/22 class, not this candidate) |
| Qwen3.6-35B | think=off, tools | 5/5 | 0/5 |
| Qwen3.6-35B | think=off, no tools | n/a | 0/5 |
| laguna hybrid | think=on, tools | 5/5 | 0/5 |
| laguna hybrid | think=on, no tools | n/a | 0/5 |
| laguna hybrid | think=off, tools | 5/5 | 0/5 |
| laguna hybrid | think=off, no tools | n/a | 0/5 |

Every think=on plus tools request returned finish_reason=tool_calls with a
well-formed call. No cell produced the both-empty symptom.

## Side observation

On the laguna hybrid lane, think=on plus tools suppressed reasoning in 4/5
requests (reasoning length 0) while think=on without tools always produced
reasoning. Consistent with the known reasoning-suppression-under-tool-turns
behavior for this family; logged, not this candidate.

**CAVEAT (2026-07-28).** The phrase "the known
reasoning-suppression-under-tool-turns behavior for this family" overstates
what is established. The observation above is n=5 on one lane, and the
suppression reading it leans on has since been narrowed twice:

- Depth: the tool-schema depth collapse does not survive in-run interleaved
  control (all pairwise p >= 0.13; the tools arm carried the highest median).
  What produces short reasoning on tool turns is truncation at the tool
  boundary, not a suppression dial. A turn that exits via `tool_calls` has a
  structurally shorter reasoning episode because it stops to call the tool.
- Firing: @apollo-mg published an apparatus cell at n=492 (HumanEval+ 164 x
  K=3, Laguna S 2.1 UD-Q2_K_XL under llama.cpp on 4x Tesla P100 sm_60, a
  752-byte agent system prompt plus 3 tool schemas) with thinking firing on
  445/492 samples (90.4%) and mean reasoning_content of 4,686 chars
  (offlabel PR #10 comment 5093534067, 2026-07-27). Tool schemas present did
  not close the gate at scale on that stack.

Read the 4/5 above as a small-n lane observation with reasoning length
measured at a tool boundary, not as evidence for a family-wide suppression
behavior. Credit @apollo-mg.

## Scope of this negative

This tests the model-plus-vLLM path only. The cited mechanism lives in
Ollama request handling, and neither lane runs Ollama. Correct registry
framing if promoted later: an Ollama-specific serving trap, not a Qwen model
trap. Ollama-side confirmation still needed before any registry entry.

Evidence: 55-row probe log (both R2-39 and R2-31 probes) plus doctor JSON
for both lanes, archived with the maintainers; available on request.
