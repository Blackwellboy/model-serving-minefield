# Trap 123: killing the vLLM V1 API server does not kill its EngineCore worker, and the orphan keeps the GPU memory

**Found by vcruz305.**

**Status: contributor-measured, conditions as reported.** Measured on my own
hardware, twice in the same session, while iterating on `vllm serve` launch
flags. Not independently reproduced here as a first-party measurement
campaign. See [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary).

**Symptom.** You kill the `vllm serve` process to relaunch with different
flags — `kill -9 <pid>` on the PID your shell reported (or the PID a process
manager tracks) — expecting the GPU to come back. `ps aux` shows that PID
gone. The very next `vllm serve` launch dies at startup with:

```
ValueError: Free memory on device cuda:0 (8.88/121.69 GiB) on startup is less
than desired GPU memory utilization (0.85, 103.44 GiB). Decrease GPU memory
utilization or reduce GPU memory used by other processes.
```

Nothing else is running. The obvious reads are all wrong: the fraction isn't
too high, no other tenant is on the box, and the process you killed really is
gone from `ps`.

**Mechanism.** vLLM's V1 engine runs `EngineCore` as a separate OS process
from the API server — spawned via `multiprocessing`, not a thread — visible
in `ps aux` as its own line (`VLLM::EngineCore`) with its own PID, distinct
from the `vllm serve` / `APIServer` PID you have. Killing the API server PID,
even with `SIGKILL`, does not signal that child: nothing in the parent's exit
path notifies or reaps it, and unless the launcher explicitly put both in one
process group and killed the group, the signal never reaches the worker. The
`EngineCore` process is, from its own point of view, still completely alive —
weights and KV cache stay resident — until something kills it directly. A
plain "note the PID, `kill` it, relaunch" cycle never does that.

**Stacks and builds bitten.** vLLM V1 engine, build
`0.1.dev1+g75231eff2.d20260809` (a Blackwell/sm_121 nightly), single-node
`uniproc` executor, `NemotronHForCausalLM` (30B-A3B hybrid Mamba+MoE) at
NVFP4, on a DGX Spark (GB10, 121 GiB unified memory). The EngineCore-as-a-
subprocess design is a V1 engine property, not something specific to this
model, quant format, or hardware — the mechanism likely generalizes across
vLLM V1 deployments; I have not checked other builds or discrete-GPU boxes,
so treat that generalization as a hypothesis, not a claim.

**The check.**

```bash
# 1. find the EngineCore child, independent of the vllm serve/APIServer PID
ps aux | grep -i 'VLLM::EngineCore'

# 2. confirm it currently owns GPU memory
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# 3. kill only the outer process, the way "note the PID and kill it" normally goes
kill -9 <api_server_pid>
sleep 3

# 4. re-run 1 and 2 -- if EngineCore is still listed and nvidia-smi still
#    reports its memory, the kill did not reach the worker
ps aux | grep -i 'VLLM::EngineCore'
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

If step 4 still shows the `EngineCore` PID and its memory, the trap fired. A
clean kill leaves neither. Offline adjudicator over an observation object:
`checks/vllm_enginecore_orphan_probe.py`.

**The fix.** Kill the `EngineCore` PID directly (`kill -9 <engine_core_pid>`),
found via `ps aux | grep VLLM::EngineCore` or by cross-referencing
`nvidia-smi --query-compute-apps`. For anything you launch yourself, start
`vllm serve` inside its own process group (e.g. `setsid vllm serve ...`) and
kill the whole group (`kill -- -$PGID`) instead of a single captured PID.
Before touching `--gpu-memory-utilization` or any other launch flag in
response to a startup OOM, run `nvidia-smi --query-compute-apps` and confirm
there is genuinely nothing else holding memory — a leftover `EngineCore` PID
reads exactly like a fraction that is set too high.

**Found.** 2026-08-19, merging a LoRA-tuned checkpoint into NVFP4 and
iterating on `vllm serve` launch flags on a DGX Spark. The first occurrence
cost one failed relaunch attributed briefly to the wrong cause before
`nvidia-smi --query-compute-apps` pointed at the orphaned PID; the second
occurrence, later the same session, reproduced identically and was resolved
in one step by killing the `EngineCore` PID directly.

**Attribution.** vcruz305.
