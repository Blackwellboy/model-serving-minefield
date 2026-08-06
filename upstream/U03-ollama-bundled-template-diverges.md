# U03: the template you are serving with is not the model's template

**Reported by @BogodaMM and @jukofyork.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** Two separate confirmations,
seven months apart, from two maintainers.

**Issue state: open** for the current instance (#14601, since 2026-03-03).
The historical instance (#1977) is `closed, fixed` after a year.

**Primary source.** Three, all read on 2026-07-28:

- [ollama/ollama#14601, "Qwen3 tool calling via /api/chat tools parameter:
  malformed tool definitions"](https://github.com/ollama/ollama/issues/14601)
 , the current, mechanically precise instance. Body and all four comments.
- [ollama/ollama#1977, "Mistakes in template definitions on models available
  to download"](https://github.com/ollama/ollama/issues/1977), the class,
  established over eighteen comments with an owner acknowledgement.
- [ollama/ollama#11621, "Qwen3-Coder missing Tools and FIM support in
  template"](https://github.com/ollama/ollama/issues/11621), a third
  instance, closed, sixty-four comments.

**Symptom.** The model is worse than its reputation, and specifically worse at
the thing the model card advertises. Tool definitions are "rejected as
malformed" by a model trained to accept them. Quality jumps when you write your
own Modelfile, which reads like the model needing coaxing and is actually the
packaging having been wrong.

**Mechanism, as stated upstream.** The template bundled with a model in the
library is a **separate artifact** from the `chat_template` in the model's own
`tokenizer_config.json`, and it can differ.

#14601 is the sharpest version. The bundled Qwen3 template renders tool
definitions with `{"type": "function", "function": {{ .Function }}}`, and
`.Function` is a Go struct. Go's default string representation is not JSON, so
the model receives

```
{"type": "function", "function": {get_weather Get the current weather for a city {object [city] {...}}}}
```

where its template expects

```
{"type": "function", "function": {"name": "get_weather", "description": "...", "parameters": {...}}}
```

Maintainer @rick-github confirmed the serializer exists and the template is
editable: Ollama has a `json` function. The reporter verified the fix,
`{{ .Function | json }}`, and posted the confirmation in the thread.

In #1977, @jukofyork audited the library's templates against the original
tokenizer configs and found errors across many models. Owner @jmorganca
replied "Will get this fixed". A recurring finding in that thread is a system
message being re-emitted on every turn instead of once.

**Two things in the source that the mining summary got wrong, and that matter.**

1. The reporter of #14601 filed **two** bugs. Bug 2, that assistant tool calls
   are stripped from history, is **struck through in the issue body and
   retracted**: the reporter found it was client-side, caused by Ollama
   returning an empty `message.content` on a tool call, and the tool call being
   available in `message.tool_calls` all along. Only Bug 1 stands.
2. The maintainer's framing is that the model in question is superseded rather
   than that the template is unfixable. That is a fair scoping and this entry
   should not be read as "Ollama's templates are broken". It is: **the bundled
   template is a distinct artifact, it has been wrong before on several models,
   and you can check yours in one command.**

**Why this is worth an entry.** The check is cheap and the failure is silent.
It also connects two things this registry measured separately: trap
[21](../traps/versioning/21-no-generation-config-server-defaults-win.md), where
a missing config means the server's built-ins become "the model's settings",
and trap [67](../traps/template/67-history-rendered-as-object-repr.md), where a
language's default representation of a structure leaks into the prompt. This
is that same object-repr failure on a different stack and a different field.

**What we have not done.** Nobody here has reproduced this. We have not run
`ollama show --modelfile` against a library model and diffed it, on any model,
at any version. The general claim, that bundled and official templates can
diverge, is supported by three threads; whether any *particular* model you
pull today is affected is exactly what the check below is for.

## If you have this stack

Ollama, and any model you actually use. Five minutes, no serving required.

1. `ollama show <model> --modelfile` and keep the `TEMPLATE` block.
2. Fetch the same model's `tokenizer_config.json` from its Hugging Face
   repository and extract `chat_template`.
3. Diff them **semantically**, not textually, they are different template
   languages, so a textual diff is noise. Ask three questions instead: does the
   tool-definition branch serialize as JSON; is the system message emitted once
   or on every turn; are the tool and thinking branches present at all.
4. If you find a divergence, render both with the same three-message history
   and compare the strings the model would receive.

**CONFIRM.** A material divergence, a structure rendered as anything other
than JSON, a missing tool or FIM branch, a system message repeated per turn,
and the behaviour changes when you serve with a corrected `TEMPLATE`.

**REFUTE.** The bundled template is semantically equivalent to the official one
for the model you checked. This is a per-model result, so report the model and
the version rather than a verdict on the library.

**Most useful contribution here:** a small table of models checked, with
pass or fail and the date. The class is established; what nobody has is
coverage.

## Attribution

@BogodaMM for the `.Function` serialization analysis and the verified fix,
@jukofyork for the original template audit, @d1g1t for the Qwen3-Coder
instance. Maintainer confirmations by @rick-github and @jmorganca. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).
