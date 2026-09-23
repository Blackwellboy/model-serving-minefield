# U38: systemd daemon-reload can revoke GPU device access from a live Docker container

**Reported by @zlylong, building on @johnymoo's earlier hypothesis.**

**Status: upstream-reported.** Nobody here has reproduced this mechanism on Blackwellboy infrastructure.

**Maintainer engagement: maintainer responded.**

**Issue state: open.**

**Primary source.** https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark/issues/216#issuecomment-5790686366 , read on 2026-09-24.

**Earlier mechanism report.** https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark/issues/216#issuecomment-5552475460

**Vendor corroboration.** NVIDIA Container Toolkit documents the same class of GPU-access loss on affected systemd-cgroup configurations after `systemctl daemon-reload`: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html#containers-losing-access-to-gpus-with-error-failed-to-initialize-nvml-unknown-error

## Symptom

A GPU container can serve normally for days and then fail at an apparently unrelated CUDA or Triton operation with `operation not permitted`, `cudaErrorNotPermitted`, NVML loss, or `No CUDA GPUs are available`.

In the confirmed DGX Spark report, both TP ranks hit a Triton CUDA `operation not permitted` in the same second on a text-only request. A worker container remained alive afterward, but opening `/dev/nvidiactl`, `/dev/nvidia0` and `/dev/nvidia-uvm` failed, and a tiny Torch CUDA allocation reported no available GPU.

The systemd scope had `DevicePolicy=strict`. Explicitly declared InfiniBand devices appeared in `DeviceAllow`; NVIDIA device majors did not.

## Mechanism

In the reported vulnerable configuration:

- Docker used the `systemd` cgroup driver on cgroup v2;
- GPUs were requested through `gpus: all` / the NVIDIA runtime-hook path;
- NVIDIA device permissions were present in the running container cgroup but were not represented equivalently in systemd's durable `DeviceAllow` state;
- a host `systemctl daemon-reload` caused systemd to re-apply the scope's device policy and remove the GPU permissions it did not know about.

That creates a delayed-reporter trap. Already-open device descriptors, already-loaded kernels, or existing mappings can keep useful GPU work alive for a while. The first later operation that needs a fresh NVIDIA device open, mapping, CUDA module load, Triton specialization, or first-seen workload shape can be where EPERM finally becomes visible.

The observed CUDA/Triton crash site therefore does not necessarily identify the causal model/runtime component.

## Controlled upstream evidence

@zlylong reported two long-uptime occurrences on 2x DGX Spark / GB10, TP=2 over RoCE, using `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` and a drowzeys Vision-EXP-ablit lane.

The later report closed the loop with a controlled A/B:

**Vulnerable arm**

1. GPU container starts with working CUDA.
2. Docker uses the `systemd` cgroup driver.
3. Host runs `systemctl daemon-reload`.
4. NVIDIA device-node access becomes denied.

**Mitigation arm**

1. Docker is switched to `native.cgroupdriver=cgroupfs`.
2. Docker is restarted and the stack recreated.
3. CUDA and `/dev/nvidiactl` access work.
4. Host runs the same `systemctl daemon-reload`.
5. CUDA and NVIDIA device-node access remain functional.
6. Text, image and `/v1/responses` requests succeed before and after the reload.

The reporter also connected the production incident timeline to host package maintenance / `unattended-upgrades` activity shortly before the failure.

## Mechanism boundary

Do not read this entry as "every Docker host using the systemd cgroup driver is broken."

Exposure depends on the realized combination of:

- Docker and `runc` version;
- cgroup version;
- NVIDIA driver and Container Toolkit version;
- legacy hook versus CDI versus explicit-device injection;
- whether required NVIDIA device nodes and `/dev/char` mappings exist;
- systemd device policy and the actual OCI device specification.

NVIDIA documents multiple mitigation families, including `cgroupfs`, explicitly requested device nodes, and CDI. Related older `runc` / device-node variants may not apply to every modern host.

Capture the realized runtime path rather than inferring vulnerability from `Cgroup Driver: systemd` alone.

## If you have this stack

Start with a **non-destructive** check on the affected running container:

```bash
docker info | grep -E 'Cgroup Driver|Cgroup Version'
systemctl show docker-<container-id>.scope -p DevicePolicy -p DeviceAllow
docker exec <container> sh -c '(exec 3<>/dev/nvidiactl) && echo OK || echo DENIED'
```

If a failure already occurred, also inspect host systemd reload and package-maintenance history around the timestamp before blaming the CUDA/Triton site.

A deliberate `systemctl daemon-reload` is a host-level infrastructure test. Do it only on a disposable/maintenance lane where losing GPU access is acceptable.

**CONFIRM.** On a pinned vulnerable configuration, device access and CUDA work before the reload, the controlled host `daemon-reload` removes NVIDIA device access, and an otherwise matched documented mitigation preserves access across the same reload.

**REFUTE.** The same pinned configuration retains NVIDIA device access across the reload, the reported serving failure occurs while the relevant device nodes remain accessible, or another independently demonstrated mechanism explains the failure without cgroup/device-policy revocation.

## Benchmark / soak consequence

Long-soak receipts should preserve Docker/cgroup/runc/NVIDIA-container provenance and distinguish host device revocation from model/runtime instability.

An unexplained long-uptime CUDA `operation not permitted`, NVML loss, or sudden `No CUDA GPUs are available` should trigger a device-access/cgroup check before it is classified as a model, quantization, Triton, scheduler, cache, vision, or runtime-age failure.

## Attribution

The systemd-cgroup / `daemon-reload` hypothesis and initial host evidence were reported by **@johnymoo**. The later controlled root-cause A/B on DGX Spark was reported by **@zlylong** in MiaAI-Lab issue #216. NVIDIA's Container Toolkit documentation independently documents the same failure class and mitigations.

This registry has not independently reproduced the mechanism.
