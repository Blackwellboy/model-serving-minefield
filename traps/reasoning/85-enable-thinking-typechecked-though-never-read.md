# Trap 85: the server type-checks `enable_thinking` by name even when the template never reads it, and rejects only the string form

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, on a Mistral-family Q8_0 GGUF of
unstated provenance, llama.cpp `b9878-2da668617`, `--jinja`. The template
contains no reasoning branch at all: it never mentions `enable_thinking`,
`thinking`, or any think tag.

**Symptom.** A client that has always sent `chat_template_kwargs:
{"enable_thinking": "false"}` starts returning HTTP 400 the moment it is
pointed at a non-reasoning lane. The knob it is setting does nothing on that
lane in either direction, so the hard failure is doubly surprising.

**Mechanism.** `enable_thinking` is special-cased by name in the server's
kwarg handling and validated as a boolean, independently of whether the
selected template consumes it. Everything else is passed through untyped.
Measured, same lane, same template, `max_tokens=10`, `temperature=0`:

| kwarg sent | result |
|---|---|
| `{"enable_thinking": true}` | 200 |
| `{"enable_thinking": 1}` | 200 |
| `{"enable_thinking": 1.0}` | 200 |
| `{"enable_thinking": null}` | 200 |
| `{"enable_thinking": "true"}` | **400** `invalid type for "enable_thinking" (expected boolean, got string)` |
| `{"enable_thinking": "false"}` | **400** same message |
| `{"thinking": "high"}` | 200 |
| `{"zzz_nonsense": "somestring"}` | 200 |
| `{"zzz_nonsense": 7}` | 200 |

So: one name is type-checked, only against strings, and integers and floats
pass straight through the same check. Every other kwarg name, invented or not,
is accepted at any type. None of the accepted ones had any effect here, because
the template reads none of them.

**Why this is the wrong shape.** Acceptance and effect are independent, and so
are rejection and relevance. On this lane the server rejects a knob it does not
use, and accepts nine knobs it also does not use. Neither the 200 nor the 400
tells you anything about whether the template read the value.

**Check it.** Send the string form and the bool form of `enable_thinking` and
compare status codes; then grep the template for the kwarg name. The pair of
answers is the finding. Clients that build kwargs from environment variables,
YAML, or query strings produce strings by default, which is what makes the
string row the common one in production.

**Scope.** llama.cpp `b9878-2da668617` serving one Mistral-family Q8_0 GGUF of
unstated provenance. The typed-by-name behaviour is a server property, so it
should travel across models on this build; the "no effect" half is a property
of this template.

**Related.** The truthiness-coercion trap is the mirror image: there a string
is *accepted* and silently coerced to true. Here a string is *rejected*
outright. Same two characters in the request body, opposite failure.

**Found.** 2026-07-28.
