# Trap 57: the thinking kwarg is evaluated for truthiness, so "false" turns it on

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on a live DeepSeek-V4-Flash lane
served with thinking disabled by default. Nine values tested, every render
pulled from the server's own tokenize endpoint.

**Evidence pointer.** The coercion is a line in the checkpoint's own Python
encoder module, which is a public source file: read where the thinking kwarg is
consumed and confirm it is tested for truthiness rather than parsed. The
behavioural half is a one-minute two-request probe on the reader's own lane,
written out in the check section. Neither step needs anything from us.

**Symptom.** You run a lane with reasoning off in the serve line. A client
wants to be explicit rather than rely on the default, so it sends the thinking
kwarg with the value `"false"`. Thinking turns **on**. The request returns 200.
The client's own logs show it asked for `false`. Token usage triples and, on a
lane whose max_tokens is sized for non-thinking replies, some replies come back
empty at the ceiling.

**Mechanism.** The kwarg is passed into the prompt builder and evaluated for
Python truthiness rather than parsed as a boolean. `"false"` is a non-empty
string, so it is true. So is `"0"`. The distinction is invisible in the request
body, because JSON `false` and JSON `"false"` differ by two characters that no
log highlights and many client libraries introduce on their own when they build
kwargs from environment variables, YAML, or query strings, all of which yield
strings.

Measured on this lane, where the serve line sets thinking off by default. The
right-hand column is the last token of the generation prompt, which is the
whole toggle:

| value sent | prompt ends with | thinking |
|---|---|---|
| `false` (JSON bool) | close tag | off |
| `0` (JSON number) | close tag | off |
| `""` | close tag | off |
| `null` | close tag | off |
| `[]`, `{}` | close tag | off |
| `true` (JSON bool) | open tag | **on** |
| `1` | open tag | **on** |
| `"false"` (string) | open tag | **on** |
| `"0"` (string) | open tag | **on** |
| `"banana"` (string) | open tag | **on** |

Every one of those returned HTTP 200. There is no validation anywhere in the
path: an entirely unknown kwarg name is also accepted with 200 and silently
ignored, so a client cannot distinguish "you honoured my flag" from "I
misspelled it and you dropped it" by looking at the status code.

Note the shape of the risk. The failure is asymmetric. Every wrong-typed value
lands on the **on** side, because every non-empty string is truthy. A lane
whose default is off can only be pushed on by a type error, never the reverse.
If your default is on, this trap is invisible on your lane and still present.

**Why this is its own entry.** Two neighbouring entries look similar and are
not.
[Trap 03](03-enable-thinking-default-drift.md) is about which *name* the toggle
has and what the default is when it is absent.
[Trap 29](29-server-reasoning-off-is-not-an-off-switch.md) is about a
correctly-typed client flag overriding a server default, which is a design
choice you can plan around. This entry is about a value that the client
believes is disabling thinking, and that means the opposite. The client is not
overriding the server; it is being misread.

For completeness on this lane, both spellings of the toggle are honoured, the
family-specific one and the more common `enable_thinking`. Both are equally
subject to the coercion above.

**The check.** No generation needed and it takes a minute. Post your message
list to the server's tokenize endpoint with `return_token_strs`, once with the
thinking kwarg as a JSON boolean `false` and once as the string `"false"`, and
compare the final token of each render. If they differ, your lane coerces. Then
send a deliberately misspelled kwarg name and confirm you get 200 rather than
an error, which tells you the surface is unvalidated and that spelling mistakes
in your own callers are silent.

**The fix.** Coerce at the gateway rather than trusting callers: parse the
value to a real boolean, and reject or normalise strings explicitly, treating
`"false"`, `"0"`, `"no"` and `""` as false rather than passing them through.
If your lane is sized for non-thinking output, strip thinking kwargs at the
gateway entirely, which also closes trap 29 on the same lane. And when auditing
callers, grep for the kwarg's **value type**, not just its name; the callers
that will bite you are the ones that look correct in review because the word
`false` is right there.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3` serving a
community-abliterated DeepSeek-V4-Flash checkpoint with
`--default-chat-template-kwargs {"thinking": false}` in the serve line,
tokenizer mode `deepseek_v4`, `--trust-remote-code`, two DGX Spark GB10 nodes.
The coercion happens in the checkpoint's own Python prompt builder, so it
travels with the checkpoint rather than the server; expect it wherever that
encoder is executed.

**Found.** 2026-07-28, first registry coverage pass on this lane.

**Attribution.** Blackwellboy. Related:
[trap 03](03-enable-thinking-default-drift.md),
[trap 29](29-server-reasoning-off-is-not-an-off-switch.md),
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) (where the extra
thinking tokens land you).
