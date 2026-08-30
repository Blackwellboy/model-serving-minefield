# text-generation-webui (oobabooga)

**Measured here:** no (no first-party run)


**We have measured nothing on this stack and we hold no upstream reports about
it.** No entry names it. Absence means nobody has reported to us, not that the
stack is clean.

Nobody here has run text-generation-webui.

## The structural fact that shapes everything below

text-generation-webui is a **front end over several interchangeable loaders**:
llama.cpp, ExLlama, Transformers and others, selected per model. That is
unusual, and it makes one class of failure much more likely here than anywhere
else in this registry:

**A comparison between two models, or two quantizations, can silently be a
comparison between two loaders.**

That is not a hypothesis about this software. It is trap
[09](../traps/runtime/09-image-choice-changes-outcome.md), measured here: same
weights, same box, three container images, three different outcomes. It is the
reason this registry's methodology preamble says the unit under test is
**image plus weights plus hardware plus build**, not "the model". A UI that
makes swapping the execution path a dropdown makes that confound one click
away, and nothing in the interface has any reason to flag it.

The mining round looked for maintainer-confirmed silent-wrong reports against
this project and found none dense enough to publish. That is recorded honestly
in the classification note *(private evidence archived)*:
plenty of forum claims, no thread worth citing. **A search finding nothing is
not evidence of nothing.**

## Which of our mechanism classes most likely apply

**Loader choice as a hidden confound**: traps
[09](../traps/runtime/09-image-choice-changes-outcome.md),
[17](../traps/evaluation/17-per-arm-recommended-sampling-confound.md),
[34](../traps/evaluation/34-baseline-you-degraded-yourself.md) and
[54](../traps/evaluation/54-run-order-and-warm-cache-artifacts.md). If you have
ever concluded here that quantization X beats quantization Y, and the two
loaded through different loaders with different sampling defaults, trap 17 is
the entry that says why that result may never have existed. The
[A/B playbook](../playbooks/before-you-publish-an-ab.md) is the sequence for
doing it properly.

**Sampling defaults differ per loader**: traps
[21](../traps/versioning/21-no-generation-config-server-defaults-win.md) and
[17](../traps/evaluation/17-per-arm-recommended-sampling-confound.md), and
[U02](../upstream/U02-ollama-go-runner-drops-sampling-penalties.md), an
upstream report that one runtime in a two-runtime product implements no penalty
sampling at all while accepting the parameters. **A product with several
runtimes behind one settings panel is where that shape belongs**, and it is the
single most specific thing to check here.

**The template layer above the loader**: traps
[24](../traps/template/24-official-template-breaks-cpp-jinja.md),
[19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md) and
[56](../traps/template/56-checkpoint-ships-no-chat-template.md), and
[U03](../upstream/U03-ollama-bundled-template-diverges.md). A front end that
maintains its own instruction-template collection owns an artifact that can
drift from the checkpoint's own.

**Partial offload read as model weakness**: trap
[97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md),
where partial GPU offload cost 22 to 31 times decode and neither the server log
nor the props endpoint named the split. A GPU-layers slider with an
autodetected default is the same hazard with a nicer presentation.

## How you would test for these

1. **Run the [doctor](../doctor/)** against the OpenAI-compatible extension.
   It has never met this stack.
2. **The experiment worth doing here, that nobody else can do as easily:**
   load the **same** model through **two different loaders** and run one fixed
   probe set at matched sampling through both. Report per-loader outputs,
   decode throughput, and the sampling parameters each loader actually applied.
   That single result would be the most valuable thing this page could gain,
   and it is a question the UI is uniquely good at asking.
3. **Check whether your sampling settings reached the sampler.** Set a penalty
   or a temperature to an extreme value that must visibly change the output.
   If nothing changes, the parameter did not arrive, that is U02's shape and
   trap [77](../traps/reasoning/77-only-one-request-field-is-validated.md)'s
   probe.
4. **Record the loader in every result you publish anywhere.** This is the ask
   that costs nothing and prevents the most damage.

## How to report a finding

Open an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml).
Data format guidance is in
[CONTRIBUTING](../CONTRIBUTING.md#sending-measurement-data). If you report a
comparison, name the loader for each arm; a comparison without it cannot be
interpreted.
