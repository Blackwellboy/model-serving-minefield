# Trap 160: a TP=2 serve can pass bring-up, then rank-diverge around a collective only under sustained load

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #89](https://github.com/Blackwellboy/model-serving-minefield/issues/89)).

**Symptom.** A two-node tensor-parallel serve starts cleanly, survives light traffic, then dies roughly 15 to 25 minutes into sustained agentic load. The head reports shared-memory broadcast stalls, `sample_tokens` RPC timeout and `EngineDeadError`, while memory pressure and RDMA error counters remain clean.

**Mechanism.** Two time-separated stack captures on both ranks showed a true rank divergence: one rank remained inside `ncclAllGather` while the peer stayed in the local operation immediately before that collective and never entered it. Which physical box became the collective-stuck rank swapped across reproductions, ruling out a fixed host/NIC/rank explanation. The measured discriminator was the whole serving build: the vLLM 0.26 lane failed four of four sustained runs, while a v0.28.0-aarch64 lane survived two matched 85+ minute runs without the stall signature.

The exact bundled component that removes the failure is **not resolved**. The upgrade also changed NCCL (reported 2.28.9 to 2.29.7) and FlashInfer, and a related upstream GB10 report later demonstrated that even identical NCCL version strings can hide different binaries. Therefore this trap does not claim that vLLM core, NCCL, FlashInfer, or one flag is the proven root cause.

**Stacks and builds bitten.** Contributor-measured on two DGX Spark / GB10 nodes, vLLM TP=2 over QSFP/RDMA, large MoE workload, old v0.26 build versus newer v0.28.0-aarch64 build. Three plausible controls did not rescue the old lane: `NCCL_CUMEM_ENABLE=0`, prefix caching off, and FlashInfer autotune off.

**The check.** At the first sustained-load stall, capture stacks on **both** ranks twice, separated by roughly 45 to 60 seconds. Preserve the actually loaded `libnccl.so` identity from each live process (for example from `/proc/<pid>/maps` plus build ID/hash), plus vLLM and FlashInfer identities. A single stack shows only where a rank was; two frame-identical captures prove it stayed there.

**The fix.** On a lane matching this signature, stop treating generic NCCL flags as the only lever. Move to a known-good whole runtime build and re-run the same sustained workload. Record the complete before/after runtime binary identities before attributing the fix to one bundled component.

**Boundary.** This is distinct from startup NCCL hangs and from failures where every rank enters the same collective. It also does not imply TP=2 on GB10 is generally unstable. The canonical claim is the measured sustained rank-divergence signature and the old-build/new-build outcome split; subcomponent ownership remains unresolved.

**Found.** 2026-09, sustained two-node TP testing.

**Attribution.** @scottleimroth.
