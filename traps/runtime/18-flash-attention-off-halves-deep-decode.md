# Trap 18: flash attention off silently halves decode at depth

**Status: reported by others** (@Defilan, measured); adopted as a preflight check in the upstream guide. All our own vLLM numbers are FLASHINFER-attention numbers, so we never measured the off arm.

**Symptom.** Decode speed collapses as context grows, far faster than
memory bandwidth predicts, and the model gets blamed for being slow at
depth. Every shallow benchmark looked fine, because the penalty grows with
depth.

**Mechanism.** Flash attention left off (`-fa` off on llama.cpp). Measured
by @Defilan on a 128 GB Strix Halo (gfx1151) box: decode at 56K context ran
**9.33 tok/s without flash attention versus 20.73 with it, a 2.2x penalty**,
prefill 2.27x, and decode retention at depth improved from 40.0% to 75.8%
of the shallow baseline. The gain grows with depth, the opposite of the
usual intuition that attention flags matter most when short. The flag had
been left off out of platform caution (RDNA3.5 instability reports) that
did not materialize. Writeup:
[a flag I never questioned cost 2x](https://llmkube.com/blog/a-flag-i-never-questioned-cost-2x);
carried as a setup-verification row in
[TheTom's guide](https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md).

Two adjacent single-flag hazards from the same guide, same credit chain:
`-fit off` is required on the relevant llama.cpp forks because the memory
auto-fitter hangs on load, and `--jinja` is load-bearing for tool-call
parsing (trap 19).

**Stacks and builds bitten.** llama.cpp on gfx1151/Strix Halo (measured);
the class applies to any runtime where an attention implementation flag
defaults off or gets turned off defensively.

**The check.** Confirm the attention implementation in your server args and
logs, then benchmark decode at your REAL working depth (40K+), not at 2K.
A depth-dependent slowdown with a healthy shallow number is this trap until
proven otherwise.

**The fix.** Turn it on, re-verify stability on your platform rather than
inheriting another platform's caution, and state the attention backend next
to every published depth number.

**Found.** 2026-07, published in the writeup above.

**Attribution.** @Defilan (measurement and writeup); TheTom (guide
integration).
