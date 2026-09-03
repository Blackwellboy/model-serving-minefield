# Trap 137: a nonzero kernel selector return is not a process failure

**Found by vcruz305 (Victor Cruz).**

**Status: contributor-measured, conditions as reported.** Cruz measured correct,
finite output from several EXL3 extension calls whose integer returns were
nonzero. Independent agents repeatedly classified those calls as failures by
applying process-exit semantics to the extension API. The registry has not
independently reproduced the extension behavior.

**Symptom.** A kernel probe produces numerically correct output, but the harness
marks the call failed because its integer return is not zero. In the measured
lane, returns including `3`, `4`, and `90` accompanied successful calls; `90`
selected a small-matrix vector path, while the smaller integers identified
tiled kernel variants.

**Mechanism.** A native extension's integer return is part of that function's
API contract. It may identify a selected algorithm, launch shape, or dispatch
route. It is not automatically a Unix process exit status or C-style
zero-success error code. The harness imposed an invented `rc == 0` contract and
overrode stronger evidence: the call completed, wrote finite output, and
matched the reference within the test tolerance.

**Stacks and builds bitten.** Contributor-measured on NVIDIA DGX Spark (GB10)
with exllamav3 1.4.5's EXL3 GEMM extension and synthetic kernel-test inputs.
The general mechanism applies to any Python/C++/CUDA extension whose return
value encodes dispatch metadata rather than success/failure.

**The check.** Before interpreting an extension return, bind the verdict to the
pinned function contract and validate the output independently:

1. inspect the exact installed wrapper/source or documented binding for the
   return-value meaning;
2. assert the call wrote an output of the expected shape and dtype;
3. reject non-finite values;
4. compare against an independent reference with a preregistered tolerance;
5. run a negative control that corrupts or suppresses the output and confirm
   the correctness gate fails even if the selector value looks familiar.

Record the field as `dispatch_id`, `kernel_variant`, or the contract's real
name, not a generic `rc`. If the contract is unavailable, the verdict is
unknown, not failure and not success.

**The fix.** Remove the invented `return == 0` gate. Decode only values defined
by the pinned extension contract, and make output parity plus finite/shape
checks the correctness gate. Fail closed when the installed build's semantics
cannot be established.

**Found.** 2026-09-02, during independent verification of EXL3 GEMM probes on a
DGX Spark.

**Attribution.** **Victor Cruz / @vcruz305** - finder and contributor
measurement.

**Related.** [76](../runtime/76-device-rejection-log-line-is-not-fatal.md)
(an alarming signal can describe a rejected route rather than the final
verdict), [115](115-exit-137-is-not-oom-killer-proof.md) (do not infer cause
from an exit value), [52](52-speed-measured-on-a-broken-config.md) (correctness
must gate performance claims).
