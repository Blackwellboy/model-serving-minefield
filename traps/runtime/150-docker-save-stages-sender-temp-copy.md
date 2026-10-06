# Trap 150: `docker save` can stage a full image copy on the sender before streaming

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #160](https://github.com/Blackwellboy/model-serving-minefield/issues/160)); classic-exporter source path also inspected.

**Symptom.** A supposedly streaming `docker save IMAGE | ssh ... docker load` transfer can fill the sender's Docker data-root disk before bytes reach the receiver.

**Mechanism.** On the measured Docker 29.2.1 classic graph-driver exporter, save first materialized all layer/config content under the daemon temp directory and only then tarred it to the output stream. A small-image control staged approximately the entire image size. Containerd-image-store export follows a different path, so the behavior is store-dependent.

**Stacks and builds bitten.** Docker Engine 29.2.1 on DGX Spark, classic exporter behavior, data root under `/var/lib/docker`.

**The check.** Identify the image store, measure free space on the Docker data-root filesystem, and watch the daemon temp directory during a small multi-second `docker save` control.

**The fix.** Ensure sender-side temporary capacity, move `DOCKER_TMPDIR` to a suitable filesystem where appropriate, use a registry/containerd streaming path, or rebuild/pull on the destination.

**Found.** 2026-09, engine-image transfer planning.

**Attribution.** @scottleimroth.
