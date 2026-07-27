# Trap 24: the official template is written for Python Jinja, and your engine is not Python

**Found by barubary and froggeric (community template fixes; issue filed by @blockoracle).**

**Status: reported by others** (official-template construct verified
directly by us in the shipped template file; the breakage reports and the
fixes are community work, not independently reproduced here).

**Symptom.** Tool calling is "completely broken" on llama.cpp or LM Studio
with the model's official chat template: schemas never render, argument
keys go missing, or the template errors out, while the same weights with
the same template work on vLLM. Swapping in a community "fixed" template
restores tools without touching the model. It looks like a model quality
gap between runtimes; it is a template engine gap.

**Mechanism.** Official templates are written and tested against Python
Jinja2. C++ Jinja implementations (llama.cpp's engine, LM Studio) support
a different subset with different semantics, so constructs that are legal
upstream silently misrender downstream. Verified directly: the official
`Qwen/Qwen3.5-35B-A3B` chat template uses the `|items` filter, a
Python-side construct that community fix lists specifically target. The
21-fix community template
([QwenLM/Qwen3 #1831](https://github.com/QwenLM/Qwen3/issues/1831))
documents the class explicitly: `| safe` filter removed for llama.cpp
compatibility, chained filters split into explicit if/else, bare key
iteration replaced with `arguments.items()`, `namespace()` constructor
workarounds, and more. One template, two engines, two different rendered
prompts.

**Stacks and builds bitten.** Qwen 3.5 and 3.6 on llama.cpp and LM Studio
per the community fix repos:
[froggeric/Qwen-Fixed-Chat-Templates](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates)
(targets llama.cpp, LM Studio, vLLM, MLX) and barubary's 21-fix attuned
template. The class is engine-general: any model whose official template
uses Python-only constructs will misrender on a C++ engine, and the
failure is silent because a template that renders wrong still renders.

**Not reproduced here on one current build, dated.** 2026-07-27, llama.cpp
b9066 serving Qwen3.5-9B Q4_K_M: the GGUF-embedded template contains
`|items`, and the C++ engine rendered the complete tool schema (function
name, every argument key, enum values, descriptions) matching a Python
Jinja2 reference render of the same template. Two honest observations
from the same probe: the engines' `tojson` implementations serialize with
different key orders, so the renders differ at the byte level even when
semantically equal (relevant to prefix caching and render diffing), and
the GGUF-embedded template differed from the official card template file
(7885 vs 7756 chars), which is
[trap 03](../reasoning/03-enable-thinking-default-drift.md)'s territory:
you may not be serving the template you think you are. The breakage
reports stand for the builds and clients they name; current llama.cpp
appears past this one.

**The check.** Render one tool-defined request through your actual serving
path and read the assembled prompt, not the request: are the tool names
and every argument key present and correctly delimited? Then diff that
render against a reference Python Jinja2 render of the same template and
messages ([checks/preflight_template.py](../../checks/preflight_template.py)
does the local reference render). Any divergence means the engine is part
of your unit under test.

**The fix.** Use an engine-tested template for your runtime (the community
fix repos exist for exactly this) or repair the Python-only constructs.
Record the template file hash and the template engine next to every
published number; "same template" across engines is not the same template.

**Found.** 2026-07-27 (mined from upstream; community fixes shipped over
the preceding months).

**Attribution.** barubary
([21-fix template](https://huggingface.co/barubary/qwen3.5-barubary-attuned-chat-template),
posted upstream by @blockoracle in
[QwenLM/Qwen3 #1831](https://github.com/QwenLM/Qwen3/issues/1831)),
froggeric
([Qwen-Fixed-Chat-Templates](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates)).
Related entries:
[trap 19](../tools/19-missing-jinja-breaks-tool-parsing.md) (the serve-flag
half of tool breakage),
[trap 04](04-history-reasoning-stripping.md) (why you must read the
assembled prompt at all).
