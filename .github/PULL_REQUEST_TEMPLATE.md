# Adding a trap entry

Thanks. Checklist for a new entry (see CONTRIBUTING.md for the format):

- [ ] One file under the right category, `traps/<category>/NN-short-slug.md`. For the number, run `python3 integrity/registry_integrity.py` and read the `next free trap number` line. **You do not have to get this right:** numbers are provisional and we rebase them at merge, so do not renumber while your PR is in review even if entries land underneath you
- [ ] **Found by** line directly under the title, naming the finder by the handle they publish under
- [ ] Status line up top, using **exactly one label from the closed set** below, plus its evidence pointer
- [ ] Sections in order: Symptom, Mechanism, Stacks and builds bitten, The check, The fix, Found, Attribution
- [ ] Symptom leads: it describes what a reader would observe, not the mechanism
- [ ] Measured, not inferred: counts and conditions are stated (0/42 style)
- [ ] Stack AND build named: server version, model, revision hash, quantization build
- [ ] The check is runnable as written (snippet, command, or a script added under `checks/`)
- [ ] Row added to the symptom table in `README.md`
- [ ] Model row added or extended in `models/README.md` if a model family is named
- [ ] Attribution names the finder by the handle they publish under, with a link to raw data if public
- [ ] No secrets, private hostnames, internal paths, or personal data anywhere in the diff

## The status vocabulary

<!-- status-vocabulary: full-set -->

Five labels, closed set. The canonical definitions are in
[CONTRIBUTING.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/CONTRIBUTING.md#status-vocabulary) and this list
must agree with them; `integrity/reference_integrity.py` asserts that it does.

| Label | Use it when |
|---|---|
| **reproduced here** | the registry ran it on our hardware, and a stranger can check the result without asking us for anything |
| **contributor-measured, conditions as reported** | you measured it yourself and published your conditions, and we have not independently reproduced it |
| **reported by others** | credited and linked to an upstream issue, report or lab, not measured by you or by us |
| **measured here, raw not published** | the registry ran it, and the evidence is not checkable by a stranger |
| **under test** | a replication is running, and the entry says what would change the label |

**If you measured it yourself, the label is `contributor-measured, conditions
as reported`, not `reproduced here`.** The "here" is the registry, not the
quality of your work. This is not a judgement on how carefully you worked, and
CONTRIBUTING used to say otherwise, which
[cost a contributor](https://github.com/Blackwellboy/model-serving-minefield/blob/main/CONTRIBUTING.md#what-reproduced-here-requires)
and was our documentation bug rather than their error.

Labels may be combined when an entry genuinely has two halves, as long as each
half carries its own evidence pointer. They may not be blended into a new
phrase.

- [ ] Status label is one of the five above, copied exactly
- [ ] **Evidence pointer present.** `reproduced here` requires one of: a URL to the raw a reader can open, in-repo raw under the MAINTAINING rules, or a runnable procedure against a publicly obtainable artifact. "We can produce the raw on request" does not qualify: a promise cannot be checked by the person reading the entry. If none of the three is available, the honest label is `measured here, raw not published`
- [ ] Any status quoted in `README.md`, `CORE.md`, a `models/` page or a `stacks/` page matches the entry's own Status line

What this PR adds:

<!-- one or two sentences -->
