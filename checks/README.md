# Checks

Runnable checks that catch registry entries. Stdlib-only where possible so
they run anywhere the lane is reachable.

## preflight_template.py

Template forensics. Answers the question every request-shaped check misses:
what does the model actually see at turn N?

Reports three things:

- **Assembly diff.** Renders the actual prompt for a marked three-turn
  conversation and reports whether the prior assistant turn's reasoning is
  **preserved or stripped** (Trap 04). Refuses to certify a lane whose
  assembled history drops the marker.
- **Injection and coercion.** Whether the template injects content, merges
  messages, or rewrites roles (system merged into user, and so on).
- **Kwarg surface.** Enumerates every chat template kwarg the Jinja actually
  reads and diffs it against what the model card documents (Trap 04
  corollary, Trap 07). Anything read-but-undocumented is an untested
  variable.

Usage:

```bash
python3 checks/preflight_template.py --base-url http://HOST:PORT/v1 \
    [--model NAME] [--api-key KEY] \
    [--template-file path/to/chat_template.jinja] \
    [--documented-kwargs enable_thinking,thinking_mode] \
    [--kwargs-on '{"enable_thinking": true}'] \
    --json results/template_forensics.json
```

Exit codes: 0 forensics complete and nothing blocking, 1 lane unreachable,
2 completed with a blocking finding (stripped reasoning, or an undocumented
kwarg that changes assembly), **3 ran but inspected nothing** (no render path
was available, so no assembly could be examined).

Exit 3 is new. This previously exited `0` when no render path was available,
so a CI gate keyed on the exit code read "I could not look at anything" as
"nothing is wrong". That is a pass over an empty comparison set, and it is
the defect described in
[the check contract](../CONTRIBUTING.md#contributed-checks-must-be-able-to-fail).
If you gate on this check, treat anything other than `0` as not-clean.

Jinja2 is used for the local render path if importable, but it is optional.

## The contract every check here must satisfy

```bash
python3 checks/tests/test_check_contract.py
```

A check that cannot report a problem is worse than no check, because it emits
a clean verdict a reader will act on. Every check in this directory declares
two controls at module level, and the harness runs them:

- `NEGATIVE_CONTROLS`: inputs that **must** make the check fail. Writing one
  is how you find out your assertion was unfalsifiable.
- `EMPTY_SET_CONTROL`: the check run with nothing to compare, which must
  **not** report success.

Both run in-process against synthetic fixtures: no lane, no network, no
weights. The rule and the two defect shapes it catches (an assertion whose
sentinel is also in its own input, and a PASS over an empty comparison set)
are in
[CONTRIBUTING](../CONTRIBUTING.md#contributed-checks-must-be-able-to-fail).
If you add a check here, add its controls in the same PR.

Optionally a check may also declare `REGRESSION_ASSERTS`, a list of
`(name, callable)` where the callable returns `True` if a specific past defect
is still dead. That is a different thing from a negative control, which feeds
an input to the check and reads the check's own verdict, and it has its own
slot so that a guard does not have to be written inverted and make
`NEGATIVE_CONTROLS` misleading.

**Shell checks are covered too.** A non-Python check declares its controls in
a sidecar at `checks/tests/controls_<stem>.py`, and a non-Python check with no
sidecar fails the build. Discovery used to glob `*.py` only, so
`util_vs_power_tell.sh` escaped the contract entirely while the harness
reported `ALL PASS (8 checks conform)`: the right count over the wrong set.

The harness is itself mutation-proven: reintroducing the vacuous pass, making
a negative control unfailable, deleting either declaration, deleting a shell
check's controls sidecar, or a regression assert coming back false each fail
the build. A harness that cannot fail would be the very defect it tests for,
which is also why it refuses to pass over zero discovered checks.

## Tests

```bash
python3 checks/tests/test_preflight_kwargs.py
```

Regression coverage for `enumerate_kwargs`, the part that decides which
identifiers are caller-supplied `chat_template_kwargs`. It got that wrong in
both directions at once: Jinja tests, filters, macro parameters and
`namespace(...)` keyword arguments were reported as kwargs (four of them
raising BLOCKING findings on a real vendor template), while the canonical
idiom `{% set x = x if x is defined else D %}` made the genuine kwargs look
like local assignments and suppressed them. The fixtures are written in the
test file rather than vendored, so it carries no third-party template text.
Set `MINEFIELD_TEMPLATE_DIR` to a directory of `*.jinja` files to also run it
over real templates on your own disk; that arm skips when the variable is
unset.
