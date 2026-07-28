#!/usr/bin/env python3
"""Analyser for the choice-logprob confirmatory arms.

Same statistics as analyse.py. Predictions come straight from the scorer's
argmax, so there is no answer extraction and, by construction, no truncation
and nothing unparsable -- which is the whole reason this protocol is the
preferred one in the Q1 plan.
"""
import json, os, sys
from math import comb

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/arm_q1/out_lp")
BAND = 1.3


def load(tag):
    recs = {}
    for line in open(os.path.join(OUT, tag + ".jsonl"), encoding="utf-8"):
        r = json.loads(line)
        recs[r["idx"]] = {"pred": r.get("pred"), "gold": r["gold"],
                          "subject": r["subject"], "err": "error" in r}
    return recs


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n))


def pair(ta, tb, a, b):
    idx = sorted(set(a) & set(b))
    n = len(idx)
    ca = sum(1 for i in idx if a[i]["pred"] == a[i]["gold"])
    cb = sum(1 for i in idx if b[i]["pred"] == b[i]["gold"])
    bd = sum(1 for i in idx if a[i]["pred"] == a[i]["gold"] and b[i]["pred"] != b[i]["gold"])
    cd = sum(1 for i in idx if a[i]["pred"] != a[i]["gold"] and b[i]["pred"] == b[i]["gold"])
    ag = sum(1 for i in idx if a[i]["pred"] == b[i]["pred"])
    d = (cb - ca) * 100.0 / n
    return {"a": ta, "b": tb, "n": n, "correct_a": ca, "correct_b": cb,
            "pct_a": round(ca * 100.0 / n, 2), "pct_b": round(cb * 100.0 / n, 2),
            "delta_pts": round(d, 2),
            "discordant_a_right_b_wrong": bd, "discordant_a_wrong_b_right": cd,
            "mcnemar_exact_p": round(mcnemar_exact(bd, cd), 6),
            "answer_agreement": ag, "answer_agreement_pct": round(ag * 100.0 / n, 2),
            "abs_delta_vs_band": round(abs(d) / BAND, 2)}


if __name__ == "__main__":
    tags = [t[:-6] for t in sorted(os.listdir(OUT))
            if t.endswith(".jsonl") and "_smoke" not in t]
    data = {t: load(t) for t in tags}
    res = {"band_pts_generation_scored_only": BAND,
           "arms": [{"tag": t, "n": len(d),
                     "correct": sum(1 for v in d.values() if v["pred"] == v["gold"]),
                     "errors": sum(1 for v in d.values() if v["err"]),
                     "truncated": 0, "unparsable": sum(1 for v in d.values() if v["pred"] is None)}
                    for t, d in data.items()],
           "pairs": []}

    def add(x, y):
        if x in data and y in data:
            res["pairs"].append(pair(x, y, data[x], data[y]))

    add("lp_k8_p1", "lp_k32_p1")
    add("lp_k8_p2", "lp_k32_p2")
    add("lp_k8_p1", "lp_k8_p2")
    add("lp_k32_p1", "lp_k32_p2")
    print(json.dumps(res, indent=2))
