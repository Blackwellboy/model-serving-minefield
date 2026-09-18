# Trap 142: Docker volume syntax can turn a missing bind source into a directory

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported.** The contributor observed the missing-source and deleted-file lifecycle on Linux Docker hosts used for local model serving. Docker's current documentation independently confirms the syntax distinction at the core of the mechanism.

**Symptom.** A container launch appears to accept a bind-mounted model/config path that does not exist, then the serving stack fails later because the expected file or model payload is absent. A sharper variant occurs when a bind-mounted source file is deleted: a later launch recreates that path as a directory, and the container can then fail immediately with a file-versus-directory mount error. `docker logs` may be empty while the useful reason is in `.State.Error`.

**Mechanism.** Bind-mount behavior depends on the Docker syntax. With `-v/--volume`, a missing host-side bind source is created automatically, and Docker creates it as a **directory**. Compose short bind syntax preserves this create-missing-source behavior for backward compatibility. By contrast, `--mount type=bind` rejects a missing source by default unless source creation is explicitly requested, and Compose long syntax can set `create_host_path: false`.

The trap is therefore not "all Docker bind mounts fabricate paths". It is that a creating syntax can convert a typo, stale compose reference, or deleted file into a real directory, moving the visible failure away from the original missing source.

**Stacks and builds bitten.** Docker on Linux hosts serving local models; the behavior is container-runtime syntax specific rather than model-engine specific. The contributor observed it in serving deployments. Vendor documentation corroborates the current `-v/--volume`, `--mount type=bind`, Compose-short and Compose-long distinction. This entry does not claim identical behavior for every historical Docker release or every container runtime.

**The check.** On a disposable host path, test the syntax you actually deploy.

1. With `-v/--volume`, point the bind source at a nonexistent path and inspect the host afterward. The positive signature is that the source now exists as a directory.
2. Use `--mount type=bind` with a nonexistent source as a negative control. Without an explicit create-source option, container creation should fail instead of fabricating the directory.
3. For the file lifecycle, begin with a real file source under the creating syntax, launch successfully, remove the host file, then launch again. Inspect the recreated source type and the container's `.State.Error`.
4. If Compose is the deployment surface, separately test short syntax and long syntax with `create_host_path: false`.

**TRAP PRESENT:** a syntax expected by the operator to fail closed instead creates a directory at the missing source path, allowing a late model/config failure or creating a persistent file-versus-directory mismatch.

**TRAP ABSENT:** the deployment rejects a missing source before container start, or an explicit preflight proves the source exists with the required type/content before launch.

**The fix.** Prefer fail-closed bind semantics for critical model/config files: `--mount type=bind` without source creation, or Compose long syntax with `create_host_path: false`. Independently preflight source type and payload, not merely `exists()`. When a container dies immediately with no useful logs, inspect `.State.Error` before blaming the serving engine or checkpoint.

**Claim boundary.** May claim that Docker's creating bind syntaxes/options can fabricate a missing source as a directory and that the deleted-file lifecycle can turn a file mount into a type mismatch. Must name the syntax. Must not say every Docker bind mount does this: default `--mount type=bind` is the fail-closed control. This is distinct from Trap 127, where an existing whole-file bind mount shadows a module inside an image and later image drift produces a crash loop.

**Attribution.** Finding and serving-lane observation: **@scottleimroth**. Maintainer syntax adjudication and registry framing: Blackwellboy. Public report: [issue #100](https://github.com/Blackwellboy/model-serving-minefield/issues/100).

**Related.** [Trap 127](127-bind-mount-shadow-drift-crash-loop.md) covers an existing bind source shadowing image content, not fabrication of an absent source.
