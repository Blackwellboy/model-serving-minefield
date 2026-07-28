#!/usr/bin/env python3
"""Build the fixed MMLU item set for the Q2 agreement-floor study.

Protocol, fixed before any run:
  - source: cais/mmlu, config 'all', split 'test'
  - shuffle: random.Random(0).shuffle over the full ordered test set
  - take: first 600 after shuffle
Recorded here so the item set is reproducible and cannot drift to fit a result.
"""
import json, random, hashlib, sys, os
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

W = os.environ.get("AGREEMENT_FLOOR_WORKDIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..")
p = hf_hub_download(repo_id="cais/mmlu", filename="all/test-00000-of-00001.parquet",
                    repo_type="dataset")
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
print(f"subjects {len(subs)}; top: {sorted(subs.items(), key=lambda x:-x[1])[:5]}")
