# Trap 131: a stray byte in the HF hub refs file breaks pinned offline revision resolution on every node

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Measured on the
finder's private 2x DGX Spark (GB10) lane and its staging NAS during
2026-08-12 to 2026-08-23. Blackwellboy has not independently reproduced this
lane. Conditions and counts below; raw artifacts are private.

**Symptom.** A model that staged and verified fine fails to resolve offline on
one or more nodes, with no change to the weights or the pin. Or a cache staged
by exact commit works when addressed by that commit but later fails when the
serve path asks for a branch name such as `main`. If the mismatch is only
noticed after deployment, nodes can end up resolving different local snapshots
under what the operator thought was one model identity.

**Mechanism.** Hugging Face Hub revision resolution uses the `refs/*` files to
map branch/tag names to snapshot commits. On the measured copy, a trailing
newline in `refs/main` became part of the revision string, so offline resolution
failed even though the snapshot bytes were present.

A second measured staging case had no `refs/main` after a commit-hash-only
fetch. That is **not, by itself, a Hugging Face Hub bug**: a workflow that asks
only for an exact commit need not have established a branch mapping. It becomes
a deployment trap when staging verifies one addressing mode (exact SHA) and the
later offline serve uses another (bare name / `main`) without validating that
the required ref mapping exists. The common mechanism is a local cache whose
`refs` bytes/mappings do not match the revision contract production will use.

**Public corroboration for the newline half.** [`huggingface_hub` issue
#4133](https://github.com/huggingface/huggingface_hub/issues/4133) reports the
same offline-resolution failure when a trailing newline becomes part of the
commit-hash string. That upstream report does not upgrade this entry's status;
the measured lane and counts here remain contributor-measured.

**Stacks and builds bitten.** HF hub cache staged on a NAS and rsynced to two
DGX Spark (GB10) nodes running vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), offline mode on
(`HF_HUB_OFFLINE=1`). Measured: a trailing newline in `refs/*` broke revision
resolution for the DeepSeek-V4-Flash model copy on both nodes and the NAS; a
405 GB commit-pinned staging fetch of another model had no `refs/main`, and a
later bare/`main` offline lookup was unresolvable until the staging layout was
normalized to include the mapping that deployment expected. The finder's
deploy gate exists precisely because this class of divergence is otherwise
silent.

**The check.**

1. Inspect the exact bytes of every `refs/*` file used by the deployment. A
   branch ref should contain exactly the expected commit id, with no accidental
   whitespace/newline bytes.
2. Record the revision form production will actually request: exact commit,
   branch/tag, or bare/default revision. If production will resolve `main`,
   verify that `refs/main` exists and maps exactly to the intended snapshot;
   if production uses an exact SHA, verify that exact snapshot directly rather
   than inventing an unnecessary branch ref.
3. Compare required ref bytes and snapshot checksums across staging and every
   node before the first offline load. Resolution-mode parity is the gate; an
   online staging success is not.

**The fix.** Make the staging and serving revision contract identical. Normalize
accidental whitespace in `refs/*`; preserve or deliberately create only the
branch/tag mappings that the later offline deployment actually requires; and
gate every node on both the expected ref mapping and snapshot checksums. A pin
written in a serve config is not sufficient if the local offline cache cannot
resolve that same pin/addressing mode.

**Found.** 2026-08-12 (the newline on the DeepSeek copy) and 2026-08-23 (the
commit-pinned staging / later branch-resolution mismatch), during staging and
cross-node verification.

**Attribution.** @sethforprivacy. Raw staging logs are in the finder's private
deployment and were not published.

**Related.** [14](14-finetune-reupload-not-drop-in.md), [75](75-release-asset-renamed-pinned-url-404.md), [21](21-no-generation-config-server-defaults-win.md).
