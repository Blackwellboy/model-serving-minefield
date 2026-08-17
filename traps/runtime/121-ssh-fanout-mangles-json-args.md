# Trap 121: SSH fanout reparses structured argv while the launcher still reports success

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (two launchers on the
same cluster, same image and intended arguments; the failing path serialized
the command through an additional remote-shell parse while the working path
preserved the arguments).

**Symptom.** A multi-node launcher completes cleanly and prints a container ID
for every worker, but one or more workers never become usable ranks. In the
contributor's failing run, `docker ps -a` showed the affected worker containers
in **`Created`** while the head waited for ranks that never arrived.

The container IDs are therefore a false readiness signal: they prove that
Docker created objects, not that the remote command survived transport or that
the workers reached the serving entrypoint.

**Important boundary on the observed `Created` state.** `Created` by itself is
**not evidence of malformed vLLM application arguments**. Docker normally
starts the container before an application such as vLLM parses arguments after
the image/command boundary; an application-argument parse failure will commonly
leave an `Exited` container instead. `Created` has several Docker/runtime causes.
The measured `Created` state is retained here as part of the contributor's
observation, but this entry does not use it to prove which token was corrupted.

**Mechanism.** The portable failure class is the extra shell parse. A launcher
starts from an argv-like command containing structured values such as:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":4,
                       "draft_tensor_parallel_size":1,
                       "attention_backend":"FLASHMLA_SPARSE"}'
```

If that argv is flattened to a string, sent through `ssh`, and interpreted by a
second shell, quoting and argument boundaries can change. JSON is an obvious
victim, but Docker-level options, mounts, environment values and application
arguments can all be affected depending on where the quoting breaks. A command
that works when executed directly on the worker is therefore not proof that the
fanout transported the same argv.

The contributor's two launchers differed in this transport behavior and only
the argument-preserving path brought the workers up. That is the finding carried
here. The exact reason the failing instance stopped in Docker's `Created` state
was not independently isolated, so the entry deliberately does not claim that
malformed JSON application args uniquely produce `Created`.

**Stacks and builds bitten.** Any SSH-fanout launcher that serializes argv into
a shell command while carrying JSON-valued CLI arguments such as
`--speculative-config`, `--compilation-config`, `--hf-overrides`, or
`--attention-config`. Observed with vLLM on four DGX Spark (GB10, sm_121a,
aarch64) nodes serving GLM-5.2 with in-checkpoint MTP. This is a
transport/launcher failure class rather than a vLLM-specific one.

**The check.** Assert actual worker state after launch and inspect Docker's own
state/error before assigning a cause:

```bash
for h in "${WORKERS[@]}"; do
  ssh "$h" 'docker ps -a --format "{{.Names}}:{{.Status}}"' | grep "$NAME"
  ssh "$h" 'docker inspect --format "status={{.State.Status}} error={{json .State.Error}} exit={{.State.ExitCode}}" '"$NAME"
done
```

Treat `Created`, `Exited`, or a missing expected container as **launch failure**,
not as proof of this specific trap. To confirm the transport failure, compare a
known-good local argv with what the remote execution layer actually receives.
Useful methods are `set -x` in a temporary remote wrapper, an argv-dumping
entrypoint in a disposable diagnostic container, or a launcher mode that writes
the exact remote script before executing it. The confirmation is an argument or
quoting difference across the transport, not a particular Docker state.

**The fix.** Preserve argument boundaries across the remote transport. One
contributor-tested option, **when both sides deliberately use Bash**, is Bash's
`%q` escaping:

```bash
shell=$(printf '%q ' "${cmd[@]}")
ssh "$user@$ip" "bash -lc $'${shell//\'/\'\\\'\'}'"
```

`printf %q` is Bash-specific; do not present it as a portable POSIX-shell
solution. Safer cross-environment patterns are to copy a generated script to
the worker and execute it, pass structured configuration through a file or
environment variable instead of an inline JSON shell fragment, or use an
argv-safe remote-execution API that does not add another shell parse.

Whatever transport is chosen, add a post-launch assertion that every expected
worker is actually running and has reached the intended entrypoint before
declaring distributed initialization started.

Related in shape to [112](112-process-liveness-is-not-model-readiness.md): a
container object existing is not the container running, in the same way a
process existing is not a model serving.

**Found.** 2026-08-15, when a second operator's launcher could not start
workers on a cluster where a different launcher, same image and intended
arguments, worked. The material difference reported was how the remote command
preserved argument boundaries.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet.
