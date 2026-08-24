# Trap 133: a stray byte in the HF hub refs file breaks pinned offline revision resolution on every node

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Measured on the
finder's private 2x DGX Spark (GB10) lane and its staging NAS during
2026-08-12 to 2026-08-23. Blackwellboy has not independently reproduced this
lane. Conditions and counts below; raw artifacts are private.

**Symptom.** A model that staged and verified fine fails to resolve offline on
one or more nodes, with no change to the weights or the pin. Or: a fetch
pinned by commit hash alone leaves the bare model name unresolvable, so the
first load errors even though the same snapshot loaded during staging. If the
failure is only noticed after a load, two nodes can silently hold different
weights under the same model name, which is divergence, not failure.

**Mechanism.** Hugging Face hub revision resolution reads the `refs/*` files
with a plain read and no strip. A stray trailing newline in `refs/main`
changes the resolved revision, so offline resolution of the pinned name
fails. Separately, a fetch pinned by commit hash alone writes no `refs/main`
at all, so the hub has no mapping from the bare model name to a revision and
any offline resolution by name has nothing to look up. Both are quiet
byte-level defects in the staged artifact; neither shows up during an online
fetch.

**Stacks and builds bitten.** HF hub cache staged on a NAS and rsynced to two
DGX Spark (GB10) nodes running vLLM `0.25.2.dev0+g752a3a504.d20260714`
(Anemll `dspark-vllm-gx10:0.1.1` image), offline mode on
(`HF_HUB_OFFLINE=1`). Measured: a trailing newline in `refs/*` broke revision
resolution for the DeepSeek-V4-Flash model copy on both nodes and the NAS;
a 405 GB sha-pinned fetch of a different model wrote no `refs/main`, and the
bare model name was unresolvable offline until a `refs/main` carrying the
pinned sha was created by hand. The finder's deploy gate exists precisely
because this class of divergence is otherwise silent.

**The check.**

1. `cat -A` the `refs/*` files in the staged cache: a trailing `$` at end of
   line is the defect.
2. After any sha-pinned fetch, verify `refs/main` exists and contains exactly
   the pinned sha with no trailing newline. If it is missing, write it by
   hand.
3. Compare the `refs/*` bytes across nodes (and the staging copy) before the
   first load, and checksum the snapshot on each node; load-time parity is
   the gate that catches divergence before inference, not after.

**The fix.** Strip trailing newlines in the fetcher (and normalize `refs/*`
when staging), and create `refs/main` from the pinned sha whenever the fetch
was pinned by hash alone. Treat the staged hub-cache snapshot as a deploy
artifact, not a byproduct: gate both nodes on refs bytes and shard
checksums before serving. A revision pin in the serve config is not a
substitute for a byte-correct local cache when offline.

**Found.** 2026-08-12 (the newline on the DeepSeek copy) and 2026-08-23 (the
sha-pinned fetch writing no `refs/main`), during staging and cross-node
verification.

**Attribution.** @sethforprivacy. Raw staging logs are in the finder's private
deployment and were not published.

**Related.** [14](../versioning/14-finetune-reupload-not-drop-in.md), [75](../versioning/75-release-asset-renamed-pinned-url-404.md), [21](../versioning/21-no-generation-config-server-defaults-win.md).
