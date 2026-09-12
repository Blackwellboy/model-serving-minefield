# Repro -> fix -> known-good pin contract

A Minefield entry is most useful when it tells a reader not only **what broke**, but exactly **where the trap exists and what immutable pin closes it**.

For a trap with an identified fix, preserve this chain whenever the upstream project exposes immutable revisions:

```text
BROKEN_PIN=<commit/tag/image/model revision known to exhibit the trap>
REPRO_BEFORE=PASS|NOT_RUN|INCONCLUSIVE
FIXED_BY=<PR/commit/change that addresses the mechanism>
KNOWN_GOOD_PIN=<first or tested immutable revision known not to exhibit the trap>
REPRO_AFTER=PASS|NOT_RUN|INCONCLUSIVE
```

`PASS` means the stated reproduction behaved as expected for that side of the transition: the trap reproduced before the fix, or the same check no longer reproduced it after the fix.

## Rules

1. **Do not invent a pin.** If only a mutable branch name or release family is known, record that fact and leave the immutable pin unknown.
2. **A workaround is not a closing pin.** Record workarounds in **The fix**, but only populate `KNOWN_GOOD_PIN` when the trap is actually absent in that tested revision/configuration.
3. **Use the same mechanism-level check before and after.** A green unrelated test suite is not `REPRO_AFTER=PASS`.
4. **Keep configuration identity attached to the pin.** Runtime version, image, model revision, quantization, relevant flags, hardware-sensitive conditions and other mechanism-critical inputs still belong in **Stacks and builds bitten**.
5. **Do not overclaim first-fixed ancestry.** If you tested one later revision and did not bisect the exact first good commit, say `tested known-good pin`, not `first fixed in`.
6. **Negative evidence stays visible.** If the supposed fix does not close the reproduction, record `REPRO_AFTER=INCONCLUSIVE` or the failed result rather than silently moving the pin.
7. **Public source links should resolve to immutable objects where possible.** Prefer commit SHAs, immutable image digests, exact tags/releases, and exact model revisions over `main`, `latest`, or an unpinned container tag.

## Finished entry format

When a closing pin is known, place a compact block immediately after **The fix**:

```markdown
**Fix/pin closure.**

- `BROKEN_PIN=` ...
- `REPRO_BEFORE=` ...
- `FIXED_BY=` ...
- `KNOWN_GOOD_PIN=` ...
- `REPRO_AFTER=` ...
```

If no immutable closing pin exists yet, say so explicitly rather than omitting the state:

```markdown
**Fix/pin closure.** `KNOWN_GOOD_PIN=UNKNOWN`; workaround only / fix not yet independently closed.
```

This contract does not change the evidence status vocabulary. It adds version-transition provenance so a future reader or agent can answer two practical questions safely: **am I on a known-bad revision, and what exact tested revision gets me out of it?**
