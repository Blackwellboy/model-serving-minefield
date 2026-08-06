# Trap 39: `device_map="auto"` grabs a device you excluded and returns garbage

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-16 entries).**

**Status: reported by others.** Observed twice by the finder; the invalid
runs were discarded rather than scored, so there is no scored count for the
failed condition. The mechanism as stated is the finder's attribution.

**Symptom.** A probe or eval that worked yesterday returns complete
nonsense. Not a degraded answer, not a formatting problem: unusable output
across every item. The weights are the same, the prompt is the same, and the
run exits cleanly. The natural conclusion is that the checkpoint is damaged,
which is exactly what the finder was in the middle of investigating when this
bit him, and it very nearly contaminated a corruption diagnosis with a
measurement artifact.

**Mechanism.** `device_map="auto"` places layers across every visible
accelerator and spills the remainder to CPU or to the `meta` device. On a box
where one GPU is reserved (a display GPU, another job's card, an
administratively off-limits device), "every visible accelerator" includes it,
because visibility is a driver-level fact and your intention is not. Two
things then go wrong at once: the placement grabs a device it should not
have, and the spill puts part of the model somewhere that does not produce
correct activations. The result is garbage output rather than a loud failure,
because nothing in the placement path treats this as an error.

The finder hit it on a 3-GPU box where GPU 2 was designated no-compute. His
first run of a tool-call syntax probe produced gibberish; re-running the same
probe pinned to GPUs 0 and 1 produced clean, interpretable results (2/12 and
1/12 on the condition under test). He recorded the first run as invalid data
rather than as a finding, and wrote `CUDA_VISIBLE_DEVICES=0,1` into the
procedure as mandatory.

**Stacks and builds bitten.** HF transformers with accelerate on a 3-GPU
workstation (2x RTX PRO 6000 usable, one reserved), Qwen3.6-35B-A3B bf16 and
its full-model exports. The class applies to any `device_map="auto"` or
`"balanced"` load on a machine where not every visible GPU is yours, which
includes most shared and most desktop boxes.

**The check.** Two lines, before any generation:

```python
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"     # set BEFORE importing torch

# after load, refuse to run on a model that got spilled
bad = {n: p.device.type for n, p in model.named_parameters()
       if p.device.type in ("meta", "cpu")}
assert not bad, f"{len(bad)} parameters offloaded: {list(bad)[:3]}"
print(sorted({str(p.device) for p in model.parameters()}))
```

The device set printed at load time should contain exactly the devices you
intended and nothing else. If `meta` or `cpu` appears in a run you believe is
fully resident, stop: the output you are about to score is not the model's.

**The fix.** Pin devices explicitly rather than relying on exclusion by
convention. Set `CUDA_VISIBLE_DEVICES` before importing torch, and prefer an
explicit `device_map` (or a single-device `.to("cuda:0")`) over `"auto"` for
anything whose output you intend to score. Assert no parameter landed on
`meta` or `cpu`. If a model genuinely does not fit, that should be a raised
error in your harness, not a silent spill that returns text.

**Found.** 2026-07-16, during a tool-call corruption investigation, where an
invalid gibberish run would have been read as further evidence of checkpoint
damage.

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who caught the artifact, discarded the run, re-measured under pinned devices,
and recorded the trap as a standing procedure change rather than a one-off.
