# Trap 117: a compilation flag is echoed back enabled and runs disabled

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (both log lines are
emitted by stock vLLM in the same boot, and the gating logic is readable in
the shipped source, so the mechanism is checkable without our data).

**Symptom.** You pass `fuse_gemm_comms` in `--compilation-config`. vLLM's own
startup summary echoes it back as `True`. Roughly fifteen seconds later the
engine prints its resolved config, and the same key is `False`. Serving is
completely healthy. Nothing fails, nothing warns you by name, and every A/B
you run "with the pass on versus off" is comparing a config against itself.

```
non-default args: {... 'pass_config': {'fuse_gemm_comms': True} ...}

Initializing a V1 LLM engine ... compilation_config={...
  'pass_config': {'fuse_norm_quant': False, ..., 'enable_sp': False,
                  'fuse_gemm_comms': False, ...} ...}
```

We had carried this flag in a production launcher for two days and had
attributed roughly +2 tok/s aggregate to it in an earlier tuning writeup. The
pass never ran in either arm; the delta was noise.

**Mechanism.** Two layers, and the second is worse than the first.

*The silent downgrade.* `fuse_gemm_comms` is gated behind sequence
parallelism, and SP declines on its own in `vllm/config/vllm.py`:

```python
if pass_config.fuse_gemm_comms:
    pass_config.enable_sp = True
if pass_config.enable_sp:
    ...
    pass_config.sp_min_token_num = get_sequence_parallelism_threshold(
        hidden_size, tp_size, element_size)
    if pass_config.sp_min_token_num is None:
        logger.warning("Model hidden_size too small for the SP threshold "
                       "heuristic, disabling. To force SP, set "
                       "pass_config.sp_min_token_num manually.")
        pass_config.enable_sp = False
        pass_config.fuse_gemm_comms = False
```

`get_sequence_parallelism_threshold()` in
`vllm/compilation/passes/fusion/sequence_parallelism.py` returns `None` for two
independent reasons, either sufficient on its own:

```python
SP_MIN_HIDDEN_SIZE: dict[int, int] = {
    90: 8192,   # H100
    100: 8192,  # Blackwell family
}
```

1. **The device capability is not in the table.** GB10 is sm_121, and only 90
   and 100 are listed, so `.get(121)` returns `None` and SP is off. A device
   that is simply newer than the table falls through silently.
2. **hidden_size is under the floor.** GLM-5.2 is `hidden_size: 6144`, below
   8192, so the heuristic declines even on a device that *is* listed.

A warning does fire, but it describes the heuristic ("hidden_size too small")
rather than naming the flag it just overrode, and it lands among several
hundred startup lines.

*The trap behind the trap.* Take the warning's own advice and force it with
`sp_min_token_num`. The resolved config now honestly reports the pass as
enabled:

```
pass_config': {'enable_sp': True, 'fuse_gemm_comms': True, 'sp_min_token_num': 1}
```

and the boot dies during `determine_available_memory`:

```
buf34 = torch.ops.symm_mem.fused_matmul_reduce_scatter.default(...)
  File ".../torch/distributed/_symmetric_memory/__init__.py", ...
RuntimeError: Failed to send fd: No such file or directory
```

The pass lowers to `fused_matmul_reduce_scatter` on PyTorch **symmetric
memory**, which rendezvouses by passing file descriptors between processes on
one host. Four separate physical nodes share no host, so the fused path cannot
work multi-node at any setting. The heuristic that quietly disabled it was
right for this cluster; it simply never said so, and the documented override
converts a silent no-op into a hard crash at init.

**Stacks and builds bitten.** vLLM `v0.23.1rc1.dev190+gab6660699.d20260704`,
`QuantTrio/GLM-5.2-Int4-Int8Mix` (compressed-tensors, unpruned), 200K context,
`fp8_ds_mla` KV, in-checkpoint MTP, `--distributed-executor-backend mp`, TP=4
across four DGX Spark (GB10, sm_121a, aarch64) nodes over RoCE.

Exposure is wider than this stack. Layer one reaches **any** model with
`hidden_size < 8192` on any device, and **any** device whose capability is
missing from `SP_MIN_HIDDEN_SIZE`. Layer two reaches **any** multi-node
deployment regardless of model size.

**The check.** Do not read the "non-default args" echo, which reports what you
asked for. Read the resolved config, printed by `Initializing a V1 LLM engine`:

```bash
docker logs <container> 2>&1 | grep -oE "pass_config[^}]*}" | tail -1
```

`'fuse_gemm_comms': False` after you passed `true` is the trap. Confirm which
of the two reasons applies, straight from the shipped source:

```bash
docker exec <container> python3 -c "
from vllm.compilation.passes.fusion.sequence_parallelism import SP_MIN_HIDDEN_SIZE
from vllm.platforms import current_platform
cap = current_platform.get_device_capability().to_int()
print('capability:', cap, 'in table:', cap in SP_MIN_HIDDEN_SIZE)
print('table:', SP_MIN_HIDDEN_SIZE)"
```

`in table: False`, or a model `hidden_size` below the printed floor, is the
cause.

**The fix.** On multi-node, leave it off and stop attributing throughput to it.
Do not "repair" it with `sp_min_token_num`: that turns a no-op into a crash,
because symmetric memory cannot span hosts. On single-node with a
small-hidden_size model, forcing it is legitimate, but verify against the
resolved config rather than the CLI echo.

The upstream-shaped ask is a warning that names the overridden flag instead of
describing the heuristic, and ideally a hard error when `fuse_gemm_comms` is
requested explicitly on a multi-node deployment where it cannot work.

**Found.** 2026-08-16, while trying to reproduce a remembered ~31 tok/s
single-stream figure on GLM-5.2 that the current build would not produce. The
remembered number turned out to predate the gate; the config that "achieved"
it had been running the pass disabled the whole time.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet. Gating logic quoted from
stock vLLM: `vllm/config/vllm.py`,
`vllm/compilation/passes/fusion/sequence_parallelism.py`. Reported as
[#43](https://github.com/Blackwellboy/model-serving-minefield/issues/43).
