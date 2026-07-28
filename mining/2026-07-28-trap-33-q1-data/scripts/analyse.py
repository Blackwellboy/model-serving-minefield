#!/usr/bin/env python3
"""Analyser for Q1 / trap 33 on NVFP4.

Per-arm counts, paired McNemar (exact, two-sided), truncation and unparsable
rates, and every delta expressed against our own published plus-or-minus 1.3
point agreement floor at n=600.

Answer extraction is identical to the Q2 agreement-floor analyser so the two
studies are directly comparable.
"""
import json, os, re, sys
from math import comb

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/arm_q1/out")
BAND = 1.3  # points at n=600, published: mining/2026-07-28-our-agreement-floor...


def parse_answer(rec):
    txt = (rec.get("content") or "").strip()
    if not txt:
        txt = (rec.get("reasoning_content") or "").strip()
    if not txt:
        return None
    m = re.search(r"\b([ABCD])\b", txt)
    if m:
        return m.group(1)
    m = re.search(r"([ABCD])", txt)
    return m.group(1) if m else None


def load(tag):
    path = os.path.join(OUT, tag + ".jsonl")
    recs = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        recs[r["idx"]] = {
            "pred": parse_answer(r),
            "gold": r["gold"],
            "subject": r["subject"],
            "trunc": r.get("finish_reason") == "length",
            "err": "error" in r,
            "toks": r.get("completion_tokens"),
        }
    return recs


def summarise(tag, recs):
    n = len(recs)
    return {
        "tag": tag,
        "n": n,
        "correct": sum(1 for v in recs.values() if v["pred"] == v["gold"]),
        "errors": sum(1 for v in recs.values() if v["err"]),
        "truncated": sum(1 for v in recs.values() if v["trunc"]),
        "unparsable": sum(1 for v in recs.values() if v["pred"] is None),
        "mean_completion_tokens": round(
            sum(v["toks"] or 0 for v in recs.values()) / max(n, 1), 2),
    }


def mcnemar_exact(b, c):
    """Two-sided exact binomial test on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def pair(tag_a, tag_b, a, b):
    idx = sorted(set(a) & set(b))
    n = len(idx)
    ca = sum(1 for i in idx if a[i]["pred"] == a[i]["gold"])
    cb = sum(1 for i in idx if b[i]["pred"] == b[i]["gold"])
    # b_disc: right in A, wrong in B.  c_disc: wrong in A, right in B.
    b_disc = sum(1 for i in idx
                 if a[i]["pred"] == a[i]["gold"] and b[i]["pred"] != b[i]["gold"])
    c_disc = sum(1 for i in idx
                 if a[i]["pred"] != a[i]["gold"] and b[i]["pred"] == b[i]["gold"])
    agree = sum(1 for i in idx if a[i]["pred"] == b[i]["pred"])
    delta = (cb - ca) * 100.0 / n
    p = mcnemar_exact(b_disc, c_disc)
    return {
        "a": tag_a, "b": tag_b, "n": n,
        "correct_a": ca, "correct_b": cb,
        "pct_a": round(ca * 100.0 / n, 2), "pct_b": round(cb * 100.0 / n, 2),
        "delta_pts": round(delta, 2),
        "discordant_a_right_b_wrong": b_disc,
        "discordant_a_wrong_b_right": c_disc,
        "mcnemar_exact_p": round(p, 6),
        "answer_agreement": agree,
        "answer_agreement_pct": round(agree * 100.0 / n, 2),
        "abs_delta_vs_band": round(abs(delta) / BAND, 2),
        "outside_band": abs(delta) > BAND,
    }


if __name__ == "__main__":
    tags = [t[:-6] for t in sorted(os.listdir(OUT)) if t.endswith(".jsonl")
            and "_smoke" not in t]
    data = {t: load(t) for t in tags}
    res = {"band_pts": BAND, "arms": [summarise(t, data[t]) for t in tags],
           "pairs": []}

    def add(x, y):
        if x in data and y in data:
            res["pairs"].append(pair(x, y, data[x], data[y]))

    # 1. the pre-registered primary contrast
    add("k8_p1", "k32_p1")
    # 2. the monotone ladder, pass 1 (executed low to high)
    add("k8_p1", "k16_p1")
    add("k8_p1", "k24_p1")
    # 3. the monotone ladder, pass 2 (executed high to low)
    add("k8_p2", "k16_p2")
    add("k8_p2", "k24_p2")
    add("k8_p2", "k32_p2")
    # 4. same-arm restart replicates: this study's own noise, measured in-run
    add("k8_p1", "k8_p2")
    add("k16_p1", "k16_p2")
    add("k24_p1", "k24_p2")
    add("k32_p1", "k32_p2")

    print(json.dumps(res, indent=2))
