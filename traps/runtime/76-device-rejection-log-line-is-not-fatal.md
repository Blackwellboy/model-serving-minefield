# Trap 76: the most alarming line in your startup log is the one that did not matter

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on Ollama 0.32.5 with `qwen3:8b` on an
NVIDIA GB10 (aarch64, CUDA 13). Anyone can reproduce it: install the current
Ollama on a card whose compute capability is newer than the first bundled
runner, start the server, and read the log. The mechanism is visible in the log
lines themselves, which the entry quotes.

**Symptom.** You bring up a new card, the server logs that it is **skipping**
your only GPU because its compute capability is not in the compiled
architectures, and it names the card. You stop, because that is a fatal-looking
line and the obvious reading is that you are about to run on CPU.

Inference then runs entirely on the GPU.

**Mechanism.** The runtime ships **more than one CUDA runner** and tries them in
order. The rejection of the first is logged at `INFO`, naming your device,
*before* the second one accepts it:

```
INFO msg="skipping CUDA device - compute capability not in compiled architectures" device="NVIDIA GB10" cc=1210 archs="[... 1000 1200]" libDirs="[.../lib/ollama .../lib/ollama/cuda_v12]"
INFO msg="inference compute" library=CUDA compute=12.1 name=CUDA0 libdirs=ollama,cuda_v13 driver=13.0
```

(Transcription note, because it matters if you go looking: the real log line
separates `device` from the explanation with an em dash. Both quotes above are
transcribed with an ASCII hyphen to match this repository's house style, so
copy the phrase rather than the punctuation if you are searching your own
logs.)

The `cuda_v12` runner is built for sm_120 and not sm_121; `cuda_v13` carries
`...1200,1210` and takes the device. On this bring-up the model then offloaded
**37 of 37 layers** with 11,139 MiB resident, which is what a fully accelerated
load looks like.

The line is not wrong and it is not a warning that should be suppressed. It is
accurate about the runner it names. It is misleading only because it is
**emitted before the outcome is decided** and reads as a verdict.

**Stacks and builds bitten.** Ollama 0.32.5 on GB10 (sm_121). The class covers
any runtime that bundles several compiled variants and logs per-variant
rejection: the same shape shows up whenever a card is newer than one of the
shipped kernel sets.

**The check.** Do not read the rejection. Read what came after it, and read what
the model actually did:

1. Find the line that reports the **selected** compute library, and check which
   `libdirs` it names. If it names a later runner than the one that was skipped,
   the skip was a fallback step and not a failure.
2. Confirm layer offload from the load line. Full offload plus resident VRAM is
   the outcome; a rejection line is a step.

**And do not let a health check grep for this string.** That is the expensive
version of this trap: a monitor that alerts on `skipping CUDA device` will fire
on every healthy start of a machine whose card is newer than the first bundled
runner, and the team will learn to ignore it. If you want an alert, alert on the
absence of the selected-compute line, or on the offload count being lower than
the model's layer count. Those are conditions that mean something.

**The fix.** Nothing to fix at the server. The fix is to your reading and to
your monitoring, which is why this is an entry rather than a bug report.

**Found.** 2026-07-28, during the first Ollama bring-up in this registry's
coverage. It cost a real debugging pause before the next line was read.

**Attribution.** Blackwellboy. Related:
[trap 08](08-image-toolchain-newer-than-driver.md) for the case where a
toolchain-versus-driver mismatch genuinely is fatal, which is the reason a
reader is primed to treat this line as fatal in the first place.
