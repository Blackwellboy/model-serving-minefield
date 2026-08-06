# U08: one extra channel, and the chat endpoint throws

**Reported by @shuaills.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer reproduced.** @byjiang1996 wrote
"Successfully reproduced the issue" and posted the evidence. That is the
strongest thing this tier says.

**Issue state: closed, not fixed.** Closed on 2025-10-10 by an inactivity bot,
with `bug` and `high priority` still attached and no fix referenced in the
thread. **A stale-bot close is not a fix.**

**Primary source.** [sgl-project/sglang#8976, "Chat Completion API fails when
Harmony models generate commentary channel
messages"](https://github.com/sgl-project/sglang/issues/8976). Read on
2026-07-28: body and both comments, including the maintainer reproduction.

**Symptom.** `/v1/chat/completions` raises a `ValueError` on a Harmony-format
model, the gpt-oss family, and it is intermittent in the worst way: the same
prompt succeeds most of the time. Whether it fires depends on how many channels
the model happened to emit, which is a property of the generation and not of
your request. So it looks like load, or a race, or a bad deploy.

**Mechanism, as stated upstream.** The Chat Completion path assumes a Harmony
model produces exactly **two** kinds of message: `analysis` (reasoning) and
`final` (the response). Harmony also defines a **`commentary`** channel, used
for tool calls and preambles. When one appears, the output message array has
three entries where the code expects two, and the handler raises rather than
degrading.

@byjiang1996 reproduced it and confirmed the shape: `output_msgs` sometimes
carries `analysis`, `commentary` and `final`, and noted this matches the
published gpt-oss Harmony specification. The extra channel is the model doing
what it is documented to do.

**Why this is worth an entry, and why the closure does not weaken it.** This
is the tier's clearest case for existing. A maintainer reproduced it, the
labels say `high priority`, and then nothing happened for two months and a bot
closed the tab. Anyone searching the tracker today sees a closed issue and
reasonably infers it was resolved. Nothing in the thread supports that
inference.

The intermittency is the expensive part. A failure that tracks a channel the
model emits **only sometimes**: more often with tools, which is when you care
presents as flakiness. Flakiness gets retried, rate-limited, or blamed on the
client, and the class of the bug is not discoverable from the outside.

Two neighbours in this registry: trap
[64](../traps/reasoning/64-answer-lands-in-reasoning-on-toggle-conflict.md),
where template and parser disagree about channels and the answer is delivered
as reasoning, and trap
[45](../traps/quantization/45-fa-all-quants-cpu-fallback.md) for the general
shape of an unhandled case that is not an error condition. This one at least
throws, which makes it the honest member of the family.

**What we have not done.** Nobody here has reproduced this. We have SGLang
first-party on our own hardware but have never served a Harmony-format model
on it, and we hold no gpt-oss checkpoint on the machines SGLang runs on. We
have also **not** checked whether SGLang has since restructured this path: the
issue being closed-stale tells you nothing either way, and confirming the fix
is as valuable here as confirming the bug.

## If you have this stack

SGLang and any gpt-oss / Harmony-format checkpoint. Under an hour. The trick is
forcing the channel rather than waiting for it.

1. Serve the model with SGLang's Harmony support and use
   `/v1/chat/completions`.
2. Make the `commentary` channel likely: send a request **with tools** and a
   prompt that invites a preamble before acting, "explain what you are about
   to do, then call the tool" is the shape.
3. Run 30 requests. Record HTTP status and, on failure, the exception type and
   the channel list the model produced.
4. Control: identical prompts **without** `tools`, where the commentary channel
   is much less likely.

**CONFIRM.** `ValueError` on the responses whose output carried a `commentary`
message, at a rate materially above the no-tools control, with the endpoint
returning 200 on the two-channel responses. Report your SGLang version, the
report is from 2025-08 and the version is the whole question now.

**REFUTE.** Every request returns 200 including those whose output carried a
commentary message. **This is the more likely and the more useful outcome**,
and it should be reported with the same care as a confirmation: it would move
this entry to `closed, fixed` and name the version, which is information
nobody currently has.

**Do not settle this by reading the tracker.** The issue is closed and the bug
may or may not be. That gap is the reason this entry exists.

## Attribution

Reported by @shuaills. Reproduced by @byjiang1996, who also connected the
behaviour to the published Harmony specification. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).
