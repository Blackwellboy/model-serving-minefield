# Contributing an entry

The registry's value is that every entry is measured, not inferred. Follow
the format and the evidence bar below and your entry will fit.

## Two ways in

1. **Issue first (lowest friction).** Open a
   [report-a-trap issue](../../issues/new?template=report-a-trap.yml) with
   the symptom and your stack. You do not need the mechanism. Someone (maybe
   you, later) turns it into an entry once the check exists.
2. **PR with a full entry.** Add one file under `traps/` named
   `NN-short-slug.md` (next free number), add a row to the symptom table in
   `README.md`, and open a PR. The PR template walks the checklist.

## Entry format

One trap per file. Use these sections, in this order:

```markdown
# Trap NN: short name

**Symptom.** What a reader would actually observe, first. The weird number,
the corrupted string, the impossible verdict. This is the section people
search.

**Mechanism.** What is actually happening between request and response, once
you know.

**Stacks and builds bitten.** Every stack, server, model, revision, and build
where this was observed. Be specific: "vLLM 0.25.1, model X rev abc1234,
NVFP4 build" beats "vLLM". If it produced a published number, say so.

**The check.** The concrete test that catches it. A command, a snippet, or an
exact assertion. A check the reader cannot run is a story, not a check.

**The fix.** What to change so the trap cannot bite.

**Found.** YYYY-MM-DD, and the context it surfaced in.

**Attribution.** Who found it, by the name or handle they publish under.
Link the raw data if it is public.
```

## Evidence bar

- **Measured, not inferred.** An entry states what was observed on a real
  serving path, with counts (0/42, 6/6, 28/30). A plausible mechanism with no
  measurement is an issue, not an entry.
- **State the stack and the build.** Server and version, model, revision
  hash, and quantization build. Thinking policy is known to differ by build
  at the same revision, so a revision alone is not enough.
- **Show the check.** Every entry ships the test that catches the trap, in
  runnable form. If the check needs more than a snippet, add a script under
  `checks/` and link it.
- **Symptom first.** Lead with what the reader observes, not with the
  mechanism. People arrive here holding a weird number.
- **Name what you cannot claim.** If you saw it on one stack, say one stack.
  If the mechanism is a hypothesis, label it a hypothesis and keep it out of
  the symptom and check sections.

## House style

Plain language. No hype. Counts and conditions next to every claim. Generic
references for tools that are not public ("a spine-probe runner") and named
references for tools that are.
