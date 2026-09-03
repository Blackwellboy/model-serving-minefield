# Trap 138: n-gram prompt lookup can duplicate tokens inside structured output

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported.** On the reported pinned
vLLM lane, draftless n-gram (prompt-lookup) speculation produced malformed JSON
at temperature 0. Removing only the n-gram speculative configuration removed
the same malformed cases. The registry has not independently reproduced the
engine behavior.

**Symptom.** Structured-output requests return HTTP 200 with a normal
`finish_reason: stop`, but the response body is not valid JSON because an
ordinary token or key is duplicated next to a prior occurrence. The measured
examples included shapes equivalent to:

```text
"audit_passed":false":false
"company":"company":"Northwind Freight"
```

The surrounding prose can remain coherent, so a caller that does not parse the
payload strictly may pass the corruption downstream as if the request
succeeded.

**Mechanism.** The measured lane used vLLM's draftless n-gram prompt-lookup
speculation. Every duplicated fragment observed in the failing structured
responses had appeared earlier in the same request, matching the surface that
the prompt-lookup matcher searches. A single-variable A/B separated the engine
path from the checkpoint: with the n-gram speculative config enabled, 3 of 12
schema cases returned malformed bodies; with speculation removed, those same
malformations disappeared. One remaining off-arm miss was valid JSON with an
incorrect value, so it is not part of this trap.

This is not the same evidence class as a draft-model speculative decoder
mangling special-token frames. The measured path used no draft model: it was
vLLM's n-gram prompt lookup, and the corruption was duplication of ordinary
JSON tokens/keys.

**Stacks and builds bitten.** Contributor-measured on vLLM `0.28.0`, aarch64,
with Qwen3.8-27B BF16 weights on NVIDIA GB10 Grace Blackwell. The contributor
reported the same malformed cases on the abliterated sibling under the same
serve configuration. The measured speculative configuration was:

```json
{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":3,"prompt_lookup_min":1}
```

Other n-gram widths/ranges, other checkpoints, other engine versions, and
speculative decoding with a draft model were not established by this report.

**The check.** Run a matched structured-output A/B in which the only serve
variable is the n-gram speculative configuration. Use temperature 0, retain raw
response bodies, require HTTP/process success in both arms, and parse every
body strictly rather than scoring only semantic fields:

```bash
curl -s "$BASE/v1/chat/completions" -d @schema_prompt.json \
  | jq -e '.choices[0].message.content | fromjson' >/dev/null || echo MALFORMED
```

For attribution, compare malformed bodies token-by-token. A repeated ordinary
token/key adjacent to an earlier occurrence is the reported signature. A random
parse failure, transport error, wrong served model, tool-parser mismatch, or
special-token corruption is not enough to call this mechanism.

**The fix.** Disable the reported n-gram prompt-lookup speculative config on
structured-output lanes unless the exact engine/model/config combination has
passed a strict-parser A/B. If keeping the optimization, gate deployment on
machine parsing of every structured fixture and re-run the check after engine
or speculative-config changes.

**Found.** 2026-09-03, during a Qwen3.8 schema-conformance comparison on DGX
Spark.

**Attribution.** **@scottleimroth** - finder and contributor measurement.

**Related.** [62](62-speculative-drafter-garbles-special-token-frames.md)
(speculative decoding can corrupt output through a different draft-model /
special-token mechanism), [52](52-speed-measured-on-a-broken-config.md)
(correctness must gate performance claims), and
[37](37-zero-across-every-arm-is-your-harness.md) (separate engine/model faults
from instrument faults before scoring the checkpoint).
