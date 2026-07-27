# Model Serving Minefield

A community registry of chat-template and serving-path traps that produce
**confidently wrong measurements** about local LLMs.

Every entry here was found the expensive way, usually after a number had
already been published or shared. The common shape: the request looks correct,
the response looks correct, and the number is still wrong, because something
happened between the two that nobody inspected. Request-shaped checks cannot
catch any of these.

Each entry leads with the symptom you would actually observe, because people
arrive here holding a weird number and no idea what caused it. Then the
mechanism, the stacks and builds it bit, the check that catches it, and the
fix.

## Find your symptom

| You are seeing | It may be | Entry |
|---|---|---|
| Firing rate reads 0% while the model is visibly reasoning | The reasoning field has two names and you read the wrong one | [Trap 01](traps/01-reasoning-field-two-names.md) |
| Every response starts with a stray `</think>` | Reasoning parser strips the open tag but not the close | [Trap 02](traps/02-orphaned-think-close-tag.md) |
| Two testers run the "same model" and get different behavior | `enable_thinking` default drifts between revisions and uploads | [Trap 03](traps/03-enable-thinking-default-drift.md) |
| Thinking fires single-turn but collapses toward zero as the conversation deepens | Prior-turn reasoning stripped from replayed history | [Trap 04](traps/04-history-reasoning-stripping.md) |
| Scored verdicts do not survive a hand-read of the same transcripts | A scorer normalization detail (curly quotes, unicode punctuation) flips verdicts | [Trap 05](traps/05-scorer-normalization-verdict-flip.md) |
| Thinking dies under any real system prompt and no prompt tuning brings it back | The template's trained identity sentence was evicted from line one | [Trap 06](traps/06-identity-sentence-eviction.md) |
| `reasoning_effort` levels change nothing | The API accepts the parameter and the template never reads it | [Trap 07](traps/07-reasoning-effort-silently-ignored.md) |

If you run one check from this registry, make it the one for
[Trap 04](traps/04-history-reasoning-stripping.md). It is the only one whose
symptom looks like a genuine model property rather than a bug, and it cost
four independent testers a combined multi-week detour.

## Methodology preamble

Three rules apply to every entry and to every number you publish about a
served model.

**1. Inspect the assembled prompt, not the request.** All of these traps live
between a correct-looking request and a correct-looking response. The only
place they are visible is the prompt the server actually renders. If your
harness has never dumped the assembled prompt at turn N, you have not checked
for any of them.

**2. State build AND revision next to every number.** Thinking policy differs
by build, not just revision. FP8 and NVFP4 uploads of the same model at the
same revision have been measured applying different thinking policies on the
wire: the FP8 build skipped trivial follow-up turns under every prompt tried,
including a byte-exact replay of a known-good client request shape, while the
NVFP4 build reasoned essentially every turn (measured by @quantumleap68 with
a logging proxy between client and server). A published firing rate that
names a revision without its build is underspecified. Treat cross-build
comparisons as cross-model until shown otherwise.

**3. Diff the kwarg surface in both directions.** Enumerate every kwarg the
chat template reads and diff it against the model card, and diff the
parameters the API accepts against what the template reads. A kwarg the
template reads but the card does not document is an untested variable
(Trap 04's control was exactly this). A parameter the API accepts but the
template never reads is a dead knob (Trap 07).

## Scope

These entries were found while characterizing a handful of models on DGX
Spark class hardware across vLLM, llama.cpp, and an EXL3-tail container.
Traps 01, 04, and 05 are template, serving-path, or scoring classes and
should be assumed present elsewhere until checked. Model revisions and builds
are named in each entry so you can tell "this was true of that checkpoint"
from "this is true of the family".

Much of the raw evidence lives in the
[Laguna S 2.1 testing lab](https://github.com/Blackwellboy/laguna-s21-lab),
where this registry started as a single file. Entries link their raw data
directly.

## Checks you can run

[`checks/preflight_template.py`](checks/preflight_template.py) is a
stdlib-only template forensics script. It renders the actual prompt for a
marked three-turn conversation and reports whether prior-turn reasoning is
preserved or stripped (Trap 04), whether the template injects or rewrites
messages, and which kwargs the template actually reads versus what the model
card documents. It refuses to certify a lane whose assembled history drops
the reasoning marker. See [`checks/README.md`](checks/README.md).

## Contributing

This registry only works if it outgrows its founding stack. If a serving path
burned you and the number survived review before anyone caught it, that is an
entry.

- **Report a trap** you have hit but not fully characterized:
  [open an issue](../../issues/new?template=report-a-trap.yml). A symptom and
  a stack description is enough to start.
- **Add an entry** yourself: one file under `traps/`, format and evidence bar
  in [CONTRIBUTING.md](CONTRIBUTING.md). The bar is measured, not inferred:
  state the stack and build, show the check that catches it.

## Credits

- **@quantumleap68**: wire-level measurements (logging-proxy methodology)
  behind Traps 06 and 07, the independent confirmation of Trap 04, and the
  FP8 versus NVFP4 build-policy split in the methodology preamble.
- **TheTom** and the offlabel project: the behavioral guide and shared probe
  tooling this work cross-validates against, and the upstream threads where
  several of these traps were reconciled.
- **@Defilan**: third-stack replications that helped separate model behavior
  from stack behavior.

## License

MIT (see [LICENSE](LICENSE)). Entries describe measurements and checks; no
model weights are included.

## Support

- GitHub Sponsors: <https://github.com/sponsors/Blackwellboy>
- Buy Me a Coffee: <https://buymeacoffee.com/blackwellboy>
