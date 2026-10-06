# Trap 145: `docker run` can hide an image pull inside your launch timeout

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #132](https://github.com/Blackwellboy/model-serving-minefield/issues/132)).

**Symptom.** An orchestrator times out inside `docker run -d` and reports a generic launch failure. No container is healthy, and repeated retries look like a slow or broken model start.

**Mechanism.** If the requested image is absent locally, Docker may pull it before creating the container. That network transfer happens inside the same `docker run` call whose timeout was often sized only for local container startup. A pull can even finish after the orchestrator gives up, leaving an unmanaged container starting in the background.

**Stacks and builds bitten.** Direct Docker orchestration across DGX Spark nodes with non-identical local image sets; observed across vLLM and SGLang image tags.

**The check.** Immediately before launch, require `docker image inspect <ref>` to succeed in the same control path that gates `docker run`. If absent, report the missing image explicitly instead of timing the launch call.

**The fix.** Separate image acquisition from container startup. Pull explicitly, verify the local image identity, then start under a timeout intended for startup only.

**Found.** 2026-09, multi-host benchmark orchestration.

**Attribution.** @scottleimroth.
