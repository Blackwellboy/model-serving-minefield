# Trap 162: with thinking on, a short answer never closes the pre-opened think block, so the whole answer is filed as reasoning

**Found by Blackwellboy.**

**Status: reproduced here** (runnable five-request procedure in The check,
against the public checkpoint and its shipped chat template on any vLLM lane;
the benchmark rates quoted under Symptom are **measured here, raw not
published**, because the item set is a private sealed benchmark).

**Symptom.** You turn thinking on and ask a short multiple-choice question.
The request returns HTTP 200, `finish_reason: "stop"`, `content: null`, and
`completion_tokens: 2`. The reasoning field holds exactly the answer you
wanted, for example `"B"`. Nothing was truncated and nothing errored. In a
scored run it looks like the model forgot how to answer easy questions only
when it is allowed to think.

Measured on a 40-item knowledge and truthfulness slice of a private
multiple-choice benchmark, non-streaming, one lane:

| Arm | Empty `content` | Of those, the reasoning field held the correct letter | `finish_reason` on the empties |
|---|---|---|---|
| thinking on, temperature 0 | **24/40** | 17/24 | `stop` 24/24 |
| thinking on, card sampling (temperature 1.0, top_p 0.95, top_k 20, seed 1) | **24/40** | 19/24 | `stop` 24/24 |
| thinking off, temperature 0 | 0/40 | not applicable | not applicable |

22 of the 24 temperature-0 empties were exactly 2 completion tokens (the
letter and the end-of-turn token); the longest was 31 tokens, a letter and a
one-sentence justification. The other 16 thinking-on items opened a normal
reasoning trace, closed it, and answered in `content` (median 377 reasoning
tokens). Scored as delivered, the two affected categories read **25** each;
counting the answer from the reasoning field they read **55** (knowledge)
and **80** (truthfulness). That is a 14-point swing on the six-category
total (64.2 against 78.3), produced by field placement alone.

These are single runs on one item set, so the rates carry wide binomial
noise and are not a capability measurement. The point is the shape: a large
share of short answers, at both sampling settings, with the reasoning field
holding the answer.

**Mechanism.** Two facts combine.

1. The chat template owns the opening tag
   ([trap 38](../template/38-template-owns-the-opening-think-tag.md)). With
   `enable_thinking` true, the generation prompt ends in `<think>\n`. With it
   false, the template writes the whole empty block, `<think>\n\n</think>\n\n`,
   so the model starts in answer position.
2. On a short, closed question the model often answers straight away and ends
   the turn **without ever writing `</think>`**. The raw completion is just
   `B` followed by the end-of-turn token. The reasoning parser, which knows the
   prompt opened a think block, treats everything before a `</think>` as
   reasoning. There is no `</think>`, so the whole completion is reasoning and
   `content` is null.

The parser is behaving as specified for a prompt-opened block; the template is
behaving as written. What breaks the contract is that the model does not
reliably honour the block the template opened for it when the question needs
no thought. **Why** it skips the close tag on these items and not others is not
established here; the trigger observed is short closed-form questions, and the
entry does not claim more than that.

How this differs from its neighbours:
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) also empties
`content`, but with `finish_reason: "length"` and a genuine trace in the
reasoning field; here the finish is `stop` and the "reasoning" is the answer.
[Trap 64](64-answer-lands-in-reasoning-on-toggle-conflict.md) reaches the same
null by a template and parser disagreement triggered by `/no_think` in user
text; here nothing disagrees and the user text is ordinary.
[Trap 23](23-streaming-answer-lands-in-reasoning-channel.md) is a
streaming-path defect; this reproduces with `stream: false`.

**Stacks and builds bitten.** `openbmb/MiniCPM-V-4.7-35B-A3B-AWQ` at revision
`ea491d008227809c62ff72dce9a5650d5d0576c1` (compressed-tensors W4A16), with
the base repository's processor configs overlaid as described in
[trap 163](../versioning/163-quantized-sibling-repo-ships-stale-processor-metadata.md)
(chat template and `tokenizer.json` are byte-identical between the two
repositories). vLLM `0.31.1rc1.dev371+gdf6c7ad03` (nightly; MiniCPM-V 4.7
support is main-only at the time of writing), transformers 5.19.0, torch
2.13.0+cu130, `--reasoning-parser qwen3`, one RTX 5090 32 GB, non-streaming
chat completions. On this build the parsed field is named `reasoning`;
`reasoning_content` is absent (see
[trap 01](01-reasoning-field-two-names.md) before you assert on either).

Not tested: the BF16 base checkpoint, streaming, other reasoning parsers,
llama.cpp or SGLang. The AWQ weights are the only weights measured, so the
entry does not separate a quantization effect from a model behaviour.

**The check.** Five requests, no benchmark needed. Replace `HOST:PORT` and the
served model name with your own.

```python
import json, urllib.request
BASE, MODEL = "http://HOST:PORT", "MiniCPM-V-4.7-35B-A3B-AWQ"
Q = ("Which planet in our solar system is the largest?\n"
     "A. Mars\nB. Jupiter\nC. Venus\nD. Mercury\nAnswer with only the letter.")
MSGS = [{"role": "user", "content": Q}]

def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))

# 1. What the template appends after the assistant header.
t = post("/tokenize", {"model": MODEL, "messages": MSGS,
         "add_generation_prompt": True, "return_token_strs": True,
         "chat_template_kwargs": {"enable_thinking": True}})
print("prompt tail:", t["token_strs"][-3:])

# 2-4. Thinking on twice, thinking off once, temperature 0.
for on in (True, True, False):
    r = post("/v1/chat/completions", {"model": MODEL, "messages": MSGS,
             "temperature": 0, "max_tokens": 512,
             "chat_template_kwargs": {"enable_thinking": on}})
    m, c = r["choices"][0]["message"], r["choices"][0]
    print(on, repr(m.get("content")),
          repr(m.get("reasoning") or m.get("reasoning_content")),
          c["finish_reason"], r["usage"]["completion_tokens"])

# 5. The raw completion, with no reasoning parser in the path.
ids = post("/tokenize", {"model": MODEL, "messages": MSGS,
           "add_generation_prompt": True,
           "chat_template_kwargs": {"enable_thinking": True}})["tokens"]
r = post("/v1/completions", {"model": MODEL, "prompt": ids,
         "temperature": 0, "max_tokens": 64, "skip_special_tokens": False})
print("raw:", repr(r["choices"][0]["text"]), r["choices"][0]["finish_reason"])
```

Recorded on the lane above, 2026-10-13:

| Request | `content` | reasoning field | `finish_reason` | completion tokens |
|---|---|---|---|---|
| prompt tail, thinking on | `<think>`, `\n` after the assistant header | | | |
| thinking on, run 1 | `null` | `"B"` | `stop` | 2 |
| thinking on, run 2 | `null` | `"B"` | `stop` | 2 |
| thinking off | `"B"` | absent | `stop` | 2 |
| raw completion, thinking-on prompt | `"B"`, no `</think>` anywhere | | `stop` | 2 |

The trap is present when the thinking-on rows have empty `content`, the answer
in the reasoning field, `finish_reason: "stop"`, and the raw completion
contains no `</think>`. It is absent if `content` carries the answer on the
thinking-on rows, or if the raw completion closes the block. One question is a
probe, not a rate: run a handful of your own short items before concluding it
is absent.

In a harness, the bucketing rule is the durable check: **empty `content`, a
non-empty reasoning field, and `finish_reason: "stop"`** is its own outcome.
Do not score it as a wrong answer and do not merge it with the
`finish_reason: "length"` bucket from trap 12.

**The fix.** In order of preference:

1. **Thinking off for direct-answer work.** Multiple choice, short Q&A,
   classification and extraction. The template then closes the block itself
   and the answer lands in `content`: 0/40 empties on the same slice.
2. **If thinking must stay on, rescue explicitly and say so.** When `content`
   is empty, `finish_reason` is `stop`, and the raw completion has no
   `</think>`, the reasoning field is the answer; take it, and record that the
   row was rescued so the number can be audited. Do not apply the same rescue
   to `finish_reason: "length"` rows, where the reasoning field is an
   unfinished trace (that is
   [trap 65](65-parser-only-rescue-kwarg.md)'s caveat, from the other side).
3. **Report both numbers when comparing thinking on against thinking off.**
   The as-delivered score measures the serving contract; the rescued score is
   closer to what the model knew. Publishing only the first attributes a field
   placement to the model.

A parser change that files a short, close-tag-less, `stop`-finished
completion as content would also recover these rows. It was not attempted
here, and it would trade this failure for misfiling genuine unclosed
reasoning as content, so it is not recommended as a default.

**Found.** 2026-10-13, first benchmark pass on a fresh MiniCPM-V 4.7 bring-up,
when the thinking-on run scored 64.2 against 75.0 for thinking off, and the
two categories where the loss concentrated were full of empty `content` rows
with a letter in the reasoning field.

**Attribution.** Blackwellboy. Related:
[trap 38](../template/38-template-owns-the-opening-think-tag.md) (who owns the
opening tag), [trap 64](64-answer-lands-in-reasoning-on-toggle-conflict.md)
(the same null reached by a toggle conflict),
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) and
[trap 16](../evaluation/16-finish-reason-is-not-a-failure-signal.md) (why
`finish_reason` has to be part of the bucket).
