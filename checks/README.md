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

Exit codes: 0 forensics complete (read the verdicts), 1 lane unreachable,
2 completed with a blocking finding (stripped reasoning, or an undocumented
kwarg that changes assembly).

Jinja2 is used for the local render path if importable, but it is optional.
