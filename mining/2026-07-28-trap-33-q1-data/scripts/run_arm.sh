#!/usr/bin/env bash
# run_arm.sh <K> <TAG>
#
# One arm = one server start. Launch line is byte-identical across arms except
# for the model directory, and the model directories differ only in
# text_config.num_experts_per_tok. Doctrine R3 (re-stop gate) and R4 (measured
# free memory) are enforced before every launch.
set -u
K="$1"; TAG="$2"
NAME="arm_k${K}"
PORT=8899
W=~/trap33
mkdir -p "$W/out" "$W/logs"
LOG="$W/logs/${TAG}.log"

{
echo "=== ARM $TAG (k=$K) $(date -u +%FT%TZ) ==="

# R3: the borrowed lane must be down and STAY down.
for i in 1 2 3; do
  up=$(docker ps --format '{{.Names}}' | grep -c '^cotenant_lane$' || true)
  if [ "$up" != "0" ]; then echo "ABORT: cotenant_lane revived (R3)"; exit 3; fi
  sleep 5
done
echo "R3 gate: cotenant_lane down across 3 checks"

# R4: measured free memory, never assumed.
ok=0
for i in $(seq 1 30); do
  AVAIL=$(free -g | awk '/^Mem:/{print $7}')
  echo "R4 gate i=$i avail=${AVAIL}G"
  if [ "$AVAIL" -ge 60 ]; then ok=$((ok+1)); else ok=0; fi
  if [ "$ok" -ge 3 ]; then break; fi
  sleep 10
done
if [ "$ok" -lt 3 ]; then echo "ABORT: R4 memory gate never cleared"; exit 5; fi
echo "R4 gate cleared at ${AVAIL}G"

docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "--- launch ---"
set -x
docker run -d --name "$NAME" --gpus all --ipc=host --network host \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v ~/trap33/arms:/arms:ro \
  vllm/vllm-openai:nightly \
  --model "/arms/k${K}" --served-model-name qwen36 \
  --host 0.0.0.0 --port $PORT --tensor-parallel-size 1 --trust-remote-code \
  --kv-cache-dtype fp8 --attention-backend flashinfer --moe-backend marlin \
  --gpu-memory-utilization 0.4 --max-model-len 262144 --max-num-seqs 4 \
  --max-num-batched-tokens 8192 --enable-chunked-prefill --async-scheduling \
  --speculative-config '{"method":"mtp","num_speculative_tokens":3,"moe_backend":"triton"}' \
  --load-format fastsafetensors --reasoning-parser qwen3 --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice
rc=$?
set +x
echo "LAUNCH_RC=$rc"
if [ "$rc" -ne 0 ]; then echo "ABORT: launch failed"; exit 1; fi

echo "--- health poll ---"
up=0
for i in $(seq 1 120); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/v1/models" || true)
  if [ "$code" = "200" ]; then up=1; echo "healthy after $((i*10))s"; break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" != "true" ]; then
    echo "ABORT: container exited during startup"; docker logs --tail 60 "$NAME"; exit 1
  fi
  sleep 10
done
if [ "$up" != "1" ]; then echo "ABORT: never became healthy"; docker logs --tail 80 "$NAME"; exit 1; fi

echo "--- effective expert count as loaded ---"
docker logs "$NAME" 2>&1 | grep -iE "num_experts_per_tok|experts_per_tok" | head -5 || true
docker exec "$NAME" python3 -c "import json;print('CONFIG num_experts_per_tok =', json.load(open('/arms/k${K}/config.json'))['text_config']['num_experts_per_tok'])"

echo "--- smoke 20 ---"
python3 "$W/runner.py" --url "http://127.0.0.1:$PORT" --model qwen36 \
  --tag "${TAG}_smoke" --items "$W/mmlu600_seed0.jsonl" --out "$W/out" --limit 20

echo "--- full 600 ---"
python3 "$W/runner.py" --url "http://127.0.0.1:$PORT" --model qwen36 \
  --tag "$TAG" --items "$W/mmlu600_seed0.jsonl" --out "$W/out"

echo "--- engine counters ---"
curl -s "http://127.0.0.1:$PORT/metrics" 2>/dev/null | grep -E "spec_decode|num_accepted|num_draft" | head -10 || true

echo "--- teardown ---"
docker rm -f "$NAME"
sleep 20
free -g
echo "=== ARM $TAG DONE $(date -u +%FT%TZ) ==="
} 2>&1 | tee "$LOG"
