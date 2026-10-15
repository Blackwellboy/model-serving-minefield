# Trap 166: switching thinking or effort per request gives each setting its own prefix cache, even at the same prompt length

**Found by Blackwellboy.**

**Status: reproduced here** (runnable check below against the reader's own
endpoint; counts measured here on 2026-10-15).

**Symptom.** You vary reasoning per request: thinking on for some calls, off
for others, or a different effort level for hard questions. The prompt is the
same long system prompt and history every time, and prefix caching is on.
Yet the first request at each new setting is as slow as a cold start, and its
`usage.prompt_tokens_details.cached_tokens` is **0**, even though the request
just before it, with a different setting, had the whole prompt cached. This
happens between two thinking levels too: `low` and `high` render to the
**same** `prompt_tokens`, so nothing in your token accounting says the prompts
differ.

Measured on one lane with a fresh, uniquely salted system prompt of about
8,000 tokens and a one-word answer, settings in sequence, 4 runs (2 with
`low` and off, 2 with `low`, `high` and off). `prompt_tokens` varies by a few
tokens between runs with the salt; within a run `low` and `high` were equal
and off was 25 tokens shorter. Warm rows leave out the 4,096-token partial
hits described below.

| call | `cached_tokens` | time |
|---|---|---|
| `low`, first | **0** | 6.0-8.3 s |
| `low`, again | 7,936 of ~8,000 | 0.7 s |
| `high`, first (same `prompt_tokens` as `low`) | **0** | 8.2 s |
| thinking off, first | **0** | 5.6-8.0 s |
| thinking off, again | 7,808-7,936 | 0.4-0.5 s |
| back to `low` | 7,936 | 0.7-0.8 s |

Every one of the 10 first calls at a new setting started cold. Every one of
the 6 returns to a setting used earlier hit the cache, so the server keeps the
variants side by side; it does not evict one to make room for the other.

**Mechanism.** The reasoning setting is rendered into the prompt **in front
of** the shared text. A zero-token hit with an otherwise identical prompt means
the two renders already differ inside the first cache block, so no block of
the system prompt or history can be shared between settings. On this family
the effort instruction sits at the very top of the prompt
([trap 58](58-reasoning-effort-injects-hidden-preamble.md) shows the same
placement for the injected `max` preamble on V4); `low` and `high` differ in
content but not in length, which is why `prompt_tokens` hides it.

What it costs depends on the pattern. The first use of each setting pays a
full cold prefill of the shared prefix. After that, a switch re-prefills only
what was added to the conversation since that setting was last used, because
each variant's cache still covers its own older prefix. An agent that thinks
after a user message and skips thinking on tool steps pays this on every
switch, and on the measured lane it still came out at about thinking-off speed
(see [trap 165](165-thinking-off-for-agent-speed-costs-reasoning.md)): the
re-prefill is cheaper than thinking on every step. A client that picks the
effort level at random per request pays it far more often.

A second effect seen in the same runs, not explained and not part of this
trap: in 4 of 10 prompt variants the warm hit stopped at exactly 4,096 tokens
and stayed there for every later call of that variant (about 4 s instead of
0.7 s). It appeared on calls that had not switched, so it is not the switch.
The shape resembles [trap 129](../memory/129-prefix-cache-hit-min-across-kv-groups.md)
(the hit is the minimum across KV cache groups); that was not tested.

Neighbours: [trap 82](../template/82-system-prompt-relocates-to-last-user-turn.md)
moves the system prompt so the prefix changes every turn;
[trap 25](../template/25-empty-think-blocks-poison-prefix-cache.md) is history think
blocks breaking the cache; [trap 54](../evaluation/54-run-order-and-warm-cache-artifacts.md)
is what this does to a timing comparison that warms only one arm.

**Stacks and builds bitten.** DeepSeek-V4.1-Flash EXL3 2.9 bpw served by an
EXL3 build of vLLM with the `deepseek_v41` tokenizer and parsers and prefix
caching on, DSpark speculative decoding (k=3), tensor parallel 2 on two DGX
Spark (GB10) nodes. Settings sent as top-level `reasoning_effort: "low"` /
`"high"`, and thinking off as `reasoning_effort: "none"` plus
`chat_template_kwargs: {"enable_thinking": false}`. Not tested: other
families. A template that renders the reasoning switch after the system
prompt, or near the end, would share almost all of the prefix; the check
tells you which you have.

**The check.** Needs a server that reports `cached_tokens` (vLLM does with
prefix caching on). Use a fresh prompt so earlier traffic cannot warm it:

```python
import json, time, urllib.request, uuid
BASE, MODEL = "http://127.0.0.1:8000/v1", "YOUR-MODEL"
system = f"Run {uuid.uuid4().hex}.\n" + "\n".join(f"Note {i}: " + "lorem ipsum dolor sit amet " * 8 for i in range(150))
def call(tag, extra):
    body = {"model": MODEL, "max_tokens": 20, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": "Reply OK."}], **extra}
    req = urllib.request.Request(BASE + "/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time(); u = json.load(urllib.request.urlopen(req, timeout=300))["usage"]
    print(tag, u["prompt_tokens"], (u.get("prompt_tokens_details") or {}).get("cached_tokens"), f"{time.time() - t:.2f}s")
A, B = {"reasoning_effort": "low"}, {"reasoning_effort": "high"}   # or your thinking on / off switch
for tag, extra in [("A", A), ("A", A), ("B", B), ("B", B), ("A", A)]:
    call(tag, extra)
```

You are bitten if the first `B` call shows `cached_tokens` 0 (or a small
number) right after a fully cached `A`. If it shows nearly the whole prompt
cached, your template puts the switch late and per-request switching is cheap.

**The fix.** Keep the number of settings small and stable: pick one level for
thinking calls and one way of switching it off, rather than varying the level
per request. Warm each variant once at startup if the first-call latency
matters. When you compare settings for speed, warm both before timing, or the
comparison measures the cache rather than the setting. If the switching
pattern is frequent and the shared prefix is long, measure the whole session,
not single calls, before deciding it is worth it.

**Found.** 2026-10-15, measuring the cost of a per-step thinking schedule in
an agent harness.

**Attribution.** Blackwellboy.
