# Trap 14: an abliterated or finetuned re-upload is not a drop-in

**Found by Blackwellboy and TheTom.**

**Status: measured here, raw not published**, and **reported by others** for
the behavioral half. Our per-shard hash table is not published, so the
specific digests below cannot be checked by reading our data. The check is a
command a reader runs against the two public repos themselves, which
re-derives the finding without us. The behavioral non-superset half is
documented upstream and linked.

**Symptom.** You swap a base model for its abliterated or finetuned
re-upload and assume "same model, one behavior patched". Then shards differ,
gating differs, the speculative drafter behaves differently, and a
"card-only revision bump" turns out to change generation.

**Mechanism.** Community re-uploads live in separate repos with their own
gating, their own shard sets, and sometimes changed auxiliary-head behavior.
Our measured case, migrating a large MoE lane from v1.0 to a v1.1
abliterated re-upload: authenticated per-shard sha256 comparison found
**45 of 48 shards identical and 3 genuinely different** (the tail shards
carrying the fix), which authorized a full requalification pass rather than
a config bump. The same family had earlier shipped draft-head config
changes (`edit_mtp` flag, edited-head count 36 to 33) that altered
speculative behavior and fixed a token-corruption bleed: drafter behavior
is part of the artifact, not a constant.

The behavioral half of this trap is upstream, credit TheTom: "a fine-tune
(or an RL-trained variant) is not automatically a strict superset of its
base", measured as capability regressions on held-out work
([offlabel patterns.md](https://github.com/TheTom/offlabel/blob/main/patterns.md)).

**Stacks and builds bitten.** A ~600B-class MoE with an MTP drafter, vLLM
TP=2 across two GB10 nodes, community abliterated re-upload; the upstream
patterns.md entry spans several model families.

**The check.** Before treating any re-upload as drop-in:

```bash
# per-shard digests, both repos, then diff
huggingface-cli download <repo> --include '*.safetensors' --dry-run  # or hash locally
sha256sum *.safetensors | sort > shards_a.txt   # repeat for the other side, diff
```

Diff shard hashes, `config.json`, the chat template, and every drafter or
auxiliary-head config. Anything that differs gets requalified, not assumed.

**The fix.** Treat re-uploads as new models with a shared ancestor. Pin
both revisions, state which one every number came from, and rerun your
acceptance battery on the swap.

**Found.** 2026-07-13 (shard comparison, internal migration log).

**Attribution.** Blackwellboy (shard and drafter mechanics); TheTom
(behavioral non-superset pattern).
