# Playbook: thinking died when I made it multi-turn

Single-turn reasons. Multi-turn does not, or reasons worse, and the answers
still read fluently. This is the most expensive shape in the registry, because
the symptom looks like a property of the model rather than a defect in your
history assembly.

Nine steps, in order. Work top to bottom and stop when the marker survives.

Nothing here is new. Every step is a published entry, sequenced.

---

## 1. Render at turn 3 and grep for a marker. Do this before anything else

**Guards:** [trap 04, prior-turn reasoning stripped from history](../traps/template/04-history-reasoning-stripping.md) (**Core**)

Assemble a three-turn conversation whose first assistant message carries a
uniquely marked reasoning string. Render the **actual prompt** through your
serving path and grep it for that marker. If the marker is absent, your
multi-turn numbers describe a model that cannot see its own thinking.

[`checks/preflight_template.py`](../checks/preflight_template.py) does exactly
this and refuses to pass the lane if the marker is missing.

This is the one entry in this registry named as the most dangerous, and the
reason is that its symptom is a plausible, publishable result rather than a
broken parse.

## 2. Look at the assembled prompt, not the answer

**Guards:** [trap 59, the model quotes reasoning that was deleted](../traps/reasoning/59-reasoning-roundtrip-confabulation.md)

Two steps, and the second is the one people skip:

1. Read one real response body and **list the message keys**. Do not assume
   either field name, including the one in the vendor's own API docs.
2. Resend a prior turn's reasoning and then look at the **assembled prompt**.
   Use the server's render route if it has one and search it for the string
   you planted.

If the string is absent, the reasoning is not reaching the model no matter how
convincingly the model discusses it. A model that fluently quotes its own
earlier reasoning is not evidence that the reasoning arrived.

## 3. Get the write field name right for your runtime

**Guards:** [trap 20, the reasoning write field is runtime-specific](../traps/reasoning/20-reasoning-write-field-name-diverges.md)

Render the same transcript twice, once with the marker under `reasoning` and
once under `reasoning_content`, and diff the renders. The arm whose render
contains the marker is your write field.

Published today: `reasoning` on vLLM with the parser measured in
[trap 04](../traps/template/04-history-reasoning-stripping.md), and
`reasoning_content` on llama.cpp, where `reasoning` is silently dropped and
renders **byte-identical** to the stripped arm. Do not port the fix by copying
a field name out of someone else's writeup. Both wrong-field cases fail by
producing absence, which is the same thing you were trying to diagnose.

## 4. Check the gate kwarg, and check its polarity

**Guards:** [trap 63, the reasoning round trip has one correct shape out of four](../traps/reasoning/63-reasoning-round-trip-one-correct-shape.md)

Four renders, one marker, one grep. Marker under `reasoning` and under
`reasoning_content`, each with the preservation kwarg at default and set.
Exactly one arm should contain it.

On one published family the preservation gate is named
`truncate_history_thinking` and **true means discard**, the opposite polarity
to the other name this registry documents, so a pipeline standardised on the
other one silently no-ops. Send both the field and the kwarg: either alone
gives you an empty think block.

## 5. Look for empty think shells in the render

**Guards:** [trap 25, empty historical think blocks](../traps/template/25-empty-think-blocks-poison-prefix-cache.md)

Render a three-turn conversation where prior assistant turns carry content but
no reasoning, and grep the assembled prompt for empty think pairs. Then
token-count two histories that differ only in empty-reasoning turns. Empty
wrappers, or differing counts, confirm it.

Note the reading trap: an absence of `<think></think>` pairs does **not**
clear step 1. A lane that drops prior reasoning and emits no wrapper at all
produces exactly that render. Trap 04 takes its verdict from the write-field
probe, not from the absence of shells.

## 6. Separate apparatus from history strip

**Guards:** [trap 30, the default system message is silently replaced](../traps/template/30-default-system-message-silently-replaced.md), [trap 06, system-prompt topology moves the gate](../traps/reasoning/06-identity-sentence-eviction.md), [trap 83, a baked default system prompt](../traps/template/83-template-carries-a-baked-default-system-prompt.md)

Multi-turn changes more than history. It usually also attaches a system
prompt, and that is a second variable.

- Read the template, do not infer from behaviour. Pull `chat_template.jinja`
  (or the `chat_template` field of `tokenizer_config.json`) from the **exact
  checkpoint your server loads**, md5sum it, record the hash next to your
  results, and read the branch that guards the default system message: does a
  caller system message replace it, merge with it, or leave it? On the
  measured checkpoint it replaces it wholesale, so every with-system-prompt
  condition also toggles default-identity-absent.
- "No system message" and "empty system message" are **different baselines**.
  Decide which arm you are running and say so next to every number.
- Your no-system-prompt control may not be a control at all: one measured
  template injects a hard-coded default system prompt whenever the request
  omits one ([trap 83](../traps/template/83-template-carries-a-baked-default-system-prompt.md)).
- Where a system prompt does move the gate, control **both** the first line
  and the tail before concluding which mechanism you have. The reported
  prefix-key mechanism did not reproduce on a second stack, where the working
  lever was the tail. And if you arrived with an agent prompt and tool
  schemas specifically, read
  [trap 06's apparatus route](../traps/reasoning/06-identity-sentence-eviction.md#if-you-arrived-here-with-an-agent-prompt-and-tools)
  first: a 752-byte agent prompt with 3 tool schemas fired 90.4% at n=492.

## 7. Check the template is not rewriting your text

**Guards:** [trap 66, the template scans user text for a toggle and deletes it](../traps/template/66-in-text-thinking-toggle-mutates-user-text.md), [trap 67, history rendered as an object repr](../traps/template/67-history-rendered-as-object-repr.md)

Two cheap offline greps and one render:

- `grep -c "/no_think" chat_template.jinja` next to the weights. Any hit means
  your users' text is being scanned, and on the measured lane the marker is
  obeyed **and deleted**, so a path or URL containing those characters comes
  back silently rewritten.
- Render a three-turn history and look for `[{'type':` or `'text':` in the
  assembled prompt. That is the server normalising message content to a list
  and the template rendering the list repr. Put the system message **first**
  in the probe: a non-first system message renders correctly and masks it.

## 8. Check where the prefix actually starts

**Guards:** [trap 82, the system prompt relocates to the last user turn](../traps/template/82-system-prompt-relocates-to-last-user-turn.md)

If every turn misses the prefix cache and the system prompt is not where you
put it, one measured template moves it onto the **last** user turn, so no two
turns share a prefix. Render two consecutive turns and compare their opening
tokens.

## 9. Assert per request which arm you actually measured

**Guards:** [trap 01, the reasoning field has two names](../traps/reasoning/01-reasoning-field-two-names.md) (**Core**), [trap 66](../traps/template/66-in-text-thinking-toggle-mutates-user-text.md)

Do not rely on the configuration to establish which arm ran. Read **both**
reasoning key names, fall back to scraping think tags out of `content`, and
assert per request: an arm you believe is thinking-off must have an absent or
empty reasoning field on **that response**, not in your config file.

```python
reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
```

On at least one server the reasoning lands under a third name and splits by
route, and `reasoning_content` exists nowhere. Enumerate the keys on **each
route you use**.

## If none of the above clears it

Carry prior reasoning yourself, as ordinary assistant `content` or as a
user-turn summary you control, rather than in a reasoning field the template
discards. Then it is visible in the render, stable for prefix caching, and
costs tokens you can see and budget
([trap 59](../traps/reasoning/59-reasoning-roundtrip-confabulation.md)).

---

**Related playbooks.** [Before you publish an A/B](before-you-publish-an-ab.md)
if the multi-turn number is going into a comparison.
[Porting a harness to a new server](porting-a-harness.md) if the fix worked on
one stack and not the next.
