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

Contributed data is normally linked rather than committed. The one case where
raw data is committed to this repo is a calibration entry whose number other
entries cite, and then only with a runnable verifier beside it; the conditions
are in [MAINTAINING.md](MAINTAINING.md#shipping-raw-data-in-the-repo).

## Entry format

One trap per file. Use these sections, in this order:

```markdown
# Trap NN: short name

**Found by <the handle they publish under>.**

**Status: <label> (<evidence pointer>).** One line on who measured it and
where. The label comes from the closed vocabulary below, and the evidence
pointer is not optional. See [Status vocabulary](#status-vocabulary).

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

## Status vocabulary

Every entry carries exactly one status label from this closed set, plus an
evidence pointer. Anything outside the set is a bug in the entry, not a
nuance: prose like "measured on our fleet" or "reproduced by @someone" reads
as a status while belonging to no tier, so a reader cannot tell how much
weight it carries.

| Label | What it claims | Who it applies to |
|---|---|---|
| **reproduced here** | we ran it, and a stranger can check the result without asking us for anything | us |
| **contributor-measured, conditions as reported** | someone else measured it and published their conditions; we have not independently reproduced it | a named contributor |
| **reported by others** | credited and linked, not independently reproduced and not measured by us either | upstream issues, bug reports, other labs |
| **measured here, raw not published** | we ran it, and the evidence is **not** checkable by a stranger | us |
| **under test** | a replication is running, and the entry says what would change it | anyone |

Labels may be combined when an entry genuinely has two halves ("reported by
others and reproduced here"), as long as each half carries its own evidence
pointer. They may not be blended into a new phrase.

### What "reproduced here" requires

**Reproduced here** is the strongest thing this registry says, so it has a
hard bar: **a stranger must be able to check it without asking us for
anything.** One of these three, named in the entry:

1. **A URL to the raw**, which they can open.
2. **In-repo raw**, under the conditions in
   [MAINTAINING.md](MAINTAINING.md#shipping-raw-data-in-the-repo).
3. **A runnable procedure against a publicly obtainable artifact**: a shipped
   chat template, a public source file, a config on the hub, or an endpoint
   on the reader's own lane. When the check section is a command a stranger
   can run to re-derive the finding for themselves, that is verification, and
   for structural findings it is a better one than our rows would be.

"We can produce the raw on request" does **not** qualify, and used to. A
promise is not evidence: it cannot be checked by the person reading the
entry, which is the only person the label exists for. An entry we measured
whose evidence meets none of the three is **measured here, raw not
published**. That is an honest label, not a demotion, and it converts to
reproduced here the day the raw lands or a runnable check is written.

### The gold standard

The strongest form of evidence in this repo is **in-repo raw plus an
independent verifier**: the data ships in the tree and a program written
separately from whatever produced the numbers re-derives every published
figure and prints pass or fail. A reader re-runs one command and needs to
trust nobody.

[The agreement floor](mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md)
is the worked example and the standard other calibration entries are held
to. Writing its verifier caught two defects in the draft before publication,
which is the argument for the standard in one sentence. Entries that other
entries cite as a threshold, floor or baseline are expected to reach it; see
[MAINTAINING.md](MAINTAINING.md#shipping-raw-data-in-the-repo) for when raw
ships in the tree.

### Accuracy deltas must carry the MDE

Any entry quoting an accuracy or score delta states the **minimum detectable
effect** for the design it was measured on, next to the number. Our own
measured floor is **about 1.3 points at n=600** on this stack
([agreement floor](mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md)),
so a 1-point difference at that n is not a result no matter how clean the
runs looked. Without the MDE beside it, a delta can be quoted by an external
reader as significant when the design could never have resolved it.

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

## External PR policy

This is the standing rule, not a decision taken once. It exists because the
first large external PR asked all four of these questions at the same time,
and a contributor deserves to know the answers before they do the work rather
than after.

**Status on a contributor's own measurements.** If you measured it yourself
and your raw lives on machines we cannot reach, the entry lands as
**contributor-measured, conditions as reported**, with your conditions and
counts in full. That is the correct label, and it is not a penalty:

- It is **not** "reproduced here". That label means a stranger can check the
  result, and it is scoped to measurements taken on our hardware. Nothing
  about your rigour changes that; the label describes who can verify, not how
  good the work is.
- It is **not** "under test" either, which several contributors have offered
  as the strict option. "Under test" means a replication is actually running.
  Applying it to a finished measurement understates it and describes work
  nobody is doing.

You do not need to hand over private raw, and we will not ask. Sanitized
extracts are welcome and upgrade nothing by themselves; a **runnable check**
does, because it moves the entry to a procedure a stranger can run (form 3
under [what "reproduced here" requires](#what-reproduced-here-requires)).
If we later reproduce it here, the entry gains the second half of a compound
status and you keep the **Found by** line.

**Numbering.** Take the next free numbers at the time you open the PR and do
not renumber while it is in review. The registry count lives in
`doctor/minefield_doctor.py` as `REGISTRY_TRAP_COUNT`, and a test fails the
build if it disagrees with the trap files, so collisions surface mechanically
rather than being someone's job to notice. If entries land underneath you
while your PR is open, **we** rebase the numbers at merge, not you.

**Volume.** Large PRs are welcome and do not need splitting on our account.
We will land them in category-sized commits and say which entries went where.
If we want a split, we will ask for a specific one rather than sending the
whole thing back. A PR is never rejected for size.

**Deduplication.** An entry that overlaps an existing one is not wasted. The
three outcomes are: it lands as its own entry, it lands as a qualifier on the
existing entry with your data and credit attached, or it becomes a row in the
existing entry's "Stacks and builds bitten". All three are contributions and
all three are credited. You are not expected to have read all 42 entries
before opening a PR; finding the overlap is a maintainer's job.

**Partial merges.** We will land the entries we can verify or accept and say
plainly, in the PR, which ones we are holding and what would unblock each.
Entries we are not ready to land go to [mining/](mining/) rather than being
closed, so the work stays findable and stays yours.

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
