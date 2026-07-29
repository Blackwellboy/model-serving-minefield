# Traps by serving stack

One page per stack: the five entries most likely to bite you there, and the
three checks to run before anything else. This is reorganisation, not new
material. Every claim on these pages is published in the entry it links.

**Two columns, and the difference between them is the point.** *Entries* are
measured: somebody ran it. *Upstream-reported* entries are from
[`upstream/`](../upstream/), where **nobody here has reproduced anything**:
they are credited reports from other people's trackers, published so a reader
with the stack can settle them. They never count as coverage and they are never
added to the first column.

| Stack | Page | Entries naming this stack | Upstream-reported |
|---|---|---|---|
| vLLM | [vllm.md](vllm.md) | 51 | 3 |
| llama.cpp and GGUF | [llama-cpp.md](llama-cpp.md) | 34 | 0 |
| Ollama | [ollama.md](ollama.md) | 9 | 5 |
| mlx_lm | [mlx.md](mlx.md) | 9 | 1 |
| HF transformers `generate()` | [hf-transformers.md](hf-transformers.md) | 7 | 0 |
| SGLang | [sglang.md](sglang.md) | 3 | 3 |
| TensorRT-LLM | [tensorrt-llm.md](tensorrt-llm.md) | 0 | 0 |
| text-generation-inference | [text-generation-inference.md](text-generation-inference.md) | 0 | 0 |
| TabbyAPI, ExLlamaV2/V3 | [tabbyapi.md](tabbyapi.md) | 0 | 0 |
| LM Studio | [lm-studio.md](lm-studio.md) | 1 | 0 |
| text-generation-webui | [text-generation-webui.md](text-generation-webui.md) | 0 | 0 |

The four stacks at zero measured entries have pages that say so and then do the
only useful thing left: name **which of our mechanism classes most likely
apply and why**, with the measured entry each class comes from, and how a
reader would test for them. A page saying "we have not tested this, here is
what to check" narrows a stranger's search without claiming anything. Absence
of a page did not.

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
- The LM Studio count of 1 is **inherited, not measured**: trap
  [24](../traps/template/24-official-template-breaks-cpp-jinja.md) names it as
  an environment the C++ Jinja portability defect applies to, and that entry
  was measured on llama.cpp. Its page says so. Similarly, five entries name
  **EXL3** as a quantization format and none of them names TabbyAPI or
  ExLlamaV2 as the server, which is why the TabbyAPI row is 0 rather than 5.
- A low count means **nobody has reported here**, not that a stack is clean.
  Every stack now has a page, including the four that have nothing first-party
  to show, because "no page" and "no entries" read identically from outside
  and mean different things. HF transformers has seven entries and not one of
  them measured here on that stack. Its page says so at the top.

  **Corrected 2026-07-28:** this paragraph previously said that no server had
  been started on SGLang for this registry. That stopped being true when
  SGLang was brought up first-party on our own hardware, and
  [CONTRIBUTING](../CONTRIBUTING.md#where-coverage-is-thin) was corrected at
  the time while this page was not. A later contributor field run now gives the
  stack three published evidence surfaces in traps 02, 12 and 77; the count is
  of those published entries, not of the still-unpublished first-party session.

## The rest of the map

[Per-model and per-stack index](../models/README.md) has the full model-family
table and the stack-level rows, including layers that are not serving stacks
(eval harnesses, process managers, container images, agent clients).

[Playbooks](../playbooks/) route by the job you are doing rather than by what
you are running.
