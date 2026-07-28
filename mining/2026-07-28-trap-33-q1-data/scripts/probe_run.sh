#!/usr/bin/env bash
# Stand a k=8 server up purely to answer the trap-15 question (does this
# endpoint expose echo+logprobs, i.e. is choice-logprob scoring possible?).
# Kept off the measured arms so the probe traffic cannot perturb them.
set -u
W=~/trap33
NAME=arm_probe
PORT=8899
{
echo "=== TRAP 15 PROBE $(date -u +%FT%TZ) ==="
for i in 1 2 3; do
  up=$(docker ps --format '{{.Names}}' | grep -c '^cotenant_lane$' || true)
  if [ "$up" != "0" ]; then echo "ABORT: laguna revived (R3)"; exit 3; fi
  sleep 5
done
ok=0
for i in $(seq 1 30); do
  AVAIL=$(free -g | awk '/^Mem:/{print $7}')
  echo "R4 gate i=$i avail=${AVAIL}G"
  if [ "$AVAIL" -ge 60 ]; then ok=$((ok+1)); else ok=0; fi
  if [ "$ok" -ge 3 ]; then break; fi
  sleep 10
done
if [ "$ok" -lt 3 ]; then echo "ABORT: R4 gate"; exit 5; fi

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --gpus all --ipc=host --network host \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v ~/trap33/arms:/arms:ro \
  vllm/vllm-openai:nightly \
  --model /arms/k8 --served-model-name qwen36 \
  --host 0.0.0.0 --port $PORT --tensor-parallel-size 1 --trust-remote-code \
  --kv-cache-dtype fp8 --attention-backend flashinfer --moe-backend marlin \
  --gpu-memory-utilization 0.4 --max-model-len 262144 --max-num-seqs 4 \
  --max-num-batched-tokens 8192 --enable-chunked-prefill --async-scheduling \
  --speculative-config '{"method":"mtp","num_speculative_tokens":3,"moe_backend":"triton"}' \
  --load-format fastsafetensors --reasoning-parser qwen3 --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice
for i in $(seq 1 120); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/v1/models" || true)
  if [ "$code" = "200" ]; then echo "healthy after $((i*10))s"; break; fi
  sleep 10
done
python3 "$W/logprob_probe.py" "http://127.0.0.1:$PORT" qwen36
docker rm -f "$NAME"
sleep 20
free -g
echo "=== PROBE DONE $(date -u +%FT%TZ) ==="
} 2>&1 | tee "$W/logs/trap15_probe.log"
