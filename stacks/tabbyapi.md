# TabbyAPI and ExLlamaV2 / ExLlamaV3

**Measured here:** no (no first-party run)


**We have measured nothing on this stack.** No entry names TabbyAPI, ExLlama,
ExLlamaV2 or EXL2 anywhere. Absence means nobody has reported to us, not that
the stack is clean.

**One distinction on this page matters more than the zero.** Five entries name
**EXL3**: traps
[02](../traps/template/02-orphaned-think-close-tag.md),
[03](../traps/reasoning/03-enable-thinking-default-drift.md),
[04](../traps/template/04-history-reasoning-stripping.md),
[10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) and
[30](../traps/template/30-default-system-message-silently-replaced.md), but
they name it as a **quantization format** in a hybrid build, served from a
container, not as ExLlama-the-runtime behind TabbyAPI. We have data about an
EXL3 *tail* in a mixed-format checkpoint. We have none about this *server*.

Reading those five as TabbyAPI coverage would be the exact error trap
[10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md) is about:
the format label is not the serving path.

Nobody here has run TabbyAPI.

## Why the gap

Our EXL3 work arrived as one arm of a quantization comparison rather than as a
serving stack we operate, and the comparison was run through a container we
already had. TabbyAPI was never stood up.

## Which of our mechanism classes most likely apply, and why

Hypotheses, each naming the measured entry the class comes from. Two of these
are sharpened by things the mining round found and this registry did **not**
publish, for want of a source good enough, they are noted as such.

**The quant label is not the kernel path**: trap
[10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md), head of a
four-entry family. EXL2 and EXL3 are the strongest candidates in the registry
for this class because their headline number, **bits per weight, is an
average**. Two checkpoints labelled the same bpw from different publishers can
differ in per-layer allocation and in the calibration set used to choose it.
The label is not even claiming to name a kernel path; it is naming a budget.
Trap 10's fix, find a runtime tell rather than trusting the label, applies
directly.

**Speculative decoding has a sharp peak, and the drafter must match**: traps
[11](../traps/runtime/11-speculative-depth-peak-and-collapse.md) and
[62](../traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md).
Trap 62 is token garbling from a drafter configuration, measured here on a
different stack. A draft model whose tokenizer or vocabulary does not match the
target is the canonical way into that, and it is a documented requirement on
this stack rather than a subtle one.

**The template you selected is not the model's template**: traps
[19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md),
[24](../traps/template/24-official-template-breaks-cpp-jinja.md) and
[56](../traps/template/56-checkpoint-ships-no-chat-template.md), and
[U03](../upstream/U03-ollama-bundled-template-diverges.md) and
[U09](../upstream/U09-vllm-mistral-chat-template-ignored.md). Where a server
selects a prompt format **by name from a configuration file** rather than
reading the checkpoint's own template, choosing the wrong name is a
configuration typo with a quality-shaped symptom. U09 is the version of this
where the template you supplied was ignored entirely, with a warning nobody
saw.

**Long-uptime state corruption.** This one has **no entry behind it** and is
listed as an open question rather than a hypothesis with support. The mining
round surfaced a community report of a server producing degrading output after
long uptime until restarted; it rests on a single forum comment and was closed
as [too weak to publish](../mining/2026-07-28-r2-queue-classified-upstream-tier.md).
It is recorded here because a soak is expensive, nobody has run one, and if the
effect is real it is the kind that never gets caught by a short test. Treat it
as unverified folklore until somebody logs it.

## How you would test for these

1. **Run the [doctor](../doctor/) against the endpoint.** One stdlib file,
   any OpenAI-compatible server, and it has never met this one.
2. **For the bpw class**, the decisive comparison is two checkpoints at the
   **same nominal bpw from different publishers**, on one fixed probe set, with
   sampling held identical across both. Report the calibration details if the
   publisher states them. Equalising sampling and template is what makes this a
   measurement rather than trap
   [17](../traps/evaluation/17-per-arm-recommended-sampling-confound.md), which
   is the most common way an A/B result turns out never to have existed.
3. **For the template class**, serve one checkpoint twice under two different
   prompt-format names and compare outputs on identical prompts. The failure is
   quality-shaped, not an error, so read the assembled prompt if the server
   exposes it.
4. **For the drafter class**, pair a target with a draft model from a different
   family and record whether you get a clean refusal, a crash, or **output**.
   Output is the interesting answer; trap 62 is what that looks like.
5. **If you run a long-lived instance**, log a fixed canary prompt at
   temperature 0 hourly and diff the outputs. That is the only way the
   long-uptime question gets settled, and it costs nothing on a server you were
   running anyway.

## How to report a finding

Open an ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml).
Data format guidance is in
[CONTRIBUTING](../CONTRIBUTING.md#sending-measurement-data). Negatives are
welcome and are worth as much as positives on a stack at zero.
