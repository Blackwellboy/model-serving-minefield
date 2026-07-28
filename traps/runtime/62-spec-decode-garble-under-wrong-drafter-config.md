# Trap 62: token garbling from a speculative-decode drafter configuration

**Found by Blackwellboy.**

**Status: reproduced here** for the fixed configuration and the check below
(both re-read from the running container and exercised again on 2026-07-28),
and **measured here, raw not published** for the failure mode itself, which was
observed once and recorded in an internal note a stranger cannot open. The
confidence is split deliberately, three ways, and the third part is not a status
because it is not a claim:

- **The fix: reproduced here.** The fixed configuration is the one this lane
  has served on continuously since 2026-07-22. It was re-read from the running
  container on 2026-07-28 and exercised again in that session across roughly
  eighty generations with no malformed markup in any raw response body.
- **The failure mode: measured here, raw not published.** The garbling was
  observed once, on this lane, on 2026-07-22, and is recorded in our own
  operational note from that day with the corrupted frame quoted verbatim. That
  note is internal, so a stranger cannot check it. It was deliberately not
  reproduced for this entry: the lane is production and the pre-change
  container is a rollback anchor, not a test bed.
- **Causal attribution: NOT established.** The fix landed as five simultaneous
  changes. No single-variable ablation was run, so this entry does not claim to
  know which one stopped the garbling.

**Symptom.** A speculative-decode lane returns text that is mostly fine and
then emits a corrupted special-token frame into visible content. The recorded
instance leaked a mangled tool-markup close tag into the user-facing string: a
tag whose token sequence had decayed into a fragment that is not any real token
of the dialect. The request is HTTP 200, finish_reason is normal, and nothing
is logged as an error. It reads like a model quality problem and it is not one.

**Mechanism (as understood, not as proven here).** Speculative decoding
proposes several tokens per step and then verifies them. If the drafter runs
with a sampling method the verifier does not expect, tokens can be accepted
that the target model would not have produced. On multi-token special-token
sequences the visible result is a partially correct tag: the leading tokens are
accepted, the remainder come from the drafter, and the decoded string is a tag
that does not exist. That is why the corruption appears preferentially on
markup and tool frames rather than ordinary prose, and why it is easy to
misread as the model inventing a tag.

Our operational note attributes the root cause to a known greedy-drafter
garbling issue in this serving stack, fixed upstream by the stack's maintainer
on 2026-07-03; this deployment's pin predated that fix. That attribution is
**community-reported and inherited**, not independently confirmed by us.

**What actually differed, broken versus fixed.** Taken from `docker inspect` of
both containers, not from documentation. The rollback container ran from
2026-07-12T18:37Z to 2026-07-22T10:09Z; the current container has run since
2026-07-22T10:09Z. Same image, same weights, same node pair.

| | broken (rollback anchor) | fixed (live) |
|---|---|---|
| `num_speculative_tokens` | 5 | 3 |
| `draft_sample_method` | absent (stack default) | `probabilistic` |
| `--max-cudagraph-capture-size` | absent | 4 |
| `VLLM_USE_FLASHINFER_SAMPLER` | unset | 1 |
| drafter source file | the image's own | host file bind-mounted read-only over it |

Everything else in the two launch lines is byte-identical, including
`--kv-cache-dtype nvfp4_ds_mla`, `--block-size 256`, `--max-model-len 1048576`,
`--max-num-seqs 4`, `--gpu-memory-utilization 0.85`, tensor parallel 2 across
two nodes, and the generation-config override. The two container environments
differ by exactly one variable, confirmed by diffing both in full.

**A distinction worth keeping.** The bind-mounted drafter file is often
described as part of "the garble fix". Reading it against the stack's own
original shows it is not. The only functional change is a guard that detects a
non-uniform flattened batch, meaning a mixed prefill/decode step whose
per-request rows are unequal, and skips speculation for that step instead of
raising and killing the worker. Its own comment calls it a
concurrency-greater-than-one fix. That is a **crash** guard, not a garbling
guard. It was bundled into the same maintenance window. Treat the two as
separate changes that happen to share a date.

**Stacks and builds bitten.** A vLLM `0.21.1rc1.dev339+g1967a5627bc3` build
serving a community-abliterated DeepSeek-V4-Flash checkpoint (FP8 weight-block
quantisation, NVFP4 MLA KV cache) on two DGX Spark GB10 nodes, tensor parallel
2, arm64 with CUDA 13. Scope this narrowly. The drafter here is the model's own
multi-token-prediction head, and the interaction is with that drafter and that
sampler path. It is not a claim about speculative decoding generally, and it is
not a claim about stock DeepSeek V4-Flash.

**The check a stranger can run.** You do not need to reproduce the failure.

1. Read the engine's own startup line and confirm what the drafter is actually
   configured as, rather than what the launcher intended. The engine logs a
   speculative-config summary at init. Confirm the token count, and separately
   confirm that a draft sampling method is set at all. An absent method is the
   risky state, not a wrong one.
2. Confirm the sampler backend variable is set in the **container's**
   environment, not in the shell that launched it. These differ more often than
   people expect.
3. Behavioural and non-destructive: send thirty or so generations that force
   the model through its markup dialect (tool calls, structured output) and
   scan the **raw** response bodies, before any client-side parsing, for
   fragments of special-token syntax that are not complete valid tokens.
   Well-formed markup is fine; truncated or spliced markup is the signature.
   Parsing first will hide exactly the evidence you need, because a tolerant
   parser discards the malformed fragment.

**The fix.** If your lane shows the signature, the configuration this lane runs
is a known-good point in the space: drafter depth 3, an explicit probabilistic
draft sampling method, the FlashInfer sampler backend on, and the cudagraph
capture size pinned to the lane's max sequence count. Change them together or
ablate them one at a time deliberately. Do not assume the depth reduction alone
is the fix, because nobody has demonstrated that. Keep the pre-change container
as a rollback anchor rather than deleting it; that is what made this entry's
forensics possible five days later.

**Related.** [Trap 11](11-speculative-depth-peak-and-collapse.md) covers
acceptance collapsing past the drafter's trained depth, the performance-shaped
version of the same "depth is not free" problem.
[Trap 28](28-mtp-fails-only-under-concurrency-or-temperature.md) covers
speculative paths that pass a bench and fail in production; the bind-mounted
batch guard described above is an independent instance of exactly that class on
this lane, and is evidence for it.

**Found.** Failure 2026-07-22 on the live lane; configuration forensics and
this entry 2026-07-28.

**Attribution.** Failure mode and upstream root-cause attribution:
community-reported by the serving stack's maintainer, inherited via our
2026-07-22 operational note. Configuration forensics, the broken-versus-fixed
table, the drafter-guard distinction and the check: Blackwellboy.

## Added 2026-07-28: full CUDA graphs wedge decode on this hardware

**Found by [@drowzeys](https://github.com/drowzeys) (Keys)**, shared from his public notes at [notes-for-DSV4F-DSpark-Abliteration](https://github.com/drowzeys/notes-for-DSV4F-DSpark-Abliteration). **Status: reported by others.** Not reproduced here, and not measured here either: this is a credited
report from a stack we do not run, recorded because it sits on the same
drafter-and-graph-capture surface this entry is about.

On a dual DGX Spark (GB10, sm_121a) serving DeepSeek-V4-Flash under vLLM, Keys
reports that enabling **full CUDA graphs** wedges decode. His working
configuration disables them, and his notes treat that as a required setting
rather than a tuning preference.

Why it belongs here rather than as its own entry: this entry is already about a
speculative-decode configuration that produces broken output rather than an
error, and graph capture interacts with the drafter directly. Two configuration
surfaces, one symptom class, and neither announces itself.

**What this does NOT establish.** We have not reproduced it, we have not
isolated it from the rest of his serve line, and no causal attribution is
claimed. If you are debugging garbled or wedged decode on a speculative lane,
add "are full CUDA graphs on" to the list of things to vary, one at a time.
