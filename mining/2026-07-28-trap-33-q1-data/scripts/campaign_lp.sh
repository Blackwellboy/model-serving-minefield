#!/usr/bin/env bash
# Confirmatory choice-logprob pass. Alternating order again: k8, k32, then a k8
# restart replicate so this protocol carries its own measured restart noise
# rather than borrowing the generation-scored band.
set -u
cd ~/trap33
for i in $(seq 1 120); do
  n=$(docker ps -a --format '{{.Names}}' | grep -cE '^trap33' || true)
  if [ "$n" = "0" ]; then break; fi
  sleep 15
done
for spec in "8 lp_k8_p1" "32 lp_k32_p1" "8 lp_k8_p2" "32 lp_k32_p2"; do
  set -- $spec
  echo "### LP CAMPAIGN starting $2 at $(date -u +%FT%TZ)"
  bash run_arm_lp.sh "$1" "$2"
  rc=$?
  echo "### LP CAMPAIGN $2 rc=$rc at $(date -u +%FT%TZ)"
  if [ "$rc" -ne 0 ]; then echo "### LP CAMPAIGN ABORTING on $2"; exit "$rc"; fi
done
echo "### LP CAMPAIGN COMPLETE $(date -u +%FT%TZ)"
