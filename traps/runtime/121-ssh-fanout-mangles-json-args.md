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

**Mechanism.** The launcher builds a `docker run ... vllm serve ...` string and
ships it to each worker over `ssh`. The serve command contains JSON:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":4,
                       "draft_tensor_parallel_size":1,
                       "attention_backend":"FLASHMLA_SPARSE"}'
```

`ssh` concatenates its arguments and hands them to a **second** shell on the
remote host. The local shell consumes the single quotes, the remote shell
re-splits on braces, commas and colons, and `docker` receives a malformed
argv. Docker creates the container object, fails to assemble a runnable
command, and leaves it in `Created`.

Nothing in the failure mentions quoting. The same command pasted by hand on
the worker works, which sends people looking at the image, the mounts or the
fabric.

**Stacks and builds bitten.** Any SSH-fanout launcher passing JSON-valued CLI
arguments: `--speculative-config`, `--compilation-config`, `--hf-overrides`,
`--attention-config`. Observed with vLLM on four DGX Spark (GB10, sm_121a,
aarch64) nodes, GLM-5.2 with in-checkpoint MTP. Not vLLM-specific — it is a
property of the transport, not the server.

**The check.** Assert *running*, not *created*, after launch:

```bash
for h in "${WORKERS[@]}"; do
  ssh "$h" 'docker ps -a --format "{{.Names}}:{{.Status}}"' | grep "$NAME"
done
```

Any worker reporting `Created` is this trap. To see it directly, print what
the remote shell actually received:

```bash
ssh "$h" 'printf "ARGV: %s\n" "$@"' _ $CMD    # braces and quotes re-split
```

**The fix.** Quote the entire remote command so it survives the second shell:

```bash
shell=$(printf '%q ' "${cmd[@]}")
ssh "$user@$ip" "$shell"
```

A launcher doing this starts workers reliably with identical arguments; the
same launcher without it failed every time on any argument containing `{`.
The alternative that sidesteps quoting entirely is to write the command to a
script, copy it over, and execute the file.

Related in shape to [112](112-process-liveness-is-not-model-readiness.md): a
container object existing is not the container running, in the same way a
process existing is not a model serving.

**Found.** 2026-08-15, when a second operator's launcher could not start
workers on a cluster where a different launcher, same image and same
arguments, worked. The only material difference was `printf %q` on the remote
command.

**Attribution.** tonyd2wild, 4x DGX Spark GB10 fleet.
