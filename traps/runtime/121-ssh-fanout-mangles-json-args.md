# Trap 121: the launcher reports success, prints container IDs, and the workers never start

**Found by tonyd2wild.**

**Status: contributor-measured, conditions as reported** (reproduced against
two launchers on the same cluster, same image, same arguments, differing only
in remote-command quoting).

**Symptom.** A multi-node launcher completes cleanly and prints a container ID
for every worker. On the head, `docker ps` shows the head container `Up`. On
the workers, `docker ps -a` shows the container in **`Created`** — never `Up`.
No crash, no error, and `docker logs` is empty because the entrypoint never
ran. The head then waits for ranks that will never arrive, which presents as a
distributed-init hang rather than a launch failure.

The launcher's own output is the misleading part: container IDs were genuinely
issued, so every line it prints is true and the deployment is still dead.

**Mechanism.** The launcher builds a `docker run ... vllm serve ...` command and
ships it to each worker over `ssh`. The serve command contains JSON-valued
arguments such as:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":4,
                       "draft_tensor_parallel_size":1,
                       "attention_backend":"FLASHMLA_SPARSE"}'
```

A command that is safe as a local argv can become unsafe when flattened to a
string and parsed again by a remote shell. In the contributor's failing
launcher, quoting was consumed/reinterpreted across that second parse and the
remote `docker run` received different arguments from the local command.
Docker created the container object but never reached a runnable entrypoint, so
workers remained in `Created` while the launcher printed valid container IDs.

Nothing in the failure mentions quoting. The same command pasted by hand on
the worker works, which sends people looking at the image, the mounts or the
fabric.

**Stacks and builds bitten.** Any SSH-fanout launcher that serializes argv into
a shell command while carrying JSON-valued CLI arguments such as
`--speculative-config`, `--compilation-config`, `--hf-overrides`, or
`--attention-config`. Observed with vLLM on four DGX Spark (GB10, sm_121a,
aarch64) nodes, GLM-5.2 with in-checkpoint MTP. This is a transport/launcher
failure class rather than a vLLM-specific one.

**The check.** Assert *running*, not merely *created*, after launch:

```bash
for h in "${WORKERS[@]}"; do
  ssh "$h" 'docker ps -a --format "{{.Names}}:{{.Status}}"' | grep "$NAME"
done
```

Any worker reporting `Created` is a launch failure even if the launcher printed
a container ID. To debug the transport, compare a known-good local argv with
what the remote entrypoint actually receives; avoid relying only on the
human-readable command string printed before `ssh`.

**The fix.** Preserve the argument boundaries across the remote transport.
One contributor-tested option, **when both sides deliberately use Bash**, is
Bash's `%q` escaping:

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
worker is actually `Up` before declaring distributed initialization started.

Related in shape to [112](112-process-liveness-is-not-model-readiness.md): a
container object existing is not the container running, in the same way a
process existing is not a model serving.

**Found.** 2026-08-15, when a second operator's launcher could not start
workers on a cluster where a different launcher, same image and same
arguments, worked. The material difference was how the remote command
preserved argument boundaries.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet.
