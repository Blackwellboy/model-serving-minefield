#!/usr/bin/env bash
# run_arm_lp.sh <K> <TAG>  -- same arm mechanics as run_arm.sh, choice-logprob
# scoring instead of generation scoring. Launch line is byte-identical to the
# generation-scored arms, so the two protocols see the same server.
set -u
K="$1"; TAG="$2"
NAME="armlp_k${K}"
PORT=8899
W=~/trap33
mkdir -p "$W/out" "$W/logs"
LOG="$W/logs/${TAG}.log"

{
echo "=== ARM $TAG (k=$K, choice-logprob) $(date -u +%FT%TZ) ==="
for i in 1 2 3; do
  up=$(docker ps --format '{{.Names}}' | grep -c '^cotenant_lane$' || true)
  if [ "$up" != "0" ]; then echo "ABORT: cotenant_lane revived (R3)"; exit 3; fi
  sleep 5
done
echo "R3 gate: cotenant_lane down across 3 checks"

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
if [ "$rc" -ne 0 ]; then echo "ABORT: launch failed"; exit 1; fi

up=0
for i in $(seq 1 120); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/v1/models" || true)
  if [ "$code" = "200" ]; then up=1; echo "healthy after $((i*10))s"; break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" != "true" ]; then
    echo "ABORT: container exited during startup"; docker logs --tail 60 "$NAME"; exit 1
  fi
  sleep 10
done
if [ "$up" != "1" ]; then echo "ABORT: never became healthy"; exit 1; fi

docker exec "$NAME" python3 -c "import json;print('CONFIG num_experts_per_tok =', json.load(open('/arms/k${K}/config.json'))['text_config']['num_experts_per_tok'])"

echo "--- smoke 20 ---"
python3 "$W/logprob_runner.py" --url "http://127.0.0.1:$PORT" --model qwen36 \
  --tag "${TAG}_smoke" --items "$W/mmlu600_seed0.jsonl" --out "$W/out" --limit 20

# Smoke gate. A working choice-logprob scorer sits near the generation-scored
# arms (about 17/20); chance is 5/20. The first version of this runner scored
# 3/20 because it read the generated token instead of the choice, so the gate
# is not decoration.
SMOKE=$(python3 -c "
import json
rs=[json.loads(l) for l in open('$W/out/${TAG}_smoke.jsonl')]
print(sum(1 for r in rs if r.get('pred')==r['gold']))
")
echo "smoke correct = $SMOKE / 20"
if [ "$SMOKE" -lt 10 ]; then
  echo "ABORT: smoke gate failed ($SMOKE/20, chance is 5) -- scorer is wrong, not the model"
  docker rm -f "$NAME"; exit 6
fi

echo "--- full 600 ---"
python3 "$W/logprob_runner.py" --url "http://127.0.0.1:$PORT" --model qwen36 \
  --tag "$TAG" --items "$W/mmlu600_seed0.jsonl" --out "$W/out"

docker rm -f "$NAME"
sleep 20
free -g
echo "=== ARM $TAG DONE $(date -u +%FT%TZ) ==="
} 2>&1 | tee "$LOG"
