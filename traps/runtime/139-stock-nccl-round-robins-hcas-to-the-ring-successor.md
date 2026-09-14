# Trap 139: stock NCCL can select the wrong HCA for a peer on a switchless multi-NIC cycle

**Found by @btcxoomer. Independent public implementation and qualification evidence by Alex Ellis (@alexellisuk).**

**Status: contributor-measured, conditions as reported.** The exact 3-node failure was measured by @btcxoomer on a three-node DGX Spark / GB10 switchless triangle on 2026-09-05. Alex Ellis independently published and qualified a four-node switchless NCCL implementation in [`alexellis/switchless-nccl`](https://github.com/alexellis/switchless-nccl). Alex's work supports the same broader direct-cable topology class; it is not presented as an independent reproduction of the contributor's exact 3-node channel map.

**Symptom.** A tensor-parallel bring-up on a switchless topology can fail during NCCL transport setup even though the destination peer is directly connected and the physical links are healthy. In the contributor's 3-node triangle, the debug channel map showed traffic for one peer assigned to the interface physically cabled to the other peer. The resulting peer/interface pairing had no physical path and the collective timed out.

The same contributor failure reproduced on two independent surfaces in the same pinned image: the real serving bring-up and a minimal `torch.distributed` collective. That is strong evidence that the failure was below the serving engine rather than a vLLM-only fault.

**Mechanism.** The reported stock lane selected HCAs as if all selected interfaces could reach the ring successor. That assumption is harmless on a switched fabric where either interface can reach the peer, but it is false on a direct-cable cycle where each interface reaches only its cabled neighbour. The decisive diagnostic is therefore not link state alone: it is whether each selected peer/device pair corresponds to a physically reachable leg.

Alex Ellis's public four-node repository independently documents the adjacent topology problem. On a four-node direct-cable cycle, stock NCCL can attempt Tree/PAT relationships between ranks that are not directly cabled. His source-pinned implementation constrains the topology to a qualified Ring path, uses subnet-aware peer/interface selection, verifies the selected fabric identities, and proves which NCCL library each process loaded. This corroborates the switchless topology class without collapsing the two distinct evidence surfaces into one mechanism claim.

**Stacks and builds bitten.** The exact 3-node report came from a DGX Spark / GB10 switchless triangle using the stock NCCL carried by the contributor's pinned serving image. The exact stock NCCL version string was not preserved before replacement, so this entry does not generalize the failure to every NCCL release.

Alex Ellis's independently published implementation is source-pinned to NVIDIA NCCL `v2.30.7-1` at commit `73cf112295c33aee2b895f329f592f2a9b4b0f97`; his canonical switchless release is `v0.0.1` and publishes source/binary provenance in the repository.

**The check.** Before serving on a switchless multi-NIC cycle, run a value-checked multi-rank collective inside the exact runtime image with NCCL debug logging enabled. For every rank-to-peer relationship, map the selected network device to the physical neighbour that device can actually reach.

**TRAP PRESENT:** a peer is assigned to an interface physically cabled to a different neighbour and the collective fails during transport setup.

**TRAP ABSENT:** every selected peer/device relationship follows a physically reachable leg and the value-checked collective completes.

Do not use link-up alone, process liveness, or a green API health endpoint as proof that the collective path is correct.

**The fix.** Use a NCCL path explicitly qualified for the direct-cable topology and prove that every rank process loads the same pinned library. Alex's public four-node runtime contract is a concrete reference: Ring-only switchless operation, subnet-aware routing, no NIC merging, explicit RoCE/GID validation, and in-process library-identity verification.

Do **not** blindly hard-code `NCCL_IB_GID_INDEX=3` as a portable fix. GID tables are per-host and can change when stale addresses are present. On modern NCCL, prefer dynamic selection of the intended IPv4 RoCEv2 entry and verify the result on every relevant port. If a legacy deployment must pin an index, verify that exact index independently on every host/interface first. This is the same portability class documented in Trap 114.

**Fix/pin closure.** For @btcxoomer's exact 3-node lane, `BROKEN_PIN=UNKNOWN` because the original stock NCCL build identity was not captured before replacement. `REPRO_BEFORE=PASS` on both the serving path and the minimal collective. The working replacement used a topology-aware NCCL 2.30.7-based path, but the exact final 3-node binary identity was not preserved, so `KNOWN_GOOD_PIN=UNKNOWN` for that contributor lane.

Separately, Alex Ellis publishes a tested four-node switchless known-good implementation at `alexellis/switchless-nccl` release `v0.0.1`, with the upstream source pin, patch provenance, binary hashes, a four-rank value-checked collective qualification, and a matched serving qualification. That is independent known-good evidence for the four-node solution class; it is not substituted as the closing pin for the different 3-node contributor lane.

**Claim boundary.** May claim: on the contributor's reported lane, wrong HCA selection made a healthy switchless triangle fail during NCCL transport setup; the peer/device channel map is the decisive diagnostic; and a topology-aware switchless NCCL path fixed the reported lane. May also claim that Alex Ellis independently published and qualified a source-pinned four-node switchless NCCL implementation. Must not claim that every stock NCCL version has the exact same 3-node selection behavior, that Alex independently reproduced @btcxoomer's exact channel map, or that one numeric GID index is portable across hosts.

**Found.** 2026-09-05 by @btcxoomer during a 3-node DGX Spark TP=3 bring-up.

**Attribution.** Original 3-node finding, diagnosis, and contributor reproduction: **@btcxoomer**. Independent public source-pinned switchless implementation, hardening, runtime contract, and four-node qualification evidence: **Alex Ellis (@alexellisuk), OpenFaaS Ltd**, [`alexellis/switchless-nccl`](https://github.com/alexellis/switchless-nccl). Alex's repository preserves the upstream SparkRing, NVIDIA, and Joseph Rose provenance on which his implementation builds.

**Related.** [Trap 114](114-hardcoded-rdma-gid-index-is-not-portable.md) for GID-index portability, [Trap 134](../evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md) for link-up versus path proof, and [U20](../../upstream/U20-gb10-direct-qsfp-single-hca-half-bandwidth.md) for the GB10 direct-link bandwidth side of the fabric story.
