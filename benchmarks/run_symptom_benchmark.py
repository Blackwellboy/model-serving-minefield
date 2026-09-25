"""Score the offline symptom matcher against plain-language user queries.

    python benchmarks/run_symptom_benchmark.py            # summary table
    python benchmarks/run_symptom_benchmark.py --misses   # list every miss
    python benchmarks/run_symptom_benchmark.py --json     # machine-readable

Metrics, per split:
  top1    the right trap is ranked first
  top5    the right trap is anywhere in the first five
  found   the right trap is returned at all (the matcher refuses weak text)
  mrr     mean reciprocal rank of the right trap (0 when not returned)
Negatives are off-domain queries; `false_alarm` is the share that returned
any canonical candidate. Lower is better.

Tune matcher changes on the `tune` split only and report `holdout`, so a
published number is not a number the matcher was fitted to.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from minefield.matching import search  # noqa: E402
from minefield.registry import load_registry  # noqa: E402

DATA = Path(__file__).with_name("symptom_queries.json")


def _rank(registry, query: str, trap: str, limit: int) -> int | None:
    results = search(registry, query, limit=limit)
    ids = [r["trap_ids"][0] for r in results]
    return ids.index(trap) + 1 if trap in ids else None


def evaluate(limit: int = 10) -> dict:
    registry = load_registry(ROOT)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    splits: dict[str, dict] = {}
    misses: list[dict] = []
    for case in data["cases"]:
        rank = _rank(registry, case["query"], case["trap"], limit)
        s = splits.setdefault(case["split"], {"n": 0, "top1": 0, "top5": 0, "found": 0, "rr": 0.0})
        s["n"] += 1
        if rank:
            s["found"] += 1
            s["rr"] += 1.0 / rank
            s["top1"] += rank == 1
            s["top5"] += rank <= 5
        if not rank or rank > 5:
            misses.append({**case, "rank": rank})
    negatives = {}
    for name, queries in sorted(data["negatives"].items()):
        hits = [q for q in queries if search(registry, q, limit=1)]
        negatives[name] = {"n": len(queries), "false_alarm": round(len(hits) / len(queries), 3), "hits": hits}
    summary = {
        name: {
            "n": s["n"],
            "top1": round(s["top1"] / s["n"], 3),
            "top5": round(s["top5"] / s["n"], 3),
            "found": round(s["found"] / s["n"], 3),
            "mrr": round(s["rr"] / s["n"], 3),
        }
        for name, s in sorted(splits.items())
    }
    return {
        "splits": summary,
        "negatives": negatives,
        "misses": misses,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--misses", action="store_true", help="list queries whose trap was not in the top 5")
    args = ap.parse_args(argv)
    report = evaluate()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{'split':<8} {'n':>4} {'top1':>6} {'top5':>6} {'found':>6} {'mrr':>6}")
    for name, s in report["splits"].items():
        print(f"{name:<8} {s['n']:>4} {s['top1']:>6.1%} {s['top5']:>6.1%} {s['found']:>6.1%} {s['mrr']:>6.3f}")
    for name, neg in report["negatives"].items():
        print(f"off-domain false alarms [{name}]: {neg['false_alarm']:.1%} of {neg['n']}")
    if args.misses:
        for m in report["misses"]:
            print(f"  [{m['split']}] trap {m['trap']} rank={m['rank']}: {m['query']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
