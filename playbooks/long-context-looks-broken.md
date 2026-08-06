# Playbook: long context looks broken

The window accepts your prompt. Nothing errors. The token count is exactly
what you expected. And the answer comes from nowhere near the start of the
document. Nine steps, in order, and the first three cost nothing but reading.

Nothing here is new. Every step is a published entry, sequenced. The case
study running through it is the DeepSeek-V4-Flash lane on its
[model page](../models/deepseek-v4-flash.md), where an advertised million-token
window rests on a 64K trained base.

---

## 1. Read the three ceilings before you trust any context number

**Guards:** [trap 61, a 1M advertised window and a 64K trained window](../traps/evaluation/61-advertised-window-fails-silently.md) (**Core**), [trap 55, supported context is not trained context](../traps/evaluation/55-supported-context-is-not-trained-context.md)

Advertised, served and trained are three different numbers, and none of them
is necessarily the usable one.

1. Read the checkpoint's `config.json` rope-scaling block. If it carries a
   YaRN or similar factor over an `original_max_position_embeddings`, the
   advertised window is that base times that factor, and **the base is the
   trained length**. Record both numbers.
2. Read the served file's own `context_length` metadata, and the model card's
   stated **training** context, which is usually in prose rather than in
   config.
3. State the training context next to every long-context number you publish,
   and never compare a rope-extended model against a natively-long one without
   labelling which is which.

## 2. Check whether the container had to override the engine's sanity check

**Guards:** [trap 61](../traps/evaluation/61-advertised-window-fails-silently.md) (**Core**)

Check whether the serving container sets a long-context override variable. Its
presence means the advertised length **did not pass the engine's own sanity
check**. That is a free signal and it sits in the launch environment.

## 3. Anchor with a shorter-context control

**Guards:** [trap 55](../traps/evaluation/55-supported-context-is-not-trained-context.md)

Run your battery at the model's native length as well as at the long length. A
model that scores well at native and collapses at eight times native is
telling you about extension, not about capability. Include a model that was
genuinely trained long in any long-context comparison.

## 4. Nonce the FRONT of the prompt, not the back

**Guards:** [trap 60, a cold prefill and a prefix-cache hit do not return the same answer](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md)

This is the step that makes retrieval provable, and the one most harnesses get
backwards.

Send one long prompt with a fact at position zero. Record the answer, the
`finish_reason`, and the cache-hit delta from the server's own metrics. Send
the **byte-identical** prompt again immediately and record the same three. If
the cache-hit fraction goes from roughly zero to roughly one and either the
answer or the finish reason changes, you have this trap. Two requests, no
configuration change, and it works on any server exposing prefix-cache
counters.

To measure the lane honestly afterwards, make every evaluation prompt unique
at the **front**, not just at the back. A per-item nonce in the first tokens
is what forces a genuine prefill.

## 5. Report cold and warm as separate numbers

**Guards:** [trap 60](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md)

There is no flag that makes the two paths agree, and disabling prefix caching
trades a large latency win for the worse of the two behaviours. The actionable
part is measurement discipline: report the two separately rather than
averaging them, state which one your benchmark measured, and treat a
long-context result that was not verified cold as an **upper bound** rather
than a result.

Related, if you are trying to isolate a single request from prior slot state:
whether `cache_prompt: false` isolates is a **per-build** fact. It does on one
measured llama.cpp build
([trap 88](../traps/runtime/88-cache-prompt-false-does-isolate-here.md)), which
is a third data point that does not reproduce two prior stacks. Do not assume
either way; measure it on your build.

## 6. Design the retrieval probe so a failure is unambiguous

**Guards:** [trap 61](../traps/evaluation/61-advertised-window-fails-silently.md) (**Core**)

Measure with a fact at position zero, **unique non-repeating filler**, and a
decoy at the tail, laddered across depths. Repeating filler lets a model
answer from pattern rather than from retrieval, and a probe that cannot fail
cannot pass either.

If you are chunking documents, note that the published lane's honest
instruction-following limit measured an order of magnitude below its trained
length and nearly two below its advertised one.

## 7. Check whether the prefix cache is engaging at all

**Guards:** [trap 47, prefix caching silently auto-disabled for hybrid architectures](../traps/runtime/47-prefix-caching-autodisabled-hybrid.md)

Two lines: the startup log line for the prefix-caching flag, and a behavioural
probe over three consecutive turns of the same conversation. If time to first
token stays flat as the conversation grows instead of falling after turn 1,
the cache is not engaging. On hybrid and recurrent architectures the engine
can auto-disable it and say so once, at startup.

There is no client-side fix. Choose the engine by workload shape and state the
shape whenever you publish a throughput number for a hybrid model.

## 8. Do not trust an introspection route about context

**Guards:** [trap 87, `/props` reports the PER-SLOT context](../traps/runtime/87-llamacpp-props-reports-per-slot-context.md), [trap 79, an out-of-range context request is accepted](../traps/memory/79-out-of-range-context-request-accepted.md)

- On one measured llama.cpp build, `/props` reports the **per-slot** context
  rather than the value you launched with, exposes no trained context at all,
  and self-reports the props endpoint as disabled while serving it. If you
  divide your launch context by your slot count and the introspection number
  matches, that is what you are reading.
- On another stack an out-of-range context request returns HTTP 200 with empty
  content and no clamp message. Read the model's declared context, assert you
  are under it, and log the value you sent next to every result. A run whose
  context parameter was not recorded cannot be diagnosed later.

## 9. Size the KV cache in bytes, and check the real memory limit

**Guards:** [trap 13, gpu-memory-utilization fractions on unified memory](../traps/memory/13-utilization-fraction-on-unified-memory.md), [trap 55](../traps/evaluation/55-supported-context-is-not-trained-context.md)

On unified memory, pin the KV cache in **bytes** instead of by fraction. The
flag pair to know: fraction for throwaway experiments, bytes for anything
shared or long-running. After serving, read the actual KV pool size from the
server logs and the OS's available memory, and ask whether either number was
chosen or merely happened.

The KV footprint at the advertised length is frequently the real limit anyway.
One reported stack allocated full-size KV for all 48 layers even though 36
were sliding-window with a 512-token span, which wedged a 128 GB box into swap
at 256K.

---

**Related playbooks.** [Before you publish an A/B](before-you-publish-an-ab.md)
before a long-context delta becomes a number.
[Porting a harness to a new server](porting-a-harness.md) if the harness is new
to this stack.
