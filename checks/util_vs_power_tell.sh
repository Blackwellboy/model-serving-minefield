#!/usr/bin/env bash
# Trap 46 check: high GPU utilization at low power draw means you are on a fallback kernel.
#
# Run this WHILE a decode benchmark is in flight. Busy compute units that do not saturate
# tensor cores show up as ~98% utilization at ~47% TDP. After rebuilding against a branch
# tip that actually contains the arch-native kernel, the same workload ran 95% util at 80%
# TDP and 2.5x the throughput (16 to 40 tok/s on a 27B 4-bit model).
#
# Boards that do not report power.draw or power.limit (Jetson and GB10-class among them)
# emit [N/A]. An earlier version let awk coerce that to 0, which made every healthy lane on
# those boards read as SUSPECT FALLBACK. Unreadable power is now "inspected nothing"
# (exit 3), never a finding and never a pass.
#
# Usage:  bash util_vs_power_tell.sh [seconds] [gpu_index]
# Exit codes: 0 ran, nothing blocking. 1 target unreachable. 2 ran, blocking finding.
#             3 ran, but inspected nothing.

set -uo pipefail
SECS="${1:-30}"
GPU="${2:-0}"
OK=0; UNREACHABLE=1; BLOCKING=2; NOTHING_INSPECTED=3

command -v nvidia-smi >/dev/null 2>&1 || {
  echo "  nvidia-smi not found; cannot reach the target"; exit $UNREACHABLE; }

samples=$(nvidia-smi -i "$GPU" \
  --query-gpu=utilization.gpu,power.draw,power.limit \
  --format=csv,noheader,nounits -l 1 -c "$SECS" 2>/dev/null)

[ -n "$samples" ] || { echo "  no samples collected"; exit $UNREACHABLE; }

# Count only rows where BOTH power fields are numeric. [N/A], "N/A" and blanks do not count.
read -r n_ok mean_util mean_pw limit <<<"$(awk -F', *' '
  function num(x) { return (x ~ /^[0-9]+(\.[0-9]+)?$/) }
  { if (num($1) && num($2) && num($3) && $3 > 0) { u+=$1; p+=$2; l=$3; n++ } }
  END { if (n) printf "%d %.1f %.0f %.0f", n, u/n, p/n, l; else print "0 0 0 0" }
' <<<"$samples")"

total=$(wc -l <<<"$samples" | tr -d ' ')
echo "  samples with numeric power : ${n_ok} of ${total} over ${SECS}s on GPU ${GPU}"

if [ "$n_ok" -eq 0 ]; then
  cat <<'EOF'
  This board does not report power.draw or power.limit (Jetson and GB10-class do not).
  INSPECTED NOTHING: the utilization-versus-power tell cannot be evaluated here, and a
  clean verdict would be a false one. Use the ancestry check instead:

    git merge-base --is-ancestor <fix-commit> <running-HEAD> && echo present || echo STALE

  and read the server's startup system_info banner for the arch-native feature flag.
EOF
  exit $NOTHING_INSPECTED
fi

pct=$(awk -v p="$mean_pw" -v l="$limit" 'BEGIN{ printf "%.0f", 100*p/l }')
echo "  mean utilization           : ${mean_util}%"
echo "  mean power                 : ${mean_pw}W / ${limit}W (${pct}% TDP)"

hi_util=$(awk -v u="$mean_util" 'BEGIN{ print (u >= 90) ? 1 : 0 }')
lo_power=$(awk -v p="$pct"      'BEGIN{ print (p  <  60) ? 1 : 0 }')

if [ "$hi_util" = "1" ] && [ "$lo_power" = "1" ]; then
  cat <<'EOF'

  BLOCKING: high-util / low-power. SUSPECT FALLBACK KERNEL.

  Next, in this order:
    1. git merge-base --is-ancestor <fix-commit> <running-HEAD> && echo present || echo STALE
       (the fix is often already in the branch you track; production was never rebuilt)
    2. read the server's startup system_info banner for the arch-native feature flag.
       A flag you passed is not evidence; a banner the binary printed is.
    3. rebuild from the branch tip in an isolated `git worktree`, mirroring the prod cache.

  On cutover: SIGTERM can leave the old server in D state still holding VRAM. Use kill -9.
EOF
  exit $BLOCKING
fi

if [ "$hi_util" = "1" ]; then
  echo
  echo "  ok: high utilization with healthy power draw, kernel path looks real."
  exit $OK
fi

echo
echo "  INSPECTED NOTHING: utilization below 90%, so the tell does not apply. The"
echo "  bottleneck is probably elsewhere (queueing behind other requests, host-side,"
echo "  or client-side). This is not a clean bill for the kernel path."
exit $NOTHING_INSPECTED
