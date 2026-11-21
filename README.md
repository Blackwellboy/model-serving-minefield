# Model Serving Minefield

**Your local model isn't broken. Something between your request and its
answer is.** This is a registry of the serving and measurement bugs that make
a healthy model look dumb, or make a bad number look convincing: chat
templates, tool parsers, reasoning fields, quantization kernel paths,
container toolchains, memory allocation, eval harnesses and versioning. Every
entry leads with the symptom you would actually see, then the mechanism, the
stacks and builds it hit, **one check that proves it**, and the fix.

[![integrity](https://github.com/Blackwellboy/model-serving-minefield/actions/workflows/integrity.yml/badge.svg)](https://github.com/Blackwellboy/model-serving-minefield/actions/workflows/integrity.yml)
[![surfaces](https://github.com/Blackwellboy/model-serving-minefield/actions/workflows/surfaces.yml/badge.svg)](https://github.com/Blackwellboy/model-serving-minefield/actions/workflows/surfaces.yml)

## Try it in ten seconds

```bash
pipx install model-serving-minefield
minefield "streaming shows blank replies" --stack vllm
```

Describe what you see in plain words. You get the few traps that match, how
strong each match is, the one check to run next, and a link to the entry.
Run `minefield` on its own for a numbered menu; each option says what it
touches (nothing, files you name, or a set number of requests) before it runs.
(`msmf` is a short alias package that installs the same thing.)

```bash
# offline: read your launch scripts, compose files, model folder, chat template, logs and eval results
minefield scan docker-compose.yml start.sh ./models/my-model ./logs/

# live: a bounded, read-only preflight against any OpenAI-compatible endpoint
minefield quick --base-url http://HOST:PORT/v1 --json doctor.json

# everything at once: symptom + files + endpoint
minefield diagnose "tp=2 dies after twenty minutes" --files start.sh ./logs/ --base-url http://HOST:8000/v1
```

Between `scan`, the log checks and the live doctor,
131 of the 168 traps have at least one automatic check
(`minefield coverage` prints the breakdown). A match is a lead to check, never
a diagnosis, and **no match is not a clean bill of health**.

## Find your symptom

All 168 entries are in **[TRAPS.md](TRAPS.md)**, one row each: what you are
seeing, what it may be, the entry, and its evidence status. Shorter routes:

- **Know your stack?** [stacks/](stacks/) has a page per serving stack
  (vLLM, llama.cpp, Ollama, SGLang, mlx_lm, TabbyAPI and ExLlamaV3, and
  more) with the entries most likely to bite and the checks to run first.
- **Know your model?** [models/README.md](models/README.md) maps model
  families to what has bitten people on them.
- **Holding a job, not a symptom?** [playbooks/](playbooks/) are ordered
  checklists: publishing an A/B, multi-turn thinking, porting a harness, long
  context, reading a soak, and more.
- **Want the twelve that cost people the most evenings?** Read
  [CORE.md](CORE.md).

Ten that bite almost everyone:

| You are seeing | Entry |
|---|---|
| A thinking model's multi-turn score drops for no reason | [04](traps/template/04-history-reasoning-stripping.md) |
| "Reasoning fired 0%" while the model visibly reasons | [01](traps/reasoning/01-reasoning-field-two-names.md) |
| Two people say "same model" and their numbers never agree | [03](traps/reasoning/03-enable-thinking-default-drift.md) |
| HTTP 200 with empty content, scored as the model failing | [12](traps/evaluation/12-empty-content-at-token-ceiling.md) |
| An A/B gain that disappears when both arms use the same sampling | [17](traps/evaluation/17-per-arm-recommended-sampling-confound.md) |
| A re-run of the same weights scores differently | [35](traps/evaluation/35-identical-weights-do-not-score-identically.md) |
| The quant name says one thing and the speed says another | [10](traps/quantization/10-quant-label-is-not-the-kernel-path.md) |
| "The model can't call tools" | [19](traps/tools/19-missing-jinja-breaks-tool-parsing.md) |
| You changed a flag, restarted, and nothing changed | [53](traps/runtime/53-config-edit-never-took-effect.md) |
| A long prompt is accepted and answered from nowhere near its start | [61](traps/evaluation/61-advertised-window-fails-silently.md) |

## How much to trust an entry

<!-- status-vocabulary: full-set -->
Each entry carries exactly one status from a
[closed vocabulary](CONTRIBUTING.md#status-vocabulary): **reproduced here**
(we ran it, and you can check the result without asking us for anything),
**contributor-measured,
conditions as reported** (someone else measured it and published their
conditions), **reported by others** (credited and
linked, not independently reproduced), **measured here, raw not published**
(we ran it, and you cannot check it), and **under test**. Reports from other
people's trackers that nobody here has run live separately in
[upstream/](upstream/) and never count toward the total.

## Use it from an agent

- **MCP:** `minefield-mcp` over stdio exposes search, report interpretation,
  reproduction plans and explicit-file inspection. It cannot restart or modify
  a server. See [docs/MCP_SETUP.md](docs/MCP_SETUP.md).
- **Agent with GitHub access:** point it at
  [AGENT_START_HERE.md](AGENT_START_HERE.md) (or [llms.txt](llms.txt)) plus
  your redacted logs.
- **Agent without GitHub access:** upload
  [dist/MINEFIELD_AGENT_BUNDLE.md](dist/MINEFIELD_AGENT_BUNDLE.md).
- **Hermes:** the [hermes-minefield](https://github.com/Blackwellboy/hermes-minefield)
  plugin adds `/minefield`. See [docs/HERMES_SETUP.md](docs/HERMES_SETUP.md).
- **CI:** run `minefield scan` on your own pull requests with the
  [example GitHub Action](docs/GITHUB_ACTION_SCAN.md).
- **Machine-readable:** [dist/MINEFIELD_REGISTRY.json](dist/MINEFIELD_REGISTRY.json)
  is the whole registry with a schema and checksums.

## Contribute

Hit something real that isn't here? Open an
["I hit a trap" issue](../../issues/new?template=report-a-trap.yml). Four
plain questions, no writeup needed; a maintainer verifies what can be
verified, writes the entry and credits you by name. Scrub hostnames, IPs,
paths and credentials first, but keep the model, version, quantization and
serve flags exactly as they are. Writing the entry yourself is welcome too:
see [CONTRIBUTING.md](CONTRIBUTING.md). Contributors are credited in every
entry and in [HALL_OF_FAME.md](HALL_OF_FAME.md).

## More

- [docs/GUIDE.md](docs/GUIDE.md): the full guide (the doctor, every way in,
  the pre-serve checklist, categories, methodology, scope, recent additions)
- [CHANGELOG.md](CHANGELOG.md), [MAINTAINING.md](MAINTAINING.md),
  [SECURITY.md](SECURITY.md), [CITATION.cff](CITATION.cff)
- Raw evidence for many entries:
  [model-serving-minefield-evidence](https://github.com/Blackwellboy/model-serving-minefield-evidence)
  and the [Laguna S 2.1 testing lab](https://github.com/Blackwellboy/laguna-s21-lab)
- Adoptions and outcomes: [community/COMMUNITY_IMPACT.md](community/COMMUNITY_IMPACT.md)

MIT licensed ([LICENSE](LICENSE)). Entries describe measurements and checks;
no model weights are included. Support:
[GitHub Sponsors](https://github.com/sponsors/Blackwellboy) ·
[Buy Me a Coffee](https://buymeacoffee.com/blackwellboy)
