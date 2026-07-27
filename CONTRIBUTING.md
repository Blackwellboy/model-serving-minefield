# Contributing an entry

The registry's value is that every entry is measured, not inferred. Follow
the format and the evidence bar below and your entry will fit.

## Two ways in

1. **Easy door (most entries should start here).** Open an
   ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml).
   Four plain questions, no formatting, no evidence checklist. A maintainer
   verifies what can be verified, writes the entry, credits you, and links
   your issue; the workflow is documented in
   [MAINTAINING.md](MAINTAINING.md). The evidence bar below applies to the
   finished entry, not to your report.
2. **Full door: PR with a complete entry.** Add one file under the right category
   directory, `traps/<category>/NN-short-slug.md` (next free global number;
   categories are listed in the README), add a row to the symptom table in
   `README.md`, and open a PR. The PR template walks the checklist.
   Categories: template, tools, reasoning, quantization, routing, runtime,
   memory, evaluation, versioning. If none fits, propose a new one in the PR.

## Where coverage is thin

Absence from this registry means nobody has reported it here, not that it is
safe. These are the gaps we know about, and they are the most useful place to
send a report:

- **Serving stacks with no entries at all: Ollama, SGLang, TensorRT-LLM,
  text-generation-inference.** Two candidates are already sitting in
  [mining/](mining/) unresolved because we could not test them: a
  thinking-plus-tools failure that did not reproduce on vLLM and looks
  Ollama-side, and an SGLang reasoning-parser null-content report. Either
  could be settled by one person who runs that stack.
- **Model families beyond Laguna S 2.1 and the Qwen 3.5/3.6 line.** Most of
  what is here was measured on two families because those are the weights we
  have.
- **Hardware beyond DGX Spark class, Apple silicon, P100, Strix Halo and
  RTX PRO 6000.** Datacenter parts and ROCm are entirely unrepresented.

## Sending measurement data

If your report comes with data rather than a description, this is the format
that costs you least and helps most:

- **Raw rows, not aggregates.** One row per request or turn (prompt or
  prompt id, whether thinking fired, reasoning and completion token counts,
  finish reason). We would rather compute the statistics ourselves so they
  are comparable to the ones already here. Do not pre-summarize.
- **The exact serve command or config** you launched with: engine and
  version, model build and quantization, sampling parameters, relevant flags.
- **One line on hardware.**
- **Say explicitly that you are happy for the data and the credit to be
  published.** We will not publish contributed data without that sentence.

Contributed data is labelled **"contributor-measured, conditions as
reported"** everywhere it appears and is never silently pooled with
measurements taken here. It can be cited as a corroborating or diverging
report at that label immediately; it feeds a headline claim only after
someone reproduces it. That is the same bar our own numbers are held to, and
it is not a comment on your work.

Scrub anything you would not want public before you send it. We are not set
up to receive confidential data and will not accept it.

## Entry format

One trap per file. Use these sections, in this order:

```markdown
# Trap NN: short name

**Found by <the handle they publish under>.**

**Status: reproduced here | reported by others | under test.** One line on
who measured it and where. "Reproduced here" means you ran it and can link
or produce the raw; "reported by others" means credited and linked, not
independently reproduced; "under test" means a replication is running.

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

## Credit

Credit is the default, not a courtesy. Contributors are named at the top of
the entry (the **Found by** line), in the Attribution section, and in
[HALL_OF_FAME.md](HALL_OF_FAME.md), by the handle they publish under, unless
they ask otherwise. Use a generic label for anything not publicly
attributable.

## House style

Plain language. No hype. Counts and conditions next to every claim. Generic
references for tools that are not public ("a spine-probe runner") and named
references for tools that are.
