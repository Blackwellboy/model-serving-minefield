# Trap 104: stale launch script silently reverts hardened config on restart

**Found by Nemo (@NemoSMF).**

**Status: contributor-measured, conditions as reported** (discovered during
config audit on DGX Spark; the pattern is generalizable to any multi-path
deployment).

**Symptom.** A serve is running with the correct, hardened configuration —
revision pinned, thinking off, token cap set, conservative `max-num-seqs`. You
restart it (manually, or after a reboot, or via a different startup path) and
the model behaves differently: thinking turns on, no token cap, a different
`max-num-seqs`. The systemd unit is correct, but the standalone launch script
and the operator docs still carry the old config. The restart reports success,
and nothing in the logs says "I am using a different configuration than last
time."

**Mechanism.** When a serve is hardened, the running process is updated first
(typically via systemd or a direct command). But the **surrounding artifacts** —
standalone launch scripts, operator docs, environment files, and README
instructions — may not be updated. A restart from any of these paths silently
reverts to the pre-hardening config. The model is not broken; the configuration
infrastructure is inconsistent. This is especially dangerous when the hardening
was done in response to a silent upstream config change (e.g., a revision that
flipped a default), because the stale script will pick up the new, unhardened
default on the next `git pull` or model update.

This is the mirror image of trap 53 ("config edit never took effect" — a stale
process kept the port). Here, the stale artifact is the launch script, and the
new config never made it to all the startup paths.

**Stacks and builds bitten.** vLLM 0.25.1, `poolside/Laguna-S-2.1-NVFP4`,
DGX Spark GB10. The systemd unit was updated with `--revision b482b5d`,
`--override-generation-config '{"enable_thinking":false,"max_tokens":16384}'`,
and `--max-num-seqs 4`. The standalone launch script (`launch-laguna.sh`) and
the operator docs (`LAGUNA-S-2.1-NVFP4.md`) still carried the original
card-recommended config: no revision pin, no token cap, `max-num-seqs 32`,
thinking on-by-default. A restart from the stale script would have silently
reverted all four hardening measures.

**The check.** After hardening a serve, verify that **every** path that can
start it carries the same config:

```bash
# 1. Check the running process
pgrep -af 'vllm serve' | grep -oP '\-\-(revision|override-generation-config|max-num-seqs)\s+\S+'

# 2. Check every launch script
for script in ~/launch-*.sh /etc/systemd/system/*vllm*; do
    echo "=== $script ==="
    grep -oP '\-\-(revision|override-generation-config|max-num-seqs)\s+\S+' "$script" 2>/dev/null || echo "(no vllm flags found)"
done

# 3. Diff: if the running process shows flags that a launch script does not,
#    that script will silently revert them on restart.
#    Every flag in the running process must appear in every launch script.
```

**The fix.** After hardening, update **all** startup paths, not just the one
currently in use:
1. The systemd unit (if using systemd)
2. The standalone launch script (for manual restarts)
3. The operator docs / README
4. Any environment files that set defaults
5. The memory or config notes that operators reference

The principle: if a flag is worth setting, it is worth setting in every path
that can start the serve. A config that lives in only one of five places is a
config that will be silently lost on the next restart from one of the other four.

**Found.** 2026-07-26, during a config audit after applying the offlabel
behavioral guide. The running process was correct; four other artifacts were
stale.

**Attribution.** Nemo (@NemoSMF). The audit and five-file update are documented
in the
[SMF Clearinghouse blog post on offlabel integration](https://www.smfclearinghouse.com/blog/2026-07-26-laguna-s-2-1-offlabel-integration).