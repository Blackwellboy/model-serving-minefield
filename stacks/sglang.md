# SGLang

**0 entries name SGLang** in their evidence surfaces (see
[how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)).

This page exists anyway, because "no page" and "no entries" read the same from
outside and they mean different things. **Zero entries here does not mean this
stack is clean.** It means nobody has reported one, which for most of this
registry's life was because nobody here had run it.

## Where this stack actually stands

Two things have happened, and neither of them is a published entry yet.

**It is not infeasible on this hardware class.** The packaging question was
settled on 2026-07-28 and the working is published:
[SGLang on GB10, feasibility](../mining/2026-07-28-sglang-on-gb10-feasibility.md).
The arm64 wheel exists, `sglang[all]` resolves cleanly on CUDA 13, and the
open risk named there was whether `sm_121` appears in the torch arch list.
That note is packaging only. No server was started for it.

**A server has since been started, first-party, and the results are not
published here yet.**
[CONTRIBUTING](../CONTRIBUTING.md#where-coverage-is-thin) carries the dated
correction: SGLang has been brought up on our own hardware, the
reasoning-parser null-content report that was the standing open ask has been
tested, and its disposition is written and awaiting publication. Until those
land, **this page has nothing first-party to show you**, and saying so is more
useful than an empty table implying the stack was examined and found clean.

The blocked-candidate records from before that session are still worth reading
for what they rule out and why:
[R2 blocked, not testable](../mining/2026-07-27-r2-blocked-not-testable.md)
and
[the blocked llama.cpp candidates, adjudicated](../mining/2026-07-28-r2-llamacpp-queue-dispositions.md).

## What to check anyway, from the cross-stack classes

None of these is an SGLang finding. They are the registry's stack-independent
classes, and they are the cheapest things to run on a server nobody here has
characterised. If one of them bites you on SGLang, that is exactly the report
this page is missing.

**1. Read every plausible spelling of the reasoning field.** The name of the
field carrying chain-of-thought is a property of the serving stack, not of the
model, and one server has carried three names split by route
([trap 01](../traps/reasoning/01-reasoning-field-two-names.md), **Core**). Use
`.get` on `content` as well: an empty channel is sometimes an absent key
rather than an empty string.

**2. Send your thinking-off switch, then check that thinking is actually
off.** Do not check the status code. A request field that a server does not
recognise is very often accepted, returns 200, and changes nothing, so a whole
thinking-off arm gets measured on a thinking lane
([trap 77](../traps/reasoning/77-only-one-request-field-is-validated.md),
**Core**). Separately, a server-side off switch can be a default that a client
kwarg overrides
([trap 29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)).

**3. Send one request that will hit the token ceiling, and look at what comes
back.** `finish_reason: length` with empty content scores as a capability
collapse rather than as a budget artifact, and there is no single ceiling that
makes it go away
([trap 12](../traps/evaluation/12-empty-content-at-token-ceiling.md), **Core**;
bucketing rule in [16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md)).

Two more that cost the most elsewhere and have no reason to spare a new stack:
prior-turn reasoning stripped from history
([04](../traps/template/04-history-reasoning-stripping.md), **Core**, the
registry's most dangerous entry because its symptom is a publishable number),
and the quant label not being the kernel path
([10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md),
**Core**).

## What the doctor can do here

The [doctor](../doctor/) talks to an OpenAI-compatible endpoint, and SGLang
serves one, so the request-shaped checks should run. **Should** is the right
word: no field report for this stack is published, and the doctor's own README
is explicit that a clean run is a statement about the handful of trap ids in
its `clean` count and never a bill of health. Run it, and if it reports
something odd or refuses to identify the stack, that is worth an issue on its
own.

## Where a report would help most

Anything at all. This is the emptiest page in the registry and the bar is low:
you do not need a writeup, a reproduction, or confidence that what you hit was
real. Four plain questions in the
[easy door](../../../issues/new?template=report-a-trap.yml), and a maintainer
does the rest. Scrub hostnames, paths and tokens out of anything you paste;
the form shows you how.

The most valuable single report would be **the reasoning field and the
thinking toggle**: which key the reasoning text arrives under, which spelling
of the toggle the server accepts, and what it does with the spellings it does
not accept. That combination is where this registry has found the most damage
on every other stack, and on this one it is unwritten.
