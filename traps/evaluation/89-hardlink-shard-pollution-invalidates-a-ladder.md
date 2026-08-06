# Trap 89: an in-place weight edit mutates the "stock" copy through a shared inode, and every comparison against it is quietly wrong

**Found by [@drowzeys](https://github.com/drowzeys) (Keys). Shared by
[@drowzeys](https://github.com/drowzeys), from his public notes.**

**Status: contributor-measured, conditions as reported** (published by Keys in
[notes-for-DSV4F-DSpark-Abliteration](https://github.com/drowzeys/notes-for-DSV4F-DSpark-Abliteration/blob/afd4137540ba5c4c2a1e96ecaf4200af74f8dfd8/TECHNICAL_REPORT.md),
sections 2.3, 3 row F5 and 3.2, at commit `afd4137`). Measured by Keys on a dual
DGX Spark GB10 fleet; **not reproduced here and not measured here.**

**Symptom.** A ladder of weight-edit recipes returns numbers that look clean -
coherent output, no errors, plausible monotonic ordering - and one rung comes in
far below where the surrounding rungs say it should. In the reported case a
recipe scored **~25% refusal bypass** with clean-looking coherence, sitting well
below a neighbouring milder recipe. The number is not noise and it is not the
recipe. It is that the thing being compared against is no longer what it says it
is: the run's *baseline* was silently modified by an earlier run in the same
ladder.

**Mechanism.** On multi-node fleets, model directories are commonly populated in
ways that **hardlink shard files** - a Hugging Face cache blob hardlinked into a
`--local-dir`, a `cp -al` staging copy, a per-node clone made from a shared cache.
Two paths that look like two independent copies are one inode with two names.

A weight-editing tool that opens a shard and writes it **in place** then writes
*through* the link. The edit lands in the "stock" copy as well as the destination
copy. Nothing errors. The filesystem did exactly what it was asked.

From that point every measurement in the campaign is against a contaminated
reference, and the failure is silent in both directions: the edited model looks
weaker than it is (the delta to "stock" shrank because stock moved toward it), and
"stock" is no longer a control at all. In the reported case, restoring stock from
a pristine copy and re-running **the same recipe** moved it from ~25% straight
into the winning band - the recipe had always been fine.

The reason this is a measurement trap and not merely a file-handling bug is that
it produces *clean* numbers. There is no corrupted output to notice, no exception,
no NaN. A ladder poisoned this way reads as a legitimate result and gets
published.

**Stacks and builds bitten.** As reported: DeepSeek-V4-Flash-DSpark (FP8 / NVFP4
serve path), dual DGX Spark GB10, TP=2, weight edits applied to FP8
`attn.wo_b` tensors by a first-party script. The mechanism is filesystem-level and
is **not specific to that model, that stack or that edit type** - anything that
rewrites shards in place (quantization passes, merges, LoRA folding, dtype
conversion, tensor surgery) over a hardlinked tree carries it. We state the one
stack it was observed on, per the evidence bar; the generality is a hypothesis,
labelled as one, and kept out of the symptom and check sections.

**It produced a published number.** Yes - the reported F5 rung
("L10-42 lambda=3.0 no-mtp on dirty stock, ~25% bypass") is recorded in the source
table as **invalid**, and is one of the two rows Keys' own selection ladder marks
that way.

**The check.** Two assertions, both runnable before any number is published.

1. **Prove the copies are actually separate copies.** Compare inode numbers
   between the edit destination and every copy you will compare against, on each
   node. A shared inode is the trap, present:

   ```bash
   # any file that appears in both trees; repeat for a few shards
   stat -c '%i %n' \
     ~/models/<edited>/model-00001-of-000NN.safetensors \
     ~/models/<stock>/model-00001-of-000NN.safetensors
   # PASS: two different inode numbers. FAIL: the same number twice.

   # sweep the whole tree: any shard with link count > 1 is suspect
   find ~/models/<stock> -name '*.safetensors' -links +1 -printf '%n %p\n'
   # PASS: no output. FAIL: any line.
   ```

   Note the negative case explicitly: **no output from the `find` is a pass only
   if the `find` actually ran over a populated directory.** An empty or wrong
   path also prints nothing. Assert a non-zero shard count first, or this check
   is a vacuous PASS in the sense of CONTRIBUTING's shape 2.

2. **Fingerprint the reference before you publish against it.** Hash a fixed set
   of layer tensors in the stock copy at the *start* of a campaign and again at
   the end. Keys' recommendation is to fingerprint **L0, L9, L10, L20, L42 and the
   MTP heads** - chosen to straddle the edit window (an edit to layers 10-42 is
   invisible at L0/L9 and visible at L10/L20/L42, so the pair tells you both that
   the fingerprint works and whether stock moved).

   ```bash
   python3 - <<'PY'
   from safetensors import safe_open
   import hashlib, glob, sys, torch
   TARGETS = ("layers.0.", "layers.9.", "layers.10.", "layers.20.", "layers.42.", "mtp.")
   shards = sorted(glob.glob(sys.argv[1] + "/*.safetensors")) if len(sys.argv)>1 else []
   assert shards, "no shards found - this is a FAIL, not a pass"
   h = hashlib.sha256(); seen = 0
   for s in shards:
       with safe_open(s, framework="pt") as f:
           for k in sorted(f.keys()):
               if any(t in k for t in TARGETS):
                   # .view(torch.uint8), NOT .numpy(): numpy() raises TypeError on
                   # bf16 and fp8, which are exactly the dtypes this trap is about.
                   h.update(k.encode())
                   h.update(f.get_tensor(k).contiguous().view(torch.uint8).numpy().tobytes())
                   seen += 1
   assert seen, "matched zero tensors - this is a FAIL, not a pass"
   print(f"{seen} tensors  {h.hexdigest()}")
   PY
   ```

   The two `assert` lines are the point. A fingerprint over an empty tensor set
   is a stable hash of nothing, and it will match itself run after run while
   telling you nothing at all.

   **The dtype detail is not cosmetic.** The obvious way to write the hash
   update is `.cpu().numpy().tobytes()`, and it works on fp32 and fails on
   `bfloat16` and `float8_e4m3fn` with
   `TypeError: Got unsupported ScalarType`. Those are the dtypes an FP8 or
   quantized checkpoint is actually stored in, so the naive version crashes on
   precisely the models worth fingerprinting and passes on the toy tensor you
   test it with. `.contiguous().view(torch.uint8)` hashes the raw storage and
   works for every dtype.

   Verified on torch 2.12.1: fp32 `.numpy()` OK, bf16 and fp8 `.numpy()` raise
   `TypeError`, `.view(torch.uint8)` succeeds for all three.

**The fix.** Three, in order of how much they buy:

1. **Write temp-then-replace, never in place.** Serialize the edited shard to a
   new file in the destination directory and `os.replace()` it over the target.
   `replace` unlinks the old name; it does not write through the link, so a
   hardlinked twin elsewhere is untouched. Keys' `project_wob.py` does exactly
   this, and his stated rule is: **never `save_file` onto a hardlinked stock
   shard.**
2. **Break links at stage time.** Copy with `cp --reflink=never -L` (or download
   without cache-linking) when creating the edit source, so the destination never
   shares an inode with anything.
3. **Fingerprint and freeze.** Record the reference fingerprint, the runtime image
   digest, the serve script and the config as a frozen identity for the campaign,
   and re-verify the fingerprint before publishing. This is the control that
   catches the trap even when 1 and 2 were skipped by someone else.

Mount the reference copy read-only where the serving path can see it
(`-v $STOCK:/model:ro`) if you can. Note the limit honestly: `:ro` protects
against the *serving container* writing, not against an editing script run on the
host, which is where this trap actually bites.

**Found.** 2026-07-09 to 2026-07-26, in a weight-edit campaign on a dual DGX Spark
GB10 fleet; written up 2026-07-28.

**Attribution.** Keys ([@drowzeys](https://github.com/drowzeys)). Source:
[notes-for-DSV4F-DSpark-Abliteration](https://github.com/drowzeys/notes-for-DSV4F-DSpark-Abliteration),
`TECHNICAL_REPORT.md` section 2.3, section 3 (F5), section 3.2, section 9 lesson 5, at commit
`afd4137540ba5c4c2a1e96ecaf4200af74f8dfd8`. Repo is MIT. The underlying
campaign is a refusal-removal study; **that methodology is deliberately out of
scope for this registry and is not described here** - what is registry material
is the filesystem-and-measurement failure, which is independent of what the edit
was for.
