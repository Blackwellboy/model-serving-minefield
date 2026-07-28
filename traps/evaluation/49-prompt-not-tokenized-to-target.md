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

**Check script.** The runnable version of this check is in review separately: every check in this repo must declare the negative and empty-set controls described in [the check contract](../../checks/README.md), and this one does not yet. The assertion above is the check; the script is a convenience wrapper for it.
