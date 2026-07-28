# TensorRT-LLM

**We have measured nothing on this stack, and we hold no upstream reports about
it either.** This page exists because "no page" and "no problems" look
identical from outside, and they are not the same thing. Absence here means
nobody has reported to us, not that the stack is clean.

**What we have.** Zero entries. One passing mention, in trap
[44](../traps/quantization/44-fp4-dequant-scale-swizzle-layout.md), where
`trtllm`'s FP4 scale-layout convention is named as a **contrast** to the one
that broke: it wants `do_shuffle=True` for the B matrix and accepts either
block shape. That is a fact about a kernel convention we had to learn to
explain a different stack's bug. It is not coverage.

Nobody here has run TensorRT-LLM.

## Why the gap, stated honestly

TensorRT-LLM's unit of deployment is a **compiled engine**, built per model,
per precision, per parallelism layout, per GPU architecture, and often per
maximum batch and sequence length. Our fleet's serving work is on runtimes that
load a checkpoint. Nothing about that makes the stack uninteresting; it makes
it a separate project rather than a flag on an existing one.

## Which of our mechanism classes most likely apply, and why

These are hypotheses. They are here to narrow a stranger's search, not to claim
a finding. Each names the measured entry the class comes from.

**The quant label is not the kernel path**: trap
[10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md), with
traps [44](../traps/quantization/44-fp4-dequant-scale-swizzle-layout.md),
[45](../traps/quantization/45-fa-all-quants-cpu-fallback.md) and
[90](../traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md).
**This is the class we would look at first**, and TensorRT-LLM should be the
*most* exposed stack in the registry to it, for a structural reason: the
build-time plugin and kernel selection is exactly the place where a label and a
path diverge, and once the engine is built the choice is frozen inside an
artifact whose filename says only what you asked for. A checkpoint runtime can
at least be interrogated at load. Trap 44's whole content is that two
frameworks disagree about an FP4 scale layout and the wrong one yields cosine
0.92 and a subtly worse model, with no error, and `trtllm` is one of the two
conventions in that entry.

**A stale build misses its own architecture's kernel**: traps
[46](../traps/versioning/46-stale-build-missing-arch-kernel.md) and
[90](../traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md).
Engines are architecture-specific by construction, and the failure mode we
measured is that the fallback is *silent* and shows up as power draw rather
than as an error.

**Advertised context is not usable context**: traps
[61](../traps/evaluation/61-advertised-window-fails-silently.md) and
[55](../traps/evaluation/55-supported-context-is-not-trained-context.md). Here
there is a second, stack-specific edge: an engine is built with a maximum
sequence length. What happens at the boundary between the *model's* window and
the *engine's* is a question nobody has answered publicly, and it is the sort
of place trap 61's failure, accepted, counted exactly, answered from nowhere
near the start, lives.

**Accepted and ignored**: traps
[07](../traps/reasoning/07-reasoning-effort-silently-ignored.md),
[77](../traps/reasoning/77-only-one-request-field-is-validated.md),
[78](../traps/tools/78-tool-choice-accepted-and-ignored.md). Any OpenAI-shaped
front end over a non-OpenAI engine has to map request fields onto engine
capabilities, and every stack we have measured drops at least one field
silently at that seam.

## How you would test for these

You need no permission and no coordination with us.

1. **Run the [doctor](../doctor/) against the endpoint.** It is a single
   stdlib file, it talks to any OpenAI-compatible server, and it has never met
   this stack. Every check it makes is request-shaped, so a first contact costs
   minutes. Historically **every** stack it has met produced at least one
   surprise on first contact, including one clean verdict that was wrong.
2. **For the kernel-path class:** build the same model twice at nominally the
   same precision with different plugin or quantization settings, and compare
   outputs on fixed prompts at temperature 0 *and* compare decode throughput.
   Trap 10's finding is that the tell is a runtime one, speed, power, a log
   line, not the label.
3. **For the context class:** send a prompt at the engine's maximum, at the
   model's advertised maximum, and at 1.5x each. Record HTTP status, the usage
   block's prompt token count, and whether the answer reflects content from the
   **start** of the prompt. Trap 61's whole point is that the first two can
   look perfect while the third fails.
4. **For accepted-and-ignored:** send one request with a deliberately
   misspelled parameter and an identical one without it. A 200 for both means
   nothing you set is confirmed to have taken effect. That is trap 77's probe
   and the doctor runs it first for this reason.

## How to report a finding

Open an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml).
Four plain questions, no formatting expected, and a maintainer writes the
entry and credits you. If you have measurements, the format that helps most is
in [CONTRIBUTING](../CONTRIBUTING.md#sending-measurement-data): raw rows rather
than aggregates, the exact build command, and one line on hardware.

**A negative is worth reporting too.** "I ran the doctor against TensorRT-LLM
and it was clean on all of it" would be the first thing anyone knows about this
stack, and it would take this page's first sentence away, which is the point.
