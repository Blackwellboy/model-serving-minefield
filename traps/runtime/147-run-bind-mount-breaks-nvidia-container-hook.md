# Trap 147: a read-only bind mount at `/run` can break every `--gpus all` container before startup

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #150](https://github.com/Blackwellboy/model-serving-minefield/issues/150)).

**Symptom.** Docker fails before the container process starts with an OCI hook error mentioning `/run/nvidia-ctk-hook`, `ldcache`, or a read-only filesystem. The same image works without the mount.

**Mechanism.** NVIDIA Container Toolkit's createContainer hook needs scratch space under the container's `/run`. A read-only bind mounted over `/run` shadows the normal writable tmpfs, so the hook cannot create its scratch directory and GPU setup fails before the GPU or image entrypoint is reached.

**Stacks and builds bitten.** Docker + NVIDIA Container Toolkit 1.19.1 on DGX Spark GB10; reproduced with both a stock CUDA image and a project image. The measured failing case is a read-only `/run` bind.

**The check.** Reduce to `docker run --rm --gpus all -v <hostdir>:/run:ro <image> nvidia-smi`, then move the same mount to another path as the control.

**The fix.** Do not shadow `/run` read-only in GPU containers. Mount application data/config elsewhere, or preserve a writable `/run` for runtime hooks.

**Found.** 2026-09, container startup debugging.

**Attribution.** @scottleimroth.
