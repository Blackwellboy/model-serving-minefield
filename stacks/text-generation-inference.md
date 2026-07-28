# text-generation-inference (TGI)

**We have measured nothing on this stack and we hold no upstream reports about
it.** Not one entry names it, not even in passing. This is the emptiest page in
the directory, and it is here because "no page" and "no problems" read the same
from outside.

Absence means nobody has reported to us. It is not a clean bill of health, and
given that TGI is one of the most widely deployed inference servers in
existence, a zero here says considerably more about our sample than about the
software.

Nobody here has run TGI.

## Why the gap

No principled reason, which is worth saying plainly rather than
rationalising. Our fleet grew around vLLM, llama.cpp, Ollama, mlx_lm and more
recently SGLang, because those are what our hardware and our weights pushed us
toward. TGI never came up. It is the largest unexplained hole in this
registry's coverage.

## Which of our mechanism classes most likely apply, and why

Hypotheses, each naming the measured entry the class comes from. TGI is a
**Rust router in front of a Python shard**, and that architecture is what makes
the first two guesses specific rather than generic.

**Prior-turn reasoning stripped from history**: trap
[04](../traps/template/04-history-reasoning-stripping.md), the registry's most
dangerous entry, with traps
[20](../traps/reasoning/20-reasoning-write-field-name-diverges.md),
[63](../traps/reasoning/63-reasoning-round-trip-one-correct-shape.md) and
[59](../traps/reasoning/59-reasoning-roundtrip-confabulation.md). **This is
where we would look first.** The class is: what a reasoning model wrote on turn
one is dropped before turn two, so multi-turn quality degrades in a way that
produces a plausible, publishable number rather than a broken parse. It bites
wherever a router normalises messages before a template renders them, and there
are two names for the field, `reasoning` and `reasoning_content`, with
different stacks reading and writing different ones. A stack with a separate
routing layer has an extra seam for exactly this.

**The server normalises content and the template renders the normalised
form**: traps [67](../traps/template/67-history-rendered-as-object-repr.md) and
[68](../traps/template/68-multimodal-part-order-discarded.md), and
[U11](../upstream/U11-glm-tool-content-array-renders-empty.md), which is the
same mechanism reported by a model vendor on two other stacks. Any server that
converts a string `content` into a list of content parts before rendering can
hand a string-only template something it renders as empty. The tool role is
where it hurts, because an empty tool result makes the model call the tool
again forever.

**Accepted and ignored**: traps
[07](../traps/reasoning/07-reasoning-effort-silently-ignored.md),
[77](../traps/reasoning/77-only-one-request-field-is-validated.md),
[78](../traps/tools/78-tool-choice-accepted-and-ignored.md), and
[U09](../upstream/U09-vllm-mistral-chat-template-ignored.md). TGI's native API
and its OpenAI-compatible route are different surfaces over one engine, and
**every stack in this registry that has two routes has been found to behave
differently on them**: trap [01](../traps/reasoning/01-reasoning-field-two-names.md)
found one server carrying three names split by route, and
[U01](../upstream/U01-ollama-toolcalls-missing-on-openai-route.md) is an
upstream report of tool calls reaching the template on one route and not the
other. Two routes is the single strongest predictor in our data.

**Empty content at a token ceiling**: traps
[12](../traps/evaluation/12-empty-content-at-token-ceiling.md) and
[16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md). A
thinking model that spends its budget inside the think block returns a
well-formed response with nothing in it, and a harness scores that as a
capability collapse. Every stack has a version of this and the ceiling that
triggers it is per-model.

## How you would test for these

1. **Run the [doctor](../doctor/) against the endpoint.** It is one stdlib
   file with no dependencies and it has never met this stack. It checks nine of
   the [Core twelve](../CORE.md) and prints what it could not determine rather
   than a clean verdict it did not earn.
2. **Run it against both routes**: the native generate endpoint and
   `/v1/chat/completions`, and diff the two reports. On our evidence that
   diff is the most likely place a first finding appears.
3. **For the history class**, the check is in trap 04 and needs no tooling:
   send a two-turn conversation where turn one produced reasoning, and ask the
   server to echo or tokenize what it assembled. Compare the reasoning field
   you sent with the one that survives. Both field names, both directions.
4. **For the ceiling class**, sweep `max_tokens` on a prompt that reliably
   induces long reasoning, and record where `content` becomes empty while
   `finish_reason` is still `length`. Report the ceiling and the model.

## How to report a finding

Open an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml).
Four plain questions and a maintainer writes the entry and credits you. Data
format guidance is in
[CONTRIBUTING](../CONTRIBUTING.md#sending-measurement-data).

**Reporting that you found nothing is a real contribution here.** A single
doctor run posted against TGI would be the first first-party fact this project
has about the stack.
