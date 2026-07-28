# Trap 90: a kernel library advertises a fast path your card cannot run, and the six errors on the way there each look like a fixable config bug

**Found by [@drowzeys](https://github.com/drowzeys) (Keys). Shared by
[@drowzeys](https://github.com/drowzeys), from his public notes.**

**Fourth sibling to [trap 10](../quantization/10-quant-label-is-not-the-kernel-path.md),
trap 45 and [trap 46](46-stale-build-missing-arch-kernel.md).** Trap 10 is
"the checkpoint can only take one path", 45 is "your cmake line decided which
paths exist", 46 is "the path exists in the source you track but not in the
binary you are running". This one is **"the path exists in the source and in
your binary, but the precompiled kernels it dispatches to were never built for
your architecture - and no build of them exists for your CPU architecture
either."** Same consequence as all three, reached a fourth way, and the first
of the four that no rebuild can fix.

**Status: contributor-measured, conditions as reported** (published by Keys in
[notes-for-DSV4F-DSpark-Abliteration](https://github.com/drowzeys/notes-for-DSV4F-DSpark-Abliteration/blob/afd4137540ba5c4c2a1e96ecaf4200af74f8dfd8/TECHNICAL_REPORT.md),
section 3 row F9 and section 6, at commit `afd4137`). Debugged to a hard
conclusion by Keys on GB10; **not reproduced here and not measured here.**

**Symptom.** You try to move a working model onto an official engine release to
pick up a faster attention path, and you get a *sequence* of errors - six of them
in the reported case - each of which looks like the last config problem standing
between you and a working server. You fix each one. They are all real fixes. The
last error is `Unsupported architecture`, and it is the first one that tells you
the truth: **the fast path was never available on your card**, and every fix
before it was work spent walking toward a wall.

The reported ladder, in order, is worth reading as a shape rather than as
specifics:

| Step | What was changed | What came back |
|---:|---|---|
| 1 | stock SM120 path + FlashInfer 0.6.13 | `unexpected keyword argument 'swa_topk_lens'` (an 0.6.14 API) |
| 2 | switched to the MLA parent + `nvfp4_ds_mla` | assert: KV dtype must be bf16 or fp8 - the packed dtype is uint8 |
| 3 | allowed uint8 | `Expected 64 or 128 query heads, got 32` |
| 4 | padded heads to 64 | `swa_kv_cache.shape[1] == 1, got 64` (NHD vs HND layout) |
| 5 | set `kv_layout=NHD` | uint8 vs bf16 dtype mismatch |
| 6 | set KV dtype fp8 | **`Unsupported architecture`** |

**Mechanism.** The library ships **precompiled cubins** for the sparse-MLA path
that target **SM100 only**. The card in question is **SM12.1** (GB10). Nothing in
the Python API knows or says this. The API surface is architecture-agnostic, so
every argument check, dtype assert and layout assert fires *before* anything gets
far enough to look for a cubin - which means the shape and dtype errors are
genuine and answerable, and answering them just advances you to the next one. The
architecture check is last because it is deepest.

This is a versioning trap and not merely a hardware-support fact because of
the mismatch between what the *package version* implies and what the *shipped
binaries* contain. `0.6.13` installs, imports, and exposes the entry point. Its
Python signature differs from `0.6.14`'s (step 1), so version-pinning discussions
focus on the API delta and never reach the cubin question. And the fix that would
work - `flashinfer-cubin 0.6.14` for **aarch64** - did not exist as a build for
that platform at the time. So the platform gap is invisible from the package
index too.

The transferable lesson: **a library's version number tells you about its API. It
tells you nothing about which architectures its precompiled kernels cover.** Those
are two independent axes and only one of them is in the version string.

**Stacks and builds bitten.** As reported: official vLLM **0.25.0**, aarch64,
FlashInfer **0.6.13**, DeepSeek-V4 sparse MLA path, GB10 / SM12.1. The reported
conclusion is stated as a hard one: Python-level transplants alone cannot run that
sparse MLA path on GB10 with that combination. Reported on one stack.

**It produced a published outcome.** Yes, though a negative one - the project
(`dsv4f-v025-gt60`, targeting >60 tok/s single-stream) was put **ON HOLD** on
2026-07-12 as a direct result, and the resolution was to stop waiting for the
official path and serve on a prebuilt image that already carried the
architecture-appropriate kernels.

**The check.** Ask the library what it has compiled for your architecture,
**before** you start fixing shape and dtype errors:

```bash
python3 - <<'PY'
import sys
try:
    import flashinfer, torch
except ImportError as e:
    print(f"FAIL: cannot import ({e})"); sys.exit(3)   # exit 3, not 0 - "could not look" is not "nothing wrong"
cc = torch.cuda.get_device_capability()
print(f"device capability: sm_{cc[0]}{cc[1]}")
print(f"flashinfer: {getattr(flashinfer, '__version__', 'unknown')}")
# enumerate the shipped cubin/AOT artifacts and report which arches they cover
import glob, os, re
root = os.path.dirname(flashinfer.__file__)
arts = glob.glob(os.path.join(root, "**", "*.cubin"), recursive=True) + \
       glob.glob(os.path.join(root, "**", "*.so"), recursive=True)
if not arts:
    print("FAIL: zero artifacts found - cannot conclude anything"); sys.exit(3)
arches = sorted({m for a in arts for m in re.findall(r'sm[_]?(\d{2,3})', a)})
print(f"{len(arts)} artifacts, arches referenced: {arches or 'none in filenames'}")
mine = f"{cc[0]}{cc[1]}"
print("PASS" if mine in arches else f"FAIL: sm_{mine} not among shipped arches {arches}")
sys.exit(0 if mine in arches else 1)
PY
```

The `sys.exit(3)` branches are load-bearing. An import failure or an empty
artifact list means the check **could not look**, and a check that cannot look
must not exit `0` - that is the exact defect CONTRIBUTING documents in
`preflight_template.py`. Filename-based arch detection is also a heuristic and
will under-report for libraries that embed arch metadata rather than naming it;
where the artifacts are ELF, `cuobjdump --list-elf` on the `.so` is the
authoritative answer and should be preferred if available.

> **This check has NOT been run against a real FlashInfer install, and the
> entry says so rather than implying otherwise.** FlashInfer is not installed
> on any host available to us, and the hardware here is sm_120 and sm_121,
> not the SM100 the cubins in question target, so neither half of the
> comparison could be exercised. What *was* verified is only the failure path:
> the import guard fires and returns the exit-3 "cannot conclude" branch rather
> than a pass. **The artifact-globbing and the `sm_NNN` filename regex are
> written from reasoning about the package layout, not from inspecting one,
> and should be treated as a sketch until someone runs it.** Anyone with
> FlashInfer installed can settle it in under a minute, and that is the single
> most useful thing a reader of this entry could send back.

The cheaper structural check, which needs no hardware at all: **before** adopting a
fast path, confirm the library publishes a build for your `(architecture, CPU
architecture)` pair - both halves. `aarch64` was the half that did not exist here.

**The fix.** Two, and the second is the one that shipped:

1. Wait for a library build that covers your architecture on your CPU
   architecture, and pin it explicitly.
2. **Stop transplanting.** Serve on an image that already carries kernels built
   for your architecture. The reported resolution was to move to a prebuilt
   GB10-capable runtime rather than continue porting into the official release -
   and it worked, at essentially the same throughput the transplant was chasing.

Recognising the shape early is worth more than either: when a port produces a
*ladder* of shape/dtype/layout errors rather than one, stop and check
architecture support before fixing error number three.

**Found.** 2026-07-12, in a throughput port; put on hold the same day. Written up
2026-07-28.

**Attribution.** Keys ([@drowzeys](https://github.com/drowzeys)). Source:
[notes-for-DSV4F-DSpark-Abliteration](https://github.com/drowzeys/notes-for-DSV4F-DSpark-Abliteration),
`TECHNICAL_REPORT.md` section 3 (F9) and section 6, at commit
`afd4137540ba5c4c2a1e96ecaf4200af74f8dfd8`. MIT.
