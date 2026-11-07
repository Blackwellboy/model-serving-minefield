# Trap 168: `down --all` on a multi-group cluster tool stopped one group, said nothing about the others, and exited 0

**Found by Blackwellboy.**

**Status: reproduced here** (runnable `--dry-run` procedure below against the
public REXL3 v0.1.0 source and its shipped example cluster file; run on
2026-11-08 without contacting any node).

**Symptom.** You run several tensor-parallel groups from one cluster file and
take them all down with `rexl3-cluster down --cluster FILE --all`. It prints a
normal shutdown for one group and exits 0. The other groups keep running and
keep their GPUs and memory. The next `up` on those nodes then fails on a busy
GPU lock or a memory check, a long way from the command that caused it, or the
"stopped" lane goes on answering requests.

**Mechanism.** In REXL3 v0.1.0, `pick()` (`crates/cluster/src/main.rs`,
line 170) returns every group when `--all` is given. The usage text says
`--all` is for `check`, `status` and `validate`, but nothing refused it on
the other commands, and `up`, `down`, `supervise`, `logs`, `exec` and `env`
each take `gs[0]` from that list (`main.rs`, lines 513-535). The flag is
accepted, the first group is acted on, and the rest of the list is dropped
without a message.

The same tool had a quieter neighbour. A top-level per-rank
`"memory": {"min_free_gib": [...]}` list was never checked against a group's
rank count, and a rank past the end of the list got a requirement of 0 GiB
(`schema.rs`, line 133), so with `[90]` and two ranks the second rank's memory
check always passed.

The general lesson: a bulk command that accepts a scope flag it does not
implement is worse than one that rejects it, because exit 0 is what the
operator checks.

**Stacks and builds bitten.** `rexl3-cluster` from REXL3 v0.1.0 (engine source
snapshot `afc9b5df`), any cluster file with two or more groups. Reported with
a patch and tests as
[REXL3/REXL3#92](https://github.com/REXL3/REXL3/issues/92) (open when this
entry was written). Not tested: other cluster launchers.

**The check.** From the published source, with no GPU and nothing sent to a
node (`--dry-run` only prints the scripts it would run):

```bash
REXL3_NO_CUDA=1 cargo build --locked -p gb-cluster --bin rexl3-cluster
target/debug/rexl3-cluster down --cluster docs/examples/cluster.dp-fleet.json --all --dry-run
echo "exit=$?"
```

That example has two groups, `g0` on nodes A1 and A2 and `g1` on A3 and A4. On
v0.1.0 the output begins `down: cluster example-fleet group g0`, every script
is for A1 or A2, no line names `g1`, A3 or A4, and the exit status is 0. A fixed
build refuses `--all` here with a usage error, exit 2.

For any multi-group tool: after a bulk stop, list what is still running per
group rather than trusting the stop command's exit status.

**The fix.** On v0.1.0, stop each group by name (`--group g0`, then
`--group g1`, and so on) and confirm each with `status`. Give every group its
own `min_free_gib` list, or use one number for all ranks, rather than a
top-level per-rank list. The patch in #92 makes `--all` a usage error on the
single-group commands and checks the top-level list against each group that
falls back to it.

**Found.** 2026-11-08, checking the findings of a model-run source audit of the
REXL3 v0.1.0 engine against the code.

**Attribution.** Blackwellboy. Upstream report:
[REXL3/REXL3#92](https://github.com/REXL3/REXL3/issues/92).
