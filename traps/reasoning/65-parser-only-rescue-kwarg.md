# Trap 65: the fix for empty content is a kwarg the template never reads, documented in a docstring

**Found by Blackwellboy.**

**Status: reproduced here, clean A/B at an identical token budget.**

**Symptom.** You hit the empty-content-at-ceiling failure, you go looking for a
mitigation, and you find nothing in the model card. The mitigation exists, is
shipped, is supported, and is documented in a comment inside a file you had to
know to download.

**Mechanism.** This family ships its reasoning parser **inside the checkpoint
repository**, not in the serving stack. That parser reads a kwarg,
`force_nonempty_content`, which the chat template does not read at all. When set,
if the response would otherwise have empty content, the parser moves the
reasoning into `content` instead of leaving it in the reasoning channel.

So there are two kwarg surfaces on this lane, read by two different components,
and enumerating the template's kwargs (which is the standard advice, and correct)
finds only one of them.

Measured at a deliberately tight ceiling, same prompt, same 48-token budget:

| Arm | `finish_reason` | content chars | reasoning chars |
|---|---|---|---|
| default | `length` | **0** | 88 |
| `force_nonempty_content: true` | `length` | **90** | 0 |

**Stacks and builds bitten.** NVIDIA Nemotron 3 Super 120B A12B NVFP4, vLLM
0.20.0 vendor container, single GB10-class node, with the repository's own
`super_v3_reasoning_parser.py` mounted via `--reasoning-parser-plugin`.

Not tested on the two sibling checkpoints, whose parsers are different files.
Read the parser you actually mounted; do not assume the kwarg is there.

**The check.** Two steps, both cheap.

1. **Read the parser source.** It is small; the Super one is 1909 bytes. Grep it
   for kwarg reads. The kwargs a parser reads are not in the card, not in the
   template, and not discoverable from the API.
2. Send a request at a tight budget with and without the kwarg and compare
   `content` length.

**The fix.** Pass it, when it is right for your workload:

```json
"chat_template_kwargs": {"force_nonempty_content": true}
```

with the caveat that it is a **rescue, not a solution**. What you get back in
`content` is the reasoning trace, truncated at your ceiling, not an answer. It
converts a silent empty response into a visible partial one, which is strictly
better for an agent loop and strictly worse for a scorer that will now mark a
truncated trace as an answer. Keep bucketing `finish_reason: "length"`
separately either way.

**The general lesson, which is the reason this is a registry entry rather than a
tip.** When a checkpoint ships its own parser, **the parser is part of the kwarg
surface**. The standard discipline of "enumerate every kwarg the template reads
and diff it against the card" is necessary and, here, not sufficient. Enumerate
the parser's kwargs too, from its source, because there is no other way to find
them.

**Negatives recorded.**

- The template does not read this kwarg, so a template-side kwarg enumeration
  correctly reports it as absent. The enumeration is not wrong; its scope is.
- The kwarg appears in no section of the model card.
- It does not prevent the truncation; it only changes which field the truncated
  output lands in.

**Related.**
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md), the failure this
rescues; [trap 07](07-reasoning-effort-silently-ignored.md), the inverse case of a
kwarg accepted but not read;
[in-repo parser draft](../runtime/70-in-repo-parser-not-bundled.md), the packaging
pattern that creates the second kwarg surface.

**Found.** 2026-07-27.

**Attribution.** Blackwellboy.
