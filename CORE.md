# The Core 12

If you only read twelve entries, read these.

They are not the twelve we are proudest of and they are not the twelve with
the best data. They are the twelve chosen on **evidence of what has cost
people evenings**: entries whose symptom looks like a property of the model,
whose check is cheap, and which have already bitten more than one person or
more than one stack. Everything else in the registry is Extended, which means
useful and specific rather than lesser: an Extended entry is exactly what you
want the moment you are in it.

The [playbooks](playbooks/) sequence these into the four jobs people arrive
with. This page is the reading list.

| Entry | Status | Why it is Core |
|---|---|---|
| [04, prior-turn reasoning stripped from history](traps/template/04-history-reasoning-stripping.md) | reproduced here | The registry's own most dangerous entry. Its symptom is a plausible, publishable number rather than a broken parse, and it cost four independent testers a combined multi-week detour |
| [01, the reasoning field has two names](traps/reasoning/01-reasoning-field-two-names.md) | reproduced here | Produces a confident, consistent 0% firing rate. It bit three separate tools, reproduced on three stacks, and one server carries three names split by route |
| [03, `enable_thinking` default drift](traps/reasoning/03-enable-thinking-default-drift.md) | reproduced here | Two testers say "same model" and then spend a week reconciling numbers that were never comparable |
| [12, empty content at a token ceiling](traps/evaluation/12-empty-content-at-token-ceiling.md) | reproduced here | Scores as a capability collapse. There is no single ceiling that makes it go away, which is why copying a budget from a sibling model does not work |
| [17, per-arm recommended sampling](traps/evaluation/17-per-arm-recommended-sampling-confound.md) | reported by others, confound reproduced here | The most common way a clean A/B effect turns out never to have existed |
| [35, identical weights do not score identically](traps/evaluation/35-identical-weights-do-not-score-identically.md) | reproduced here | Without your own agreement floor, every small delta you publish is unfounded. This entry is what makes a minimum detectable effect available to you |
| [16, finish_reason is not a failure signal](traps/evaluation/16-finish-reason-is-not-a-failure-signal.md) | reported by others and reproduced here | Moves aggregates by whole points, and it is the bucketing rule that entry 12 depends on |
| [10, the quant label is not the kernel path](traps/quantization/10-quant-label-is-not-the-kernel-path.md) | reproduced here | Head of a four-entry family. The label tells you what the checkpoint is called; only a runtime tell says which path the engine took |
| [19, one missing server flag turns tool calls into prose](traps/tools/19-missing-jinja-breaks-tool-parsing.md) | reported by others | "The model cannot tool-call" attributed to the model when it is one flag on the serve line |
| [53, the config edit never took effect](traps/runtime/53-config-edit-never-took-effect.md) | contributor-measured, conditions as reported | The restart reported success and lied, so every reasonable next debugging step is a dead end |
| [61, an advertised window that fails silently](traps/evaluation/61-advertised-window-fails-silently.md) | reproduced here (arithmetic) and measured here, raw not published (curve) | Three ceilings, no error at any of them. The prompt is accepted, counted exactly, and answered from nowhere near the start |
| [77, one request field is validated and every other one is accepted](traps/reasoning/77-only-one-request-field-is-validated.md) | reproduced here | The highest operator impact of this registry's Ollama set: a whole thinking-off arm measured on a thinking lane, every request returning 200 |

## Entries that were finalists and are Extended

Each of these was a serious candidate and each is one click away from the
playbook that needs it. They are not here because twelve is twelve.

- [34, the baseline you degraded yourself](traps/evaluation/34-baseline-you-degraded-yourself.md)
  and [54, run order and cache artifacts](traps/evaluation/54-run-order-and-warm-cache-artifacts.md),
  both in [the A/B playbook](playbooks/before-you-publish-an-ab.md).
- [09, same weights, three images, three outcomes](traps/runtime/09-image-choice-changes-outcome.md),
  which is the reason this registry's methodology preamble says the unit under
  test is image plus weights plus hardware plus build.
- [20, the reasoning write field is runtime-specific](traps/reasoning/20-reasoning-write-field-name-diverges.md)
  and [63, one correct round-trip shape out of four](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md),
  both in [the multi-turn playbook](playbooks/thinking-died-multi-turn.md).
- [55, supported context is not trained context](traps/evaluation/55-supported-context-is-not-trained-context.md),
  in [the long-context playbook](playbooks/long-context-looks-broken.md).
- [78, `tool_choice` is accepted and ignored](traps/tools/78-tool-choice-accepted-and-ignored.md),
  in [the porting playbook](playbooks/porting-a-harness.md).

## How Core interacts with the doctor

The [doctor](doctor/) orders its output Core first, within each verdict
bucket, so the checks most likely to matter are the first lines you read. It
implements checks for 9 of the twelve above (01, 03, 04, 10, 12, 16, 17, 19,
77); 35, 53 and 61 have no check in it and are yours to run. That is not a
gap in the tier, it is the tier being chosen on cost rather than on what a
request-shaped tool can reach.

**77 was the fourth uncovered one until 2026-07-28.** Its own entry names the
probe as the fix, in its own words: send one deliberately misspelled parameter
and see whether you get a 400. That is a request-shaped question with a real
paired control (the identical request without the invented field must return
200), so it went in. The check runs first, because on a lane that accepts
anything, every parameter every other check sends is a hypothesis rather than
a setting. What it can say is narrow and the tool says so: a CLEAN rules out
"a misspelled or unimplemented parameter is silently accepted", and never that
a particular toggle took effect. That question stays behavioural, with 03
and 29.
