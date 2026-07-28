#!/usr/bin/env bash
# Build one model directory per arm. Every file is a HARD LINK to the pinned
# snapshot (zero copy, resolves identically inside and outside the container)
# except config.json, which is a real file differing ONLY in
# text_config.num_experts_per_tok.
set -eu
SNAP=~/.cache/huggingface/hub/models--nvidia--Qwen3.6-35B-A3B-NVFP4/snapshots/491c2f1ea524c639598bf8fa787a93fed5a6fbce
ROOT=~/trap33/arms
mkdir -p "$ROOT"

norm() {
  python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])),indent=1,sort_keys=True))" "$1"
}

for K in 8 16 24 32; do
  D="$ROOT/k$K"
  rm -rf "$D"; mkdir -p "$D"
  for f in "$SNAP"/*; do
    b=$(basename "$f")
    if [ "$b" = "config.json" ]; then continue; fi
    ln "$(readlink -f "$f")" "$D/$b"
  done
  python3 - "$SNAP/config.json" "$D/config.json" "$K" <<'PYEOF'
import json, sys
src, dst, k = sys.argv[1], sys.argv[2], int(sys.argv[3])
c = json.load(open(src))
assert c["text_config"]["num_experts_per_tok"] == 8, c["text_config"]["num_experts_per_tok"]
c["text_config"]["num_experts_per_tok"] = k
json.dump(c, open(dst, "w"), indent=2)
PYEOF
  echo "built $D  num_experts_per_tok=$K  files=$(ls -1 "$D" | wc -l)"
done

echo "=== proof: every arm config differs from the k=8 arm ONLY in that integer ==="
for K in 16 24 32; do
  echo "--- k8 vs k$K ---"
  diff <(norm "$ROOT/k8/config.json") <(norm "$ROOT/k$K/config.json") || true
done

echo "=== proof: k8 arm config is semantically identical to the pinned snapshot ==="
if diff <(norm "$SNAP/config.json") <(norm "$ROOT/k8/config.json"); then echo "IDENTICAL"; fi

echo "=== proof: weight files share inodes with the pinned snapshot (no copy, same bytes) ==="
for f in model-00001-of-00003.safetensors model-00002-of-00003.safetensors model-00003-of-00003.safetensors; do
  a=$(stat -c %i "$(readlink -f "$SNAP/$f")")
  b=$(stat -c %i "$ROOT/k32/$f")
  if [ "$a" = "$b" ]; then s=YES; else s=NO; fi
  echo "$f snapshot_inode=$a k32_inode=$b same=$s"
done

echo "=== disk after ==="
df -h /home | tail -1
