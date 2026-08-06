#!/usr/bin/env bash
# Remaining arms, serial, ALTERNATING order.
#
# Pass 1 runs the ladder upward, pass 2 runs it downward, so no arm sits at a
# fixed position in the execution sequence and any slow drift in node state is
# spread across arms rather than loaded onto one.
#
#   executed order: k8_p1, k16_p1, k24_p1, k32_p1, k32_p2, k24_p2, k16_p2, k8_p2
#
# k8_p1 and k16_p1 were launched individually before this script; it waits for
# any in-flight arm to finish, then continues.
set -u
cd ~/trap33

# wait for any in-flight arm to clear
for i in $(seq 1 120); do
  n=$(docker ps -a --format '{{.Names}}' | grep -c '^arm_' || true)
  if [ "$n" = "0" ]; then break; fi
  sleep 15
done

for spec in "24 k24_p1" "32 k32_p1" "32 k32_p2" "24 k24_p2" "16 k16_p2" "8 k8_p2"; do
  set -- $spec
  K="$1"; TAG="$2"
  echo "### CAMPAIGN starting $TAG at $(date -u +%FT%TZ)"
  bash run_arm.sh "$K" "$TAG"
  rc=$?
  echo "### CAMPAIGN $TAG rc=$rc at $(date -u +%FT%TZ)"
  if [ "$rc" -ne 0 ]; then echo "### CAMPAIGN ABORTING on $TAG"; exit "$rc"; fi
done
echo "### CAMPAIGN COMPLETE $(date -u +%FT%TZ)"
