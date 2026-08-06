#!/usr/bin/env python3
"""Serial MMLU runner for the Q1 / trap-33 top-k study on node.

Deliberately identical in protocol to the Q2 agreement-floor runner, because
the plus-or-minus 1.3 point band this study is measured against was produced
with exactly this scoring path. One request at a time (concurrency 1), greedy,
thinking off, small cap. Captures content and reasoning_content because the
qwen3 reasoning parser can route the answer to either.
"""
import argparse, json, os, time
import requests

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--items", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--max-tokens", type=int, default=16)
a = ap.parse_args()

items = [json.loads(l) for l in open(a.items, encoding="utf-8")]
if a.limit:
    items = items[:a.limit]

os.makedirs(a.out, exist_ok=True)
outp = os.path.join(a.out, a.tag + ".jsonl")
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
        r = s.post(a.url + "/v1/chat/completions", json=body, timeout=300)
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
        rec["error"] = (type(e).__name__ + ": " + str(e))[:300]
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.flush()
    if (it["idx"] + 1) % 100 == 0:
        print("  %d/%d  %.0fs  err=%d" % (it["idx"] + 1, len(items), time.time() - t0, nerr), flush=True)
f.close()
print("DONE %s: %d items, %.0fs, errors=%d -> %s" % (a.tag, len(items), time.time() - t0, nerr, outp))
