# Trap 54: the restart reported success, the old process kept the port, and your config edit never took effect

**Found by TheTom.**

**Status: reproduced here** (two restart cycles, service manager reporting success both times, with
the old process still serving; logs held outside the tree and can be produced on request, per the
default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo)).

**Symptom.** You change a serving flag, restart, and re-test. The behavior you were trying to fix is
still there. Every reasonable next step is a dead end: is the flag spelled right, is it the right
config file, does this build even support it, is the model ignoring it. All dead ends, because the
flag is fine and the server never restarted.

Our version: two config edits made, only the **first** ever took effect. The second (a
reasoning-off flag) sat on disk being ignored while we concluded the flag did not work on that
build.

**Mechanism.** A long-lived process the service manager had lost track of kept holding the port. The
restart commands returned `SUCCESS` both times. Meanwhile the newly-launched instance crash-looped
every ~3 seconds on `bind: address already in use`, which is only visible in the log file nobody was
tailing, and the stale process kept serving the older config perfectly happily.

Two independent failure modes combine here:

1. **A restart command that reports on the *command*, not on the *process*.** Exit code 0 means "I
   sent the signal", not "the old server died and the new one bound the port."
2. **A crash-loop that looks like silence.** The replacement writes its failure to a file and dies;
   the client never notices because a healthy-looking server is still answering.

The related trap on the other side of the same problem: a graceful signal can leave a GPU process in
uninterruptible sleep still holding VRAM for seconds, so the replacement cannot allocate even when
the old one *is* dying (see [trap 47](../versioning/47-stale-build-missing-arch-kernel.md)).

**Stacks and builds bitten.** A model-swapping router under a Windows Scheduled Task on WSL2 in our
case, but the shape is generic: systemd units, launchd jobs, Docker restart policies, and process
managers all report on the action rather than the outcome. Any stack where "restart" and "the thing
that answers requests" are two different objects.

**The check.** After every restart, prove three things about the **process that is answering**, not
about the command you ran:

```bash
# 1. what is actually holding the port, and when did it start?
lsof -nP -iTCP:8080 -sTCP:LISTEN        # or: fuser -v 8080/tcp ; ss -lptn 'sport = :8080'
ps -o pid,lstart,etime,cmd -p <pid>     # start time OLDER than your edit == it never restarted

# 2. did the replacement fail to bind?
grep -i 'address already in use' server.log | tail

# 3. does the LIVE server report the setting you changed?
curl -s localhost:8080/v1/models
grep -iE 'chat template|thinking|system_info|n_parallel|n_ctx' server.log | tail -20
```

The process start time is the single highest-value line. If it predates your edit, nothing else you
are about to debug matters.

**The fix.** Make restarts prove themselves:

- Kill **by port**, not by process-name substring. `fuser -k 8080/tcp`. A name-substring kill can
  match the wrong process, and `pkill -f <pattern>` run over SSH matches its own command line and
  kills the calling shell (the pattern string is in your own argv). Use `pkill -x <exact-name>` if
  you must kill by name.
- After the kill, **assert the port is free** before starting the replacement, and assert the new
  PID is listening afterwards.
- Have the server print the settings you care about at startup and grep for them post-restart. A
  banner the binary printed is evidence; a flag you passed is not.

**Generalizes to a rule.** Before attributing a behavior to a model, prove the process serving you
was started **after** your last config change. This one masquerades as a model finding, a template
bug, and an unsupported-flag report simultaneously, and it wastes the debugging effort of all three.

**Found.** 2026-06-23, while chasing why a reasoning-off flag "did not work" on one build.

**Attribution.** TheTom.

