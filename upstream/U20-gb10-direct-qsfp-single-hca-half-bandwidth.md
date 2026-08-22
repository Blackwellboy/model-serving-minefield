# U20: a direct GB10 QSFP pair can use only one of two NICs and leave major bandwidth unused

**Reported by @Capicua25x.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The source maintainer reviewed the topology caveat and merged the documentation change.

**Issue state: closed, fixed.** PR #35 is merged.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #35](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/35), read on 2026-08-21.

**Symptom.** Two directly connected DGX Spark / GX10-class GB10 nodes appear correctly linked over QSFP, NCCL works, but node-to-node bus bandwidth sits around 98 Gb/s instead of using substantially more of the physical link.

**Mechanism.** On the reported GB10 pair, the QSFP port enumerated as two virtual NIC/controller paths. The stock/single-HCA configuration used only one. Configuring both interfaces with separate IP subnets, MTU 9000, both HCAs in `NCCL_IB_HCA`, and `NCCL_IB_MERGE_NICS=1` raised measured `nccl-tests` bus bandwidth from 98 to 161 Gb/s, a reported +64%.

This is deliberately scoped to **back-to-back direct QSFP pairs**. The source maintainer notes that a switched fabric may intentionally leave the second NIC unused, so a dark second interface is not itself evidence of a fault on every topology. The source also requires verifying the selected GID is RoCEv2 instead of copying a hard-coded index across hosts.

**What we have not done.** We have not reproduced 98 -> 161 Gb/s on Blackwellboy hardware and do not claim those exact numbers are universal. We also do not promote the adjacent pre-2026-04 BIOS Gen5-x2 note into this mechanism without a separate matched reproduction.

## If you have this stack

On a direct two-node QSFP pair, map every RDMA device to its netdev with `ibdev2netdev`, record link state and PCIe width, verify the intended GID type from sysfs, and run the same pinned `nccl-tests` case first with one HCA and then with both HCAs merged. Keep MTU, message sizes, NCCL version and CPU placement fixed.

**CONFIRM.** One-HCA mode is materially bandwidth-limited and the same pair gains substantial bus bandwidth when both GB10 interfaces are correctly addressed and merged, without changing the physical cable or benchmark.

**REFUTE.** The second interface is not part of the direct data path on the tested topology, both HCAs are already active, or one-HCA and merged-HCA arms measure the same bandwidth within noise.

## Attribution

Reported and measured by @Capicua25x; reviewed and merged by @tonyd2wild in PR #35. The registry has not independently reproduced the result.
