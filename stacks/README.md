# Traps by serving stack

One page per stack: the five entries most likely to bite you there, and the
three checks to run before anything else. This is reorganisation, not new
material. Every claim on these pages is published in the entry it links.

| Stack | Page | Entries naming this stack |
|---|---|---|
| vLLM | [vllm.md](vllm.md) | 51 |
| llama.cpp and GGUF | [llama-cpp.md](llama-cpp.md) | 34 |
| Ollama | [ollama.md](ollama.md) | 9 |
| mlx_lm | [mlx.md](mlx.md) | 9 |
| HF transformers `generate()` | [hf-transformers.md](hf-transformers.md) | 7 |
| SGLang | [sglang.md](sglang.md) | 0 |

## How those counts were derived, and what they do not mean

An entry counts for a stack when the stack is named in that entry's **evidence
surfaces**: its title, finder or status lines, its "Stacks and builds bitten"
section, a section heading, or a bolded paragraph lead-in. A passing
cross-reference in the middle of prose does not count.

Two honest limits on the numbers:

- The rule cannot tell a stack that was **bitten** from a stack named as the
  **contrast or the fix**. Trap [24](../traps/template/24-official-template-breaks-cpp-jinja.md)
  and trap [41](../traps/runtime/41-static-batching-buys-power-not-throughput.md)
  both count toward vLLM, and in both the vLLM mention is the working path
  rather than the defect. Read the count as "entries that have something to
  say about this stack", not "defects in this stack".
- A low count means **nobody has reported here**, not that a stack is clean.
  Every stack now has a page, including the two that have nothing first-party
  to show, because "no page" and "no entries" read identically from outside
  and mean different things. SGLang has zero entries and a
  [feasibility note](../mining/2026-07-28-sglang-on-gb10-feasibility.md);
  HF transformers has seven entries and not one of them measured here on that
  stack. Both pages say so at the top.

  **Corrected 2026-07-28:** this paragraph previously said that no server had
  been started on SGLang for this registry. That stopped being true when
  SGLang was brought up first-party on our own hardware, and
  [CONTRIBUTING](../CONTRIBUTING.md#where-coverage-is-thin) was corrected at
  the time while this page was not. The results of that session are written
  and awaiting publication; the count above stays at zero until they land,
  because the count is of published entries.

## The rest of the map

[Per-model and per-stack index](../models/README.md) has the full model-family
table and the stack-level rows, including layers that are not serving stacks
(eval harnesses, process managers, container images, agent clients).

[Playbooks](../playbooks/) route by the job you are doing rather than by what
you are running.
