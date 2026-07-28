# U04: a patch release moved the default context by 64x, and the tiers ignore parallelism

**Reported by @tonydiep.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer responded.** Two maintainers engaged at
length and **disputed the framing**. What survives their pushback is narrower
than the issue title, and it is the part worth publishing.

**Issue state: closed, not fixed**: closed as completed on 2026-06-09 with no
change to the tiers. The behaviour is intended.

**Primary source.** [ollama/ollama#14073, "New default context lengths will
break"](https://github.com/ollama/ollama/issues/14073). Read on 2026-07-28:
body and all twenty-three comments.

**Symptom.** Models that ran on the previous patch release stop loading after
an upgrade nobody thought was risky. You get
`model requires more system memory (74.0 GiB) than is available (56.7 GiB)`, or
a server that spills to CPU and stops responding, on a machine whose hardware
did not change. Nothing in your configuration changed either, which is why the
first hypothesis is always the model.

**Mechanism, as stated upstream.** Ollama 0.15.5 replaced a flat default
context with tiers keyed on VRAM, quoted from the release notes in the issue:

```
< 24 GiB VRAM: 4,096 context
24-48 GiB VRAM: 32,768 context
>= 48 GiB VRAM: 262,144 context
```

A machine that crosses 48 GiB gets a **64x** increase in default context from a
patch upgrade. On a large model that is the difference between fitting and not.

**What the maintainers established, and it changes the claim.** Read this part
before citing the entry.

- @jessegross showed the reporter's own models sizing correctly from current
  source, and argued the design intent: a 4k default "is difficult to use and
  surprising", there are no perfect defaults, and dynamic sizing on free VRAM
  makes quality depend on what else is running. On the crash specifically:
  "it should not crash - simply get slower as more runs on the CPU."
- @rick-github identified the actual crash in one of the reports as a GGML
  assertion, `GGML_ASSERT(ggml_nbytes(src0) <= INT_MAX)`, which fires on other
  models pushed to maximum context and is **not about VRAM**.
- The reporter's own minimal reproduction, when finally run, **worked** and
  respected the configured context. They said so in the thread.

**The two facts that survive, and they are the useful ones.**

1. **The tiers do not account for `OLLAMA_NUM_PARALLEL`.** Stated by
   @rick-github, unrebutted, and it is the one genuinely unintended interaction
   in the thread: the tier picks a per-slot context and parallelism multiplies
   the memory it implies. If you run parallel slots, the default is being
   chosen as though you do not.
2. **The escape hatch is a server-side environment variable, not a request
   field.** @rick-github: setting `OLLAMA_CONTEXT_LENGTH=4096` in the server
   environment "will act exactly as it did before the context scaling was
   added."

**Why this is worth an entry.** A version boundary that silently changes a
resource default is the shape of trap
[75](../traps/versioning/75-release-asset-renamed-pinned-url-404.md) and trap
[21](../traps/versioning/21-no-generation-config-server-defaults-win.md): the
thing that changed is not in your configuration, so your configuration is the
last place you look. And the parallelism interaction is the same arithmetic as
trap [87](../traps/runtime/87-llamacpp-props-reports-per-slot-context.md) on a
different server, a context number that means per-slot when you read it as
total, or the reverse.

**Ignore the last comment in the thread.** It is an unrelated promotional post
that also asserts a confirmation. It is not evidence.

**What we have not done.** Nobody here has reproduced this. We have not
measured the parallelism interaction, which is the only part of this report we
would want to promote, and we have not confirmed the tier values against
current source rather than against the release notes quoted in the issue.

## If you have this stack

Ollama on a machine with 48 GiB or more of VRAM. Under an hour.

1. Confirm the tier applies: start the server with no `OLLAMA_CONTEXT_LENGTH`,
   load a small model, and read the context from `ollama ps`.
2. **The parallelism arm, which is the open question.** Hold the model fixed
   and vary `OLLAMA_NUM_PARALLEL` across 1, 2 and 4. Record the chosen context
   and the reported memory footprint at each.
3. Control: set `OLLAMA_CONTEXT_LENGTH=4096` and repeat step 2.

**CONFIRM.** The chosen default context per slot does not fall as
`OLLAMA_NUM_PARALLEL` rises, so total KV demand scales with parallelism while
the default behaves as though it does not, and the machine reaches a
configuration that cannot load a model it could load at `OLLAMA_NUM_PARALLEL=1`.

**REFUTE.** The default context is divided across slots, or otherwise falls,
as parallelism rises. Report the version: this would mean the interaction
@rick-github named has since been addressed.

**Do not report** "the default is too large" as a confirmation. That is the
part the maintainers answered, it is a design decision rather than a defect,
and re-litigating it in our registry would be reporting a disagreement as a
finding.

## Attribution

Reported by @tonydiep. The parallelism interaction and the
`OLLAMA_CONTEXT_LENGTH` escape hatch are @rick-github's; the design rationale
and the sizing evidence are @jessegross's. Crash triage by @rick-github.
Credited in [HALL_OF_FAME](../HALL_OF_FAME.md).
