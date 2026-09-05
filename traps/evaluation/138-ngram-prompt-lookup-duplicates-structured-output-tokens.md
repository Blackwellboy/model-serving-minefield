# Trap 138: n-gram prompt lookup can duplicate tokens inside structured output

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported.** On the reported pinned vLLM lane, draftless n-gram (prompt-lookup) speculation produced assistant `content` strings that were intended to contain JSON but were malformed at temperature 0. Removing only the n-gram speculative configuration removed the same malformed cases. The registry has not independently reproduced the engine behavior.

**Symptom.** The OpenAI-compatible request itself succeeds: HTTP 200, a valid response envelope, and a normal `finish_reason: stop`. The corruption is inside `.choices[0].message.content`: the assistant content is supposed to be JSON, but an ordinary token or key is duplicated adjacent to a prior occurrence, so parsing that content string as JSON fails. The measured examples included shapes equivalent to:

```text
"audit_passed":false":false
"company":"company":"Northwind Freight"
```

The surrounding generated text can remain coherent, so a caller that checks only HTTP/envelope success or does not strictly parse the assistant content can pass the corruption downstream.

**Mechanism.** The measured lane used vLLM's draftless n-gram prompt-lookup speculation. Every duplicated fragment observed in the failing structured responses had appeared earlier in the same request, matching the surface that the prompt-lookup matcher searches. A single-variable A/B separated the serving path from the checkpoint under the reported fixture: with the n-gram speculative config enabled, 3 of 12 schema cases produced malformed assistant JSON content; with speculation removed, those same malformations disappeared. One remaining off-arm miss was valid JSON with an incorrect value, so it is not part of this trap.

This is not the same evidence class as a draft-model speculative decoder mangling special-token frames. The measured path used no draft model: it was vLLM's n-gram prompt lookup, and the corruption was duplication of ordinary JSON tokens/keys.

**Stacks and builds bitten.** Contributor-measured on vLLM `0.28.0`, aarch64, with Qwen3.8-27B BF16 weights on NVIDIA GB10 Grace Blackwell. The contributor reported the same malformed cases on the abliterated sibling under the same serve configuration. The measured speculative configuration was:

```json
{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":3,"prompt_lookup_min":1}
```

Other n-gram widths/ranges, other checkpoints, other engine versions, and speculative decoding with a draft model were not established by this report.

**The check.** Run a matched structured-output A/B in which the only serve variable is the n-gram speculative configuration. Use temperature 0. Preserve the successful raw OpenAI response envelope, require transport and HTTP success before judging model output, then extract and strictly parse the assistant `content` string:

```bash
raw=$(mktemp)
http=$(curl -sS -o "$raw" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  --data-binary @schema_prompt.json \
  "$BASE/v1/chat/completions") || {
    echo TRANSPORT_FAIL
    exit 2
  }

case "$http" in
  2??) ;;
  *) echo "HTTP_FAIL=$http raw=$raw"; exit 3 ;;
esac

jq -er '.choices[0].message.content' "$raw" > content.txt || {
  echo "ENVELOPE_INVALID raw=$raw"
  exit 4
}

jq -eRs 'fromjson' content.txt >/dev/null || {
  echo "MODEL_CONTENT_MALFORMED raw=$raw"
  exit 5
}
```

Keep `$raw` when the final parse fails so the emitted content can be inspected without conflating a transport error, HTTP error, or malformed OpenAI envelope with malformed model content.

For attribution, compare malformed content strings token-by-token across the n-gram-on and n-gram-off arms. A repeated ordinary token/key adjacent to an earlier occurrence is the reported signature. A random parse failure, transport error, wrong served model, tool-parser mismatch, or special-token corruption is not enough to call this mechanism.

**The fix.** Disable the reported n-gram prompt-lookup speculative config on structured-output lanes unless the exact engine/model/config combination has passed a strict-parser A/B. If keeping the optimization, gate deployment on machine parsing of every structured fixture and re-run the check after engine or speculative-config changes.

**Found.** 2026-09-03, during a Qwen3.8 schema-conformance comparison on DGX Spark.

**Attribution.** **@scottleimroth** — finder and contributor measurement.

**Related.** [62](62-speculative-drafter-garbles-special-token-frames.md) (speculative decoding can corrupt output through a different draft-model / special-token mechanism), [52](52-speed-measured-on-a-broken-config.md) (correctness must gate performance claims), and [37](37-zero-across-every-arm-is-your-harness.md) (separate engine/model faults from instrument faults before scoring the checkpoint).
