#!/usr/bin/env python3
"""Choice-logprob MMLU scorer -- the protocol Hikari used, run against our lane.

Trap 15 says an OpenAI-compatible lane may not expose echo+logprobs. This one
does (proof: logs/trap15_probe.log), so the preferred scoring path in the Q1
plan is available and this runner uses it.

For each item the raw prompt is sent through /v1/completions (no chat template,
no generation, therefore no truncation by construction) once per choice with
echo=true. The score of a choice is the summed logprob of the tokens the choice
adds beyond the base prompt. Argmax over the four choices is the prediction.
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
a = ap.parse_args()

LETTERS = ["A", "B", "C", "D"]
items = [json.loads(l) for l in open(a.items, encoding="utf-8")]
if a.limit:
    items = items[:a.limit]

os.makedirs(a.out, exist_ok=True)
outp = os.path.join(a.out, a.tag + ".jsonl")
f = open(outp, "w", encoding="utf-8")
s = requests.Session()


def echo_logprobs(prompt):
    """Return the per-token logprob list for prompt, as echoed by the server.

    max_tokens MUST be 0. With max_tokens=1 the server appends the generated
    token to the echoed `tokens` list, so len(tokens) overshoots the prompt by
    one and every continuation score silently reads the generated token instead
    of the choice. That mistake scores below chance and is easy to miss without
    a smoke gate -- it is the reason this runner asserts the prefix below.
    """
    r = s.post(a.url + "/v1/completions", json={
        "model": a.model, "prompt": prompt, "max_tokens": 0,
        "echo": True, "logprobs": 0, "temperature": 0}, timeout=300)
    r.raise_for_status()
    lp = r.json()["choices"][0]["logprobs"]
    return lp["token_logprobs"], lp["tokens"]


t0 = time.time()
nerr = 0
for it in items:
    rec = {"idx": it["idx"], "subject": it["subject"], "gold": it["gold"]}
    try:
        base_lp, base_tok = echo_logprobs(it["prompt"])
        nbase = len(base_tok)
        scores = {}
        for L in LETTERS:
            lp, tok = echo_logprobs(it["prompt"] + " " + L)
            if tok[:nbase] != base_tok:
                raise RuntimeError("tokenisation boundary moved for choice " + L)
            # tokens the choice adds beyond the base prompt
            tail = [x for x in lp[nbase:] if x is not None]
            scores[L] = sum(tail)
            if not tail:
                raise RuntimeError("empty continuation for choice " + L)
        rec["scores"] = {k: round(v, 6) for k, v in scores.items()}
        rec["pred"] = max(scores, key=scores.get)
        rec["n_base_tokens"] = nbase
    except Exception as e:
        nerr += 1
        rec["error"] = (type(e).__name__ + ": " + str(e))[:300]
        rec["pred"] = None
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.flush()
    if (it["idx"] + 1) % 100 == 0:
        print("  %d/%d  %.0fs  err=%d" % (it["idx"] + 1, len(items),
                                          time.time() - t0, nerr), flush=True)
f.close()
print("DONE %s: %d items, %.0fs, errors=%d -> %s" % (
    a.tag, len(items), time.time() - t0, nerr, outp))
