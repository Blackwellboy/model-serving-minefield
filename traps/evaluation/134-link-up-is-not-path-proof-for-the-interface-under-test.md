# Trap 134: link-up is not path proof for the interface under test

**Found by Blackwellboy.**

**Status: measured here, raw not published.** First-party multi-homed transport
benchmark campaign on ordinary Ethernet plus a second wireless path. Hostnames,
addresses, and switch model are scrubbed. Raw counter dumps stay private; the
check below is the stranger-reproducible half.

**Symptom.** An Ethernet/NIC/interface reports **link UP** at a plausible
negotiated speed, so the operator concludes "the test is wired" or "this
transport used interface X." The labelled transport arm then produces a clean
tok/s table. Later path forensics show the workload never used that interface:
routes and packet counters belong to another path (commonly wireless fallback
or a default route), while the intended interface stays healthy and mostly
idle. The benchmark looks valid while measuring a different transport than the
label says.

**Mechanism.** Four claims are routinely collapsed into one:

1. **physical link state** (carrier / negotiated speed),
2. **addressing / L2 membership** (usable address on the intended subnet or VLAN),
3. **route selection** (which interface the kernel chooses for the peer),
4. **actual packet path** (TX/RX counters and peer-side evidence during the run).

They are independent. An interface can be UP, full-duplex, and idle while
fallback or default routing carries the workload elsewhere. A successful ping
is not enough: ICMP can succeed on a path that is not the path your serving
benchmark later used, or can succeed while you still mis-label which interface
carried the bytes.

**Measured evidence (sanitized).** On one multi-homed portable-serving A/B:

- intended Ethernet reported **link UP at 1 Gb**,
- that interface initially held only **link-local** addressing,
- the route to the workload peer selected the **alternate wireless** interface,
- wireless counters moved during traffic; the intended Ethernet interface did
  **not** materially carry the workload,
- after correct fabric addressing on the intended interface, route / neighbour /
  counter evidence moved onto Ethernet,
- **no cable move and no switch mutation** were required once addressing was
  correct.

That sequence is the measurement error this entry records. It is not a claim
about any particular switch port class.

**Stacks and builds bitten.** Any multi-homed host running a transport-labelled
serving or collectives benchmark (Ethernet + Wi-Fi, multiple NICs, VPN/overlay
beside physical, dual-stack clients). Engine- and model-independent: the defect
is path attribution, not weights.

**The check.** Before recording any transport-labelled performance result,
require path proof against the **actual benchmark peer**, not a generic
gateway:

1. **Route lookup** to the peer: which interface / gateway is selected.
2. **Source / interface bind** where the OS supports it: bind to the intended
   address and show success; bind to the wrong source and show failure or a
   different path rather than silent fallback.
3. **ARP / neighbour** evidence where applicable.
4. **Before/after TX/RX counter deltas** on the intended interface during a
   known traffic burst.
5. **Peer-side counter or path evidence** when available.
6. **Negative / discriminator:** intentionally remove or mis-bind the intended
   path and prove the result changes or fails rather than silently continuing
   on the alternate path.

A green ping alone is insufficient. Preserve `path_class`, `local_interface`,
peer path, route proof, counter proof, and fallback state beside every
transport-labelled number.

**The fix.** Treat link-up as a necessary but non-sufficient preflight. Do not
publish "wired", "Ethernet", "RDMA", or "Flash vs TCP on fabric X" results
until the path-proof checklist above is green for that run. If proof is
missing, the allowed claim is end-to-end composite throughput on an unknown or
mixed path - not a transport win.

Offline metadata that compares two arms without contacting endpoints can use
[`checks/benchmark_attribution_preflight.py`](../../checks/benchmark_attribution_preflight.py)
to refuse a `TRANSPORT` claim when `path_proof` is absent. That checker audits
claim defensibility; it does not replace live route/counter forensics.

**Claim boundary.**

- May claim: link-up / negotiated speed is not proof that the labelled
  interface carried the benchmark; missing path proof can make a transport
  A/B measure the wrong path.
- Must **not** claim from this entry alone: transport protocol failure, switch
  failure, RDMA failure, GPUDirect failure, or that Ethernet is inherently
  slower or faster than another medium.
- Path proof on one session does **not** license a cross-session performance
  comparison when the remote host, engine revision, or other serving identity
  also changed. Those pairs stay end-to-end composite until the lower layers
  are held.

**If you miss it.** You optimise or blame a transport that never carried the
bytes, promote a "wired" win that was still wireless, or conclude the fabric is
broken when only addressing/path selection was wrong.

**Related.**
[Trap 48](../routing/48-dual-stack-mdns-latency-tax.md) (client chose a dead
address family),
[trap 53](../runtime/53-config-edit-never-took-effect.md) (surface said success;
live path did not change),
[trap 112](../runtime/112-process-liveness-is-not-model-readiness.md) (lower
gate green ≠ claimed capability),
[trap 114](../runtime/114-hardcoded-rdma-gid-index-is-not-portable.md) (fabric
env identity ≠ portable path). None of those owns multi-homed **interface
selection** for a labelled transport benchmark.


### Addendum - 2026-08-25: controlled path-only delta can be TRANSPORT

**Status for this addendum: measured here, raw not published** (Blackwellboy).
Entry status is unchanged. Raw counter dumps and fleet identity stay private.

Trap 134 is not only a warning that link-up is insufficient. It also sets the
**positive** standard: when model, serving recipe, endpoint identity, and code
revision are held, and route / interface / counter path proof is present for
each arm, a path-only delta may be labelled **`TRANSPORT`**.

A later controlled portable-serving A/B held:

- same client host
- same Spark endpoint
- same FlashRDMA pin `1e952ace4be94f90b88b850188e99f0493036424`
- same Qwen2-0.5B split serving recipe and W16
- same sampling / output budget
- tokenizer-verified fixtures (4K = 4019, 8K = 8004)

and changed **network path only** (dedicated 1 GbE copper vs the existing
Wi-Fi/LAN route), with path proof on both arms. Offline
[`checks/benchmark_attribution_preflight.py`](../../checks/benchmark_attribution_preflight.py)
returned `max_defensible_claim=TRANSPORT` (MODEL and SERVING_ENGINE held;
transport intended; `path_proof` PRESENT; correctness PASS).

Sanitized medians (tok/s):

| Depth | Path | TCP | Flash |
|---|---|---:|---:|
| 4K | wired | 15.724 | 15.832 |
| 4K | Wi-Fi | 9.943 | 8.164 |
| 8K | wired | 9.871 | 7.817 |
| 8K | Wi-Fi | 6.401 | 4.862 |

Wired was roughly **1.5-1.9x** Wi-Fi on this held pair. Independent raw path
baselines on the same hosts were ~940 Mbps / RTT p50 ~0.95 ms (wired) versus
~166-170 Mbps / RTT p50 ~15 ms, p95 ~109 ms (Wi-Fi).

**Claim boundary for this addendum.** May claim: with holds + path proof, a
path-only comparison can be `TRANSPORT`. Must **not** claim from these numbers
alone that Ethernet is universally 1.5-1.9x faster than Wi-Fi, that FlashRDMA
caused the gain, native RoCE, GPUDirect, or any result beyond this measured
setup. Cross-session Wi-Fi→wired tables that also change endpoint or revision
remain **`END_TO_END_COMPOSITE_ONLY`** (see the entry claim boundary above and
[the A/B playbook §11](../../playbooks/before-you-publish-an-ab.md)).

**Found.** 2026-08-25, multi-homed portable serving transport A/B with path
forensics before and after addressing correction.

**Attribution.** Blackwellboy.
