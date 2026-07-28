#!/usr/bin/env bash
# Re-emit the four arm-integrity proofs WITHOUT rebuilding anything, so the
# proof is taken from the directories the arms were actually served from.
set -u
SNAP=~/.cache/huggingface/hub/models--nvidia--Qwen3.6-35B-A3B-NVFP4/snapshots/491c2f1ea524c639598bf8fa787a93fed5a6fbce
ROOT=~/trap33/arms

norm() {
  python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])),indent=1,sort_keys=True))" "$1"
}

echo "ARM INTEGRITY PROOF  $(date -u +%FT%TZ)"
echo "pinned snapshot: 491c2f1ea524c639598bf8fa787a93fed5a6fbce"
echo

echo "=== 1. loaded value per arm directory ==="
for K in 8 16 24 32; do
  printf 'k%-3s num_experts_per_tok = %s\n' "$K" \
    "$(python3 -c "import json;print(json.load(open('$ROOT/k$K/config.json'))['text_config']['num_experts_per_tok'])")"
done
echo

echo "=== 2. k=8 arm config is semantically identical to the pinned snapshot ==="
if diff <(norm "$SNAP/config.json") <(norm "$ROOT/k8/config.json"); then
  echo "IDENTICAL"
fi
echo

echo "=== 3. each raised arm differs from the k=8 arm in exactly one line ==="
for K in 16 24 32; do
  echo "--- k8 vs k$K ---"
  diff <(norm "$ROOT/k8/config.json") <(norm "$ROOT/k$K/config.json") || true
done
echo

echo "=== 4. weight files are the same inodes in every arm (byte-identical, not copied) ==="
for f in model-00001-of-00003.safetensors model-00002-of-00003.safetensors model-00003-of-00003.safetensors; do
  printf '%s  snapshot=%s' "$f" "$(stat -c %i "$(readlink -f "$SNAP/$f")")"
  for K in 8 16 24 32; do printf '  k%s=%s' "$K" "$(stat -c %i "$ROOT/k$K/$f")"; done
  printf '\n'
done
echo

echo "=== 5. item set on the node, as read by every arm ==="
sha256sum ~/trap33/mmlu600_seed0.jsonl
echo "expected prefix c074b59b (the set the agreement floor was measured on)"
echo

echo "=== 6. serving stack ==="
hostname
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' vllm/vllm-openai:nightly
