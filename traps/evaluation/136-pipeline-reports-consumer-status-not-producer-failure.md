# Trap 136: a log-trimming pipeline can report success after the probe crashed

**Found by vcruz305 (Victor Cruz).**

**Status: contributor-measured, conditions as reported.** A shell wrapper around
a Python model-serving probe printed a traceback from the producer and then
reported `rc=0`. The contributor reproduced the status mismatch directly. The
registry has not independently reproduced the original campaign.

**Symptom.** A probe prints an obvious exception, but the wrapper, orchestration
receipt, or agent summary records success. In the measured case the producer
raised `FileNotFoundError`; the last stage still completed normally, so the
wrapper printed `rc=0` and the run was initially treated as green.

**Mechanism.** In a shell pipeline such as:

```bash
python probe.py 2>&1 | tail -20
echo "rc=$?"
```

the default pipeline status is the exit status of `tail`, not `python`.
`tail` can successfully consume and print a traceback, return zero, and erase
the producer's failure from the machine-readable verdict. A remote wrapper can
then faithfully propagate the already-wrong zero.

This is loss of process identity at the measurement boundary: the recorded
status belongs to the log consumer while the claimed status belongs to the
probe.

**Stacks and builds bitten.** Contributor-measured with Bash wrapping a Python
probe during a DGX Spark / GB10 serving-kernel investigation. The mechanism is
shell-generic and applies to any benchmark, readiness probe, profiler, or
remote executor that pipes the command under test through `tail`, `tee`,
`grep`, or another successful consumer without preserving producer status.

**The check.** Use a deliberately failing producer as a negative control before
trusting the wrapper:

```bash
set -o pipefail
python -c 'raise SystemExit(23)' 2>&1 | tail -20
test "$?" -eq 23
```

For wrappers that must support shells without `pipefail`, capture the producer
status explicitly (`PIPESTATUS[0]` in Bash) before running any later command.
Also require the receipt to name the stage whose status it records.

**The fix.** Enable `pipefail` before the command-under-test pipeline, or avoid
putting presentation filters in the verdict path. Capture and propagate the
producer status immediately. Keep log trimming as a separate display step, and
make the negative control above part of the wrapper test suite.

**Found.** 2026-09-02, while validating a model-serving kernel probe through a
remote shell wrapper.

**Attribution.** **Victor Cruz / @vcruz305** - finder and contributor
measurement.

**Related.** [115](115-exit-137-is-not-oom-killer-proof.md) (an exit value does
not prove its assumed cause), [112](../runtime/112-process-liveness-is-not-model-readiness.md)
(a green outer signal is not model readiness), [52](52-speed-measured-on-a-broken-config.md)
(a result can look valid while the measured path is invalid).
