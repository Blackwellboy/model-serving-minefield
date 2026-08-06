# Trap 87: on llama.cpp `/props` reports the PER-SLOT context, exposes no trained context, and self-reports the props endpoint as disabled while serving it

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, llama.cpp `b9878-2da668617` serving a
Mistral-family Q8_0 GGUF of unstated provenance, launched
`-c 131072 -np 4 -fa on --jinja --slots --metrics` on a single consumer GPU.

**Symptom.** Three separate ways to get the context wrong on this stack.

**1. `/props` reports per-slot context, not served context.** The lane was
launched with `-c 131072` and four slots. `/props` returns:

```
default_generation_settings.n_ctx = 32768
total_slots = 4
```

and `/slots` agrees: four slots, `n_ctx` 32768 each. So `-c` on llama.cpp is
the **total** KV budget and it is divided across `--parallel`. A monitor that
compares the launch flag against the reported context will report a fourfold
mismatch that is not a mismatch. A capacity planner that reads 32768 and
multiplies by four is right; one that reads 131072 as a per-request limit is
wrong, and finds out at
`request (40089 tokens) exceeds the available context size (32768 tokens)`.

This confirms, on a third-party contributed target, TheTom's entry claiming
that the context size divides across parallel slots.

**2. There is no trained-context field.** A trained-context key appears nowhere
in `/props`, `/slots`, or `/v1/models`. The served-versus-trained comparison
that is one field lookup on some stacks requires reading `llama.context_length`
out of the GGUF header on this one. Any portable check keyed on a trained-context
response field returns COULD-NOT-CHECK here, and should say so rather than
passing.

**The coincidence that hides it.** On this file `llama.context_length` is
32768 and the per-slot context came out at exactly 32768. A checker comparing
the two numbers would print a clean match, having compared the trained context
against a per-slot figure that only equals it because 131072 divided by four
happens to land there. Change the parallel count and the "match" moves. Getting
the right answer from the wrong two numbers is the failure mode to guard
against here.

**3. `/props` says the props endpoint is off, in its own 200 response.**

```
"endpoint_props": false
```

returned by `/props` itself, HTTP 200, while `endpoint_slots` and
`endpoint_metrics` correctly report true for the flags that were passed. Do not
gate a probe on that field; call the endpoint and read the status code.

**What `/props` is genuinely good for on this stack**, and worth reading before
declaring a lane uncharacterised: `chat_format` (here `Content-only`, i.e. no
tool-call parser was generated for this template), `reasoning_format` (`none`),
`chat_template_caps.supports_preserve_reasoning` (`false`),
`modalities` (all false), `build_info`, and the full `chat_template` string.
Between them those fields settle several questions that are otherwise answered
by probing and guessing.

**Check it.** Launch with a total context and a parallel count, then read the
reported context from `/props` and confirm it is the total divided by the
parallel count.

**Scope.** llama.cpp `b9878-2da668617`. Server property, not a model property;
the served target only supplied the context numbers.

**Found.** 2026-07-28.
