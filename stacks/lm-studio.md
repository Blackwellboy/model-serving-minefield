# LM Studio

**Measured here:** no (no first-party run)


**We have measured nothing on this stack directly.** One entry names it, trap
[24](../traps/template/24-official-template-breaks-cpp-jinja.md), and it names
it as one of the environments a **C++ Jinja portability defect** applies to,
alongside llama.cpp. That entry is real and it is relevant here, but it was
measured on llama.cpp; LM Studio appears in it by inheritance, not by
measurement.

Nobody here has run LM Studio.

## The one thing worth knowing before anything else

LM Studio is a **client and packager over an inference engine**, principally
llama.cpp with an MLX path on Apple silicon. That has a direct consequence for
this registry, and it is the most useful thing on this page:

**Most of what will bite you here is already documented, on
[llama.cpp](llama-cpp.md) and [mlx_lm](mlx.md).** Those are our two
best-covered stacks, at 34 and 9 entries. Start there rather than here.

What LM Studio adds on top is a **second template and parser layer of its
own**, and that layer is where a genuinely LM-Studio-specific trap would live.
The registry has a great deal of evidence that this is the dangerous seam: trap
[24](../traps/template/24-official-template-breaks-cpp-jinja.md) is a template
written for Python Jinja meeting a C++ engine, trap
[19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md) is one missing
flag turning tool calls into prose, and
[U06](../upstream/U06-mlx-lm-gemma4-tool-parser-missing.md) is parser inference
failing silently so raw markup lands in `content`.

## Which of our mechanism classes most likely apply

**Client-side parsers disagreeing with the model's format**: traps
[24](../traps/template/24-official-template-breaks-cpp-jinja.md),
[19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md),
[02](../traps/template/02-orphaned-think-close-tag.md), and
[U06](../upstream/U06-mlx-lm-gemma4-tool-parser-missing.md). The symptom is
always the same: the model did the right thing and the layer above it did not
recognise it, so you conclude the model cannot do the thing.

**The bundled template is not the model's template**:
[U03](../upstream/U03-ollama-bundled-template-diverges.md), an upstream report
against a different packager, and trap
[21](../traps/versioning/21-no-generation-config-server-defaults-win.md), where
a missing config means the server's built-ins silently become "the model's
settings". Any tool that repackages a model for its own catalogue owns a
template artifact separate from the checkpoint's, and that artifact can be
wrong or stale independently of the weights.

**Reasoning field naming**: traps
[01](../traps/reasoning/01-reasoning-field-two-names.md) and
[20](../traps/reasoning/20-reasoning-write-field-name-diverges.md). The read
field and the write field are runtime-specific, and a GUI that renders a
thinking pane has to pick one. If your thinking pane is empty while the model
is plainly reasoning, that is this class and not the model.

**Empty content at a token ceiling**: trap
[12](../traps/evaluation/12-empty-content-at-token-ceiling.md), and trap
[32](../traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md) for
the specific case where a max-tokens setting is a per-request **default**
rather than a cap, which we measured on mlx_lm. A GUI with a token slider is
exactly where that distinction gets lost.

## What we deliberately did not publish

The round-2 mining pass carried a community post reporting that this client's
parser breaks tool calling and reasoning for a specific model family. It rests
on a single forum post, and it was
closed as too weak *(private evidence archived)*
rather than published: no reproduction, no version, and no tracker thread to
read. It is noted here because the *class* is plausible on the reasoning above,
not because the report was verified. It was not.

## How you would test for these

1. **Run the [doctor](../doctor/)** against the local server. LM Studio exposes
   an OpenAI-compatible endpoint, which is all the doctor needs.
2. **Compare against the engine underneath.** This is the decisive experiment
   and it is available to anyone: serve the **same GGUF** with plain
   `llama-server` and through LM Studio, send identical requests, and diff the
   responses. A difference is LM Studio's layer by construction, and that is
   the only kind of finding this page can uniquely gain.
3. **For the template layer**, prompt the model to repeat its input verbatim,
   or read whatever prompt-preview the application exposes, and compare it with
   the checkpoint's own `chat_template`.
4. **For tool calling**, check `content` as well as `tool_calls`. Native
   markup sitting in `content` with an empty `tool_calls` array is parser
   inference failing, and it is reportable regardless of model.

## How to report a finding

Open an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml).
The comparison in step 2 is worth more than any number of impressions, because
it isolates the layer.
