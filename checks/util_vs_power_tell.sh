#!/usr/bin/env bash
# Trap 47 check, high GPU utilization at low power draw means you are on a fallback kernel.
#
# Run this WHILE a decode benchmark is in flight. Busy compute units that do not saturate
# tensor cores show up as ~98% utilization at ~47% TDP. After rebuilding against a branch tip
# that actually contains the arch-native kernel, the same workload ran 95% util at 80% TDP and
# 2.5x the throughput (16 -> 40 tok/s on a 27B 4-bit model).
#
# Usage:  bash util_vs_power_tell.sh [seconds] [gpu_index]
# Exit 0 = looks like a real tensor-core path, 1 = suspect fallback, 2 = could not run.

set -uo pipefail
SECS="${1:-30}"
GPU="${2:-0}"

command -v nvidia-smi >/dev/null 2>&1 || { echo "nvidia-smi not found"; exit 2; }

samples=$(nvidia-smi -i "$GPU" \
  --query-gpu=utilization.gpu,power.draw,power.limit \
  --format=csv,noheader,nounits -l 1 -c "$SECS" 2>/dev/null)

[ -n "$samples" ] || { echo "no samples collected"; exit 2; }

read -r mean_util mean_pw limit <<<"$(awk -F', *' '
  { u+=$1; p+=$2; l=$3; n++ }
  END { if (n) printf "%.1f %.0f %.0f", u/n, p/n, l }
' <<<"$samples")"

pct=$(awk -v p="$mean_pw" -v l="$limit" 'BEGIN{ if (l>0) printf "%.0f", 100*p/l; else print 0 }')

echo "  samples          : $(wc -l <<<"$samples") over ${SECS}s on GPU ${GPU}"
echo "  mean utilization : ${mean_util}%"
echo "  mean power       : ${mean_pw}W / ${limit}W (${pct}% TDP)"

hi_util=$(awk -v u="$mean_util" 'BEGIN{ print (u >= 90) ? 1 : 0 }')
lo_power=$(awk -v p="$pct"       'BEGIN{ print (p  <  60) ? 1 : 0 }')

if [ "$hi_util" = "1" ] && [ "$lo_power" = "1" ]; then
  cat <<'EOF'

  VERDICT: high-util / low-power. SUSPECT FALLBACK KERNEL.

  Next, in this order:
    1. git merge-base --is-ancestor <fix-commit> <running-HEAD> && echo present || echo STALE
       (the fix is often already in the branch you track; production was simply never rebuilt)
    2. read the server's startup system_info banner for the arch-native feature flag.
       A flag you passed is not evidence; a banner the binary printed is.
    3. rebuild from the branch tip in an isolated `git worktree`, mirroring the prod CMake cache.

  On cutover: SIGTERM can leave the old server in D state still holding VRAM. Use kill -9.
EOF
  exit 1
fi

if [ "$hi_util" = "1" ]; then
  echo
  echo "  VERDICT: high utilization with healthy power draw, kernel path looks real."
else
  echo
  echo "  VERDICT: utilization below 90%, this check is inconclusive; the bottleneck is"
  echo "  probably elsewhere (queueing behind other requests, host-side, or client-side)."
fi
exit 0
