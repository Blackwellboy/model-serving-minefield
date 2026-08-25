# Trap 49: the benchmark prompt does not tokenize to the length you named

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Symptom.** A large, clean, publishable performance gap between two implementations, in our case a
claimed **18x**: that shrinks to **2 to 3x** the moment the harness is fixed. Everything about the
result looks right: consistent across runs, monotonic, plausible mechanism ready to explain it.

**Mechanism.** The "4096-token" prompt was built as `'AI. ' * 400`, which tokenizes to **801
tokens**, and the `[:4096]` slice that was supposed to bound it was a **no-op** because the string
was already shorter. Both sides of the comparison ran an 801-token prompt while the table said 4096.

Because per-eval overhead amortizes with context length, running the *short* prompt exaggerated the
gap in exactly the direction that made the result interesting.

**Stacks and builds bitten.** Engine- and model-independent. This is a harness bug, and it is the
most embarrassing class in the registry precisely because nothing in the stack is at fault.

**The check.** **Assert the tokenized length, not the string length**, and log the server's own
count
for every benchmark prompt.

The tell that actually caught it: the KV-cache offset read **801** after a run labelled "4096
context". Any place your harness can observe a real token count, cache offset, server
`n_tokens`, `usage.prompt_tokens` on a cold request, should be asserted against the target, not
just printed.

```
$ python3 checks/tokenized_length_assert.py --base-url $URL --model $M --target 4096 --tolerance 0.02
  built prompt: 1600 chars
  server-reported prompt tokens: 801
  FAIL: 801 tokens vs target 4096 (-80.4%)
```

Related counting trap, same check: on some servers the API's prompt-token field is the **delta from
the cached prefix**, not the absolute prompt length, so a warm request under-reports. Verify on a
**cold** request, or read the server log's authoritative `n_tokens` line. We confirmed a 245K-target
prompt as `n_tokens = 246,722` that way.

**The fix.** Build benchmark prompts by tokenizing to the target, then decoding back, or grow the
filler until the measured token count is within tolerance. Record the achieved token count in the
result row next to the nominal one. If they differ by more than a couple of percent, the row is
invalid, not caveated.

**The wider rule this belongs to.** Never quote a savings or performance claim measured on a
truncated or otherwise unrepresentative distribution. We have had to retract twice: once for this,
and once for a "90% saved" figure that a full-distribution run disproved.

**Found.** 2026-04-11, when a cache-offset readout disagreed with the label on the run.

**Attribution.** TheTom.

### Addendum - 2026-08-25: character-labelled depth understates tokenizer depth (FlashRDMA portable serving)

**Status for this addendum: measured here, raw not published** (Blackwellboy; portable
cross-host serving harness). TheTom remains **Found by** for the entry. This addendum
corroborates only the shared class **nominal length ≠ realized token length**. It does
not claim to reproduce every detail of TheTom's original 18x→2-3x collapse story.

On a FlashRDMA portable serving depth suite, an earlier repetitive / character-oriented
"8K"-style fixture tokenized to only about **1.5K** model tokens. Depth cliffs and
transport timing conclusions therefore reflected a much shallower prompt than the label
claimed. The corrected suite asserted the **target-model tokenizer count before serving**
and published verified fixtures:

| Label | Tokenizer-verified prompt tokens |
|---|---:|
| short | 61 |
| 1K | 1015 |
| 4K | 4019 |
| 8K | 8004 |

Performance conclusions moved once depth was real: an "8K" result is only an 8K result
when the measured/tokenizer-counted length is ~8000, not when the file has ~8000
characters or the operator intended 8K. The check is unchanged - assert tokenized length
(and cold server-observed counts) beside every depth label.

**Check script.** [`checks/tokenized_length_assert.py`](../../checks/tokenized_length_assert.py) declares the negative and empty-set controls required by [the check contract](../../checks/README.md), so it is able to report a problem. The inline assertion above remains the check; the script is a convenience wrapper for it.
