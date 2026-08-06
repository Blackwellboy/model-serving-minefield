#!/usr/bin/env python3
"""Serial MMLU runner for the Q2 agreement-floor study.

One request at a time (concurrency 1) so that vLLM's continuous-batching
composition cannot vary between arms. Greedy: temperature 0, top_p 1.
Captures both `content` and `reasoning_content` because the qwen3 reasoning
parser can route the answer to either.
"""
import argparse, json, os, sys, time
import requests

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--max-tokens", type=int, default=16)
ap.add_argument("--no-think", action="store_true", default=True)
a = ap.parse_args()

W = os.environ.get("AGREEMENT_FLOOR_WORKDIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..")
items = [json.loads(l) for l in open(f"{W}/mmlu600_seed0.jsonl", encoding="utf-8")]
if a.limit:
    items = items[:a.limit]

outp = f"{W}/out/{a.tag}.jsonl"
os.makedirs(f"{W}/out", exist_ok=True)
f = open(outp, "w", encoding="utf-8")
s = requests.Session()
t0 = time.time()
nerr = 0
for it in items:
    body = {
        "model": a.model,
        "messages": [{"role": "user", "content": it["prompt"]}],
        "temperature": 0, "top_p": 1, "max_tokens": a.max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    rec = {"idx": it["idx"], "subject": it["subject"], "gold": it["gold"]}
    try:
        r = s.post(f"{a.url}/v1/chat/completions", json=body, timeout=300)
        r.raise_for_status()
        j = r.json()
        ch = j["choices"][0]
        msg = ch.get("message", {})
        rec["content"] = msg.get("content") or ""
        rec["reasoning_content"] = msg.get("reasoning_content") or ""
        rec["finish_reason"] = ch.get("finish_reason")
        rec["completion_tokens"] = j.get("usage", {}).get("completion_tokens")
    except Exception as e:
        nerr += 1
        rec["error"] = f"{type(e).__name__}: {e}"[:300]
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.flush()
    if (it["idx"] + 1) % 50 == 0:
        el = time.time() - t0
        print(f"  {it['idx']+1}/{len(items)}  {el:.0f}s  err={nerr}", flush=True)
f.close()
print(f"DONE {a.tag}: {len(items)} items, {time.time()-t0:.0f}s, errors={nerr} -> {outp}")
