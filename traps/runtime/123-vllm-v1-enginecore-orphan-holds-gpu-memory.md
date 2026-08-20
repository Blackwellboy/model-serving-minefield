# Trap 123: abrupt API-server PID kill can leave vLLM V1 EngineCore orphaned with GPU memory

**Found by vcruz305 (Victor Cruz).**

**Status: contributor-measured, conditions as reported.** Cruz measured this twice in one session on his own DGX Spark while iterating on `vllm serve` launch flags. The exact contributor lane and public corroboration are recorded below. Blackwellboy has not independently reproduced the runtime failure, so the contributor measurement remains the status-bearing evidence.

**Symptom.** You kill the outer `vllm serve` / API-server PID to relaunch with different flags — in the measured case, `kill -9 <api_server_pid>` — and the PID disappears from `ps`, but GPU memory does not come back. The next `vllm serve` launch then dies at startup with a message that looks like a bad memory-utilization setting:

```
ValueError: Free memory on device cuda:0 (8.88/121.69 GiB) on startup is less
than desired GPU memory utilization (0.85, 103.44 GiB). Decrease GPU memory
utilization or reduce GPU memory used by other processes.
```

On the contributor's failing state, the surviving `VLLM::EngineCore` process was reported by `nvidia-smi` as holding **104277 MiB** after the outer API-server PID had been killed. The same sequence occurred twice in the session and was cleared by killing the EngineCore PID directly.

The trap is therefore not "0.85 is too high". The discriminating observation is that the process you killed is gone while a distinct EngineCore PID still owns the GPU allocation.

**Mechanism.** vLLM V1 is deliberately multi-process. The current upstream architecture documentation separates the API server, EngineCore and GPU-worker processes; the API server talks to EngineCore over ZMQ, and EngineCore is a distinct process per data-parallel rank. Current upstream source also creates local EngineCore instances with `multiprocessing` and carries explicit graceful-shutdown/finalizer machinery.

That distinction matters to the claim boundary. Cruz did **not** show that normal vLLM shutdown is universally broken. He showed that an abrupt **direct SIGKILL of only the API-server PID** did not propagate to the distinct EngineCore process on his pinned build. SIGKILL cannot run the parent process's normal cleanup/finalizer path. A launcher or shell pattern that only targets `vllm serve` can likewise miss a child whose process title is `VLLM::EngineCore`.

The surviving EngineCore then remains a real live resource owner until separately terminated, so the next launch sees genuinely unavailable GPU memory and reports the generic startup utilization error.

**Stacks and builds bitten.** Contributor-measured on vLLM V1 build `0.1.dev1+g75231eff2.d20260809` (Blackwell/sm_121 nightly), single-node `uniproc` executor, `NemotronHForCausalLM` (30B-A3B hybrid Mamba+MoE) at NVFP4, DGX Spark (GB10, 121 GiB unified memory).

The process split is a V1 architecture property, but the exact teardown behavior is build/launcher/signal dependent. Do not generalize the DGX Spark measurement into "every vLLM V1 shutdown leaks memory." In particular, current upstream source has an EngineCore process manager with an explicit `shutdown()` path; graceful SIGTERM/service-manager teardown must be measured separately from parent-only SIGKILL.

**Independent public corroboration.** These sources strengthen the process/lifecycle interpretation without changing the status from contributor-measured:

- [vLLM current architecture overview](https://github.com/vllm-project/vllm/blob/main/docs/design/arch_overview.md) documents API server, EngineCore and GPU workers as separate V1 processes.
- [vLLM current `vllm/v1/engine/utils.py`](https://github.com/vllm-project/vllm/blob/main/vllm/v1/engine/utils.py) shows EngineCore creation through a multiprocessing context and the normal process-manager shutdown/finalizer path.
- [vLLM issue #47266](https://github.com/vllm-project/vllm/issues/47266), on RTX PRO 6000 Blackwell / vLLM 0.24.0, independently reports abrupt parent teardown leaving `VLLM::EngineCore` / worker processes alive and retaining GPU memory, followed by the same class of next-launch free-memory error.
- [vLLM issue #48234](https://github.com/vllm-project/vllm/issues/48234), on RTX PRO 6000 Blackwell / vLLM 0.24.0, separately reports crashes leaving orphaned `VLLM::EngineCore` processes that retain GPU memory and must be killed before restart.
- [vllm-metal issue #479](https://github.com/vllm-project/vllm-metal/issues/479) explicitly records a different bug whose investigation found that `pkill -f "vllm serve"` did not match the renamed `VLLM::EngineCore`, leaving EngineCore/resource-tracker processes behind. That corroborates the process-title/naive-kill failure mode, not the NVIDIA memory amount.

**The check.** Identify the *same EngineCore PID* in both the process table and GPU process accounting before and after killing only the outer API-server PID:

```bash
# 1. identify API server and EngineCore separately
pgrep -af 'vllm serve|api_server'
pgrep -af 'VLLM::EngineCore'

# 2. bind GPU memory ownership to the EngineCore PID, not just "some memory exists"
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv

# 3. reproduce only when it is safe to do so: kill the outer API-server PID
kill -9 <api_server_pid>
sleep 3

# 4. the trap fires only if the EngineCore PID survives AND still owns GPU memory
pgrep -af 'VLLM::EngineCore'
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv
```

If step 4 shows the same surviving EngineCore PID with non-zero GPU memory after the API-server PID is gone, the trap fired. Generic residual GPU use from another PID is **not** enough to diagnose this trap. The offline adjudicator mirrors that ownership requirement: `checks/vllm_enginecore_orphan_probe.py`.

**The fix.** Prefer graceful service teardown that lets vLLM's process manager clean up EngineCore and workers, and verify that the GPU allocation actually falls before relaunching. For a genuinely orphaned measured state, terminate the owning `VLLM::EngineCore` PID and any associated vLLM workers rather than lowering `--gpu-memory-utilization` to fit around the leak.

For launchers you control, supervise the whole process tree/process group instead of retaining only the API-server PID. A `setsid`-style process group can make group teardown explicit, but validate the exact service-manager semantics on your stack rather than assuming one shell recipe is portable everywhere.

Before changing memory flags in response to this startup error, first inspect the GPU process table. If no EngineCore PID owns the missing memory, this trap does not own the diagnosis; on DGX Spark/shared-memory systems see [Trap 119](../memory/119-free-memory-drifts-down-after-churn.md) for moving shared-pool pressure and other reclaim states.

**Found.** 2026-08-19, while Cruz was merging a LoRA-tuned checkpoint into NVFP4 and iterating on `vllm serve` launch flags on a DGX Spark. The LoRA merge, model family and quantization describe the lane; none is claimed as causal. The first occurrence caused one failed relaunch to be briefly attributed to the wrong cause. The second reproduced the same lifecycle state and was cleared by terminating EngineCore directly.

**Attribution.** **Victor Cruz / @vcruz305** — finder and contributor measurement for this trap. Public-source reporters above retain credit for their independent corroborating reports. See also [Trap 116](116-successful-load-does-not-prove-first-forward-dtype-path.md), where Cruz authored the F16 embedding patch chain and instrumentation used for runtime proof while Blackwellboy performed the external multi-node hardware qualification.

**Related.** [119](../memory/119-free-memory-drifts-down-after-churn.md) (same startup-memory symptom family, different ownership), [116](116-successful-load-does-not-prove-first-forward-dtype-path.md) (Cruz patch/instrumentation contribution; different mechanism), [112](112-process-liveness-is-not-model-readiness.md) (process state is not a readiness verdict).
