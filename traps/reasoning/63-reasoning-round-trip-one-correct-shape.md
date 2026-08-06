# Trap 63: the reasoning round trip has exactly one correct shape out of four

**Found by Blackwellboy.**

**Status: reproduced here** on three checkpoints of one family, by three
different methods, one of them server-side end to end. The gate kwarg, its
polarity and the field name the template reads are all in the checkpoints'
own public chat templates, so a stranger settles the structural half offline
with a grep and the behavioural half with the four renders below, on their
own lane, without asking us for anything.

**Symptom.** You append the assistant message you just received to your history
and send it back, the way every chat client does. Multi-turn quality is lower
than single-turn and gets worse with depth. Nothing in the API response tells you
why: HTTP 200, sensible text, the reasoning field populated on every turn. If you
read the chat template to find the fix, the template tells you to send
`reasoning_content`, and doing that changes nothing at all.

**Mechanism.** Two independent gates compose, and the obvious fix for each one is
wrong.

1. **The template strips prior-turn reasoning by default**, replacing it with an
   empty `<think></think>` pair, gated by a kwarg the model card does not
   document. On this family the kwarg is **`truncate_history_thinking`**, it
   defaults to **`true`**, and **`false` is the preserve setting**. Note the
   polarity: this registry's existing entries document `preserve_thinking`,
   where **true** preserves. Same switch, opposite sense, different name. A
   pipeline standardised on "set preserve_thinking true" silently no-ops here.
2. **The field name the server writes is not the field name the template
   reads.** The server writes `message.reasoning`. The template source reads
   `message.reasoning_content`. But the request schema does not carry an
   unrecognised `reasoning_content` through to the renderer, so sending the name
   the template asks for drops the value before the template ever sees it. The
   server maps its own `reasoning` field into the renderer's context instead.

Reading the template source alone therefore produces the wrong answer with high
confidence, which is what makes this a trap rather than a naming inconvenience.

**The four-arm result.** Measured server-side through
`POST /v1/chat/completions/render` plus `POST /detokenize`, so this is the prompt
the model actually receives. The assistant turn carried a marker string.

| Arm | Reasoning key sent | `truncate_history_thinking` | Marker reaches the prompt |
|---|---|---|---|
| A | `reasoning` | `false` | **yes** |
| B | `reasoning` | default (`true`) | no |
| C | `reasoning_content` | `false` | no |
| D | `reasoning_content` | default (`true`) | no |

Abbreviated renders of the assistant turn:

```
A: <|im_start|>assistant\n<think>\nMARKER\n</think>\nA1<|im_end|>
B: <|im_start|>assistant\n<think></think>\nA1<|im_end|>
C: <|im_start|>assistant\n<think></think>A1<|im_end|>
D: <|im_start|>assistant\n<think></think>A1<|im_end|>
```

Arms C and D render `<think></think>A1` with no newline; arm B renders
`<think></think>\nA1` with one. That is not cosmetic. It shows B went through the
truncation branch (it had reasoning and removed it) while C and D went through
the never-had-reasoning branch. **Two different code paths, one identical-looking
outcome.** If you are diffing renders to find your fix, that one-character
difference is the only signal that anything reached the template at all.

**Stacks and builds bitten.** Three checkpoints of the NVIDIA Nemotron 3 family
on GB10-class single nodes, characterised in three independent sessions:

- **Super 120B A12B NVFP4**, vLLM 0.20.0 vendor container. The four-arm table
  above, server-side.
- **Nano 30B A3B NVFP4**, vLLM 0.25.1 in a pip venv. Offline Jinja render of the
  checkpoint template at the pinned revision confirmed the stripping and the
  kwarg polarity independently, and correctly reported that the template source
  reads `reasoning_content` only. Live serving then showed the server writes
  `reasoning`.
- **Nano Omni 30B A3B NVFP4**, vLLM 0.20.0 upstream arm64 container. Confirmed
  the kwarg half through `POST /tokenize` with per-token strings: an inline
  `<think>...</think>` in prior content survives with
  `truncate_history_thinking: false` (95 prompt tokens against 80 stripped), and
  an inbound `reasoning_content` is dropped before rendering. **The `reasoning`
  arm was not run on this checkpoint**, so its round trip is confirmed for the
  gate and open for the field name.

The Nano and Super conclusions look contradictory and are not. An offline render
sees exactly the keys you hand it; a live server maps its own field and drops the
unrecognised one. Both are correct about different layers, and a reader who has
only one of them will implement the wrong fix.

**The check.** Four renders, one marker, one grep. Build a two-turn history whose
assistant message carries a unique marker string as its reasoning. Render it four
ways: marker under `reasoning` and under `reasoning_content`, each with the
preservation kwarg at default and set. Grep each assembled prompt for the marker.
Exactly one arm should contain it. If none does, the switch has another name and
you need the kwarg enumeration below.

On vLLM: `POST /v1/chat/completions/render` returns `token_ids`, and
`POST /detokenize` converts them back to text. `POST /tokenize` with
`return_token_strs: true` also works and is available on builds whose route
listing does not advertise it. On llama.cpp: `/apply-template`. Otherwise
[`checks/preflight_template.py`](../../checks/preflight_template.py) with
`--template-file`, and
[`doctor/minefield_doctor.py`](../../doctor/minefield_doctor.py), which now tries
four known gate names in both polarities against both field names and names the
combination that worked.

**Corollary, and this is the general lesson.** Enumerate every kwarg the template
reads and diff it against the card. On this family the template reads three and
the card documents one. Anything read-but-undocumented is an untested variable,
and if it sits near a thinking branch, assume it changes your results until you
have shown it does not.

**The fix.** Send **both**:

```json
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "reasoning": "<exactly as returned>"},
    {"role": "user", "content": "..."}
  ],
  "chat_template_kwargs": {"truncate_history_thinking": false}
}
```

Either alone gives you an empty think block. Do not port the field name or the
kwarg polarity from another model's writeup; probe your own lane.

**If you miss it.** Every multi-turn evaluation measures a model that cannot see
its own prior reasoning, and the history contains empty `<think></think>` blocks
that read as a demonstration that assistant turns in this conversation do not
think. Truncation is scoped to assistant turns before the **last** user message,
so the effect grows with conversation depth. That is exactly the shape that gets
published as a depth-dependent capability finding, which is what this registry's
history-stripping entry was created to prevent.

**Negatives recorded.**

- Sending `reasoning_content` alone: no effect at all, on any of the three
  checkpoints. It is not merely the wrong key; it never reaches the renderer.
- Setting the kwarg without resending reasoning: no effect. There is nothing left
  to preserve.
- `preserve_thinking: true`, the name from this registry's existing entries: not
  read by any of these three templates. Confirmed by kwarg enumeration on all
  three, which returns `enable_thinking`, `truncate_history_thinking` and, on
  Super, `low_effort`.
- The most recent assistant turn keeps its reasoning under all four arms. Only
  turns before the last user message are affected, so a two-turn probe that puts
  the marked turn last will show no problem and is the wrong probe.

**Related.** Cross-links rather than duplicates:
[trap 01](01-reasoning-field-two-names.md) is the read side of the field-name
divergence; [trap 20](20-reasoning-write-field-name-diverges.md) is the write
side, and this entry is a third runtime for it where the answer is `reasoning`;
[trap 04](../template/04-history-reasoning-stripping.md) is the stripping
mechanism, and this entry adds a family whose gate has a **different name and
inverted polarity**;
[trap 25](../template/25-empty-think-blocks-poison-prefix-cache.md) is the
empty-shell render this produces;
[trap 03](03-enable-thinking-default-drift.md) is the documented sibling kwarg.

**Found.** 2026-07-27 and 2026-07-28, across three independent characterisation
sessions of the same model family on the same hardware class, merged 2026-07-28.

**Attribution.** Blackwellboy. The mechanism it confirms is not new to this
registry; what is new is a family with an inverted-polarity gate, a third runtime
for the write-field divergence, and a fully crossed four-arm render measured
server-side.
