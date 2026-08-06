#!/usr/bin/env python3
"""Rebuild the pinned MMLU-600 item set used by the Q2 agreement-floor study.

Protocol is copied verbatim from the Q2 builder so the bytes -- and therefore
the sha256 -- must match c074b59b...:
  - source: cais/mmlu, config 'all', split 'test'
  - shuffle: random.Random(0).shuffle over the full ordered test set
  - take: first 600 after shuffle
"""
import json, random, hashlib, os
import pyarrow.parquet as pq

W = os.path.expanduser("~/arm_q1")
os.makedirs(W, exist_ok=True)

p = os.path.expanduser(
    "~/.cache/huggingface/hub/datasets--cais--mmlu/snapshots/"
    "c30699e8356da336a370243923dbaf21066bb9fe/all/test-00000-of-00001.parquet")
t = pq.read_table(p).to_pydict()
n_all = len(t["question"])
rows = [{"question": t["question"][i], "subject": t["subject"][i],
         "choices": list(t["choices"][i]), "answer": int(t["answer"][i])}
        for i in range(n_all)]
print(f"full test set: {n_all} items")

order = list(range(n_all))
random.Random(0).shuffle(order)
sel = [rows[i] for i in order[:600]]

LETTERS = "ABCD"
items = []
for k, r in enumerate(sel):
    assert len(r["choices"]) == 4, r
    body = (r["question"].strip() + "\n"
            + "\n".join(f"{LETTERS[j]}. {c}" for j, c in enumerate(r["choices"])))
    prompt = ("The following is a multiple choice question. "
              "Answer with a single letter (A, B, C, or D) and nothing else.\n\n"
              + body + "\n\nAnswer:")
    items.append({"idx": k, "subject": r["subject"], "gold": LETTERS[r["answer"]],
                  "prompt": prompt})

out = f"{W}/mmlu600_seed0.jsonl"
with open(out, "w", encoding="utf-8") as f:
    for it in items:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")

h = hashlib.sha256(open(out, "rb").read()).hexdigest()
subs = {}
for it in items:
    subs[it["subject"]] = subs.get(it["subject"], 0) + 1
print(f"wrote {out}")
print(f"sha256 {h}")
print(f"EXPECTED PREFIX c074b59b -> {'MATCH' if h.startswith('c074b59b') else 'MISMATCH'}")
print(f"subjects {len(subs)}; top: {sorted(subs.items(), key=lambda x: -x[1])[:5]}")
