# Adding a trap entry

Thanks. Checklist for a new entry (see CONTRIBUTING.md for the format):

- [ ] One file under the right category, `traps/<category>/NN-short-slug.md`, next free global number
- [ ] Status line up top: reproduced here / reported by others / under test
- [ ] Sections in order: Symptom, Mechanism, Stacks and builds bitten, The check, The fix, Found, Attribution
- [ ] Symptom leads: it describes what a reader would observe, not the mechanism
- [ ] Measured, not inferred: counts and conditions are stated (0/42 style)
- [ ] Stack AND build named: server version, model, revision hash, quantization build
- [ ] The check is runnable as written (snippet, command, or a script added under `checks/`)
- [ ] Row added to the symptom table in `README.md`
- [ ] Attribution names the finder by the handle they publish under, with a link to raw data if public
- [ ] No secrets, private hostnames, internal paths, or personal data anywhere in the diff

What this PR adds:

<!-- one or two sentences -->
