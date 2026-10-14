"""Re-key line-keyed sanitizer waivers to where their reviewed text now lives.

usage: rekey_adjudications.py REPO BASE_REF OUT_FILE

A waiver is `path:line: reason`. Inserting or deleting lines above it makes it
cover a different line (and every pattern on that line). For each waiver, take
the exact text it covered at BASE_REF (where it was reviewed) and find that
identical text in the current file: same line -> keep; moved -> re-key to the
nearest identical line; gone -> drop. Line 0 (a filename waiver) is kept while
the file exists. Prints a summary; never adds a waiver for text nobody reviewed.
"""
import subprocess, sys
from pathlib import Path

repo, base, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
ADJ = "integrity/_proofs/sanitizer_adjudicated.txt"
_cache = {}


def base_lines(path):
    if path not in _cache:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{base}:{path}"], capture_output=True)
        _cache[path] = r.stdout.decode("utf-8", "replace").split("\n") if r.returncode == 0 else None
    return _cache[path]


def cur_lines(path):
    p = repo / path
    return p.read_text(encoding="utf-8", errors="replace").split("\n") if p.is_file() else None


stats = {"kept": 0, "rekeyed": 0, "dropped_gone": 0, "dropped_nofile": 0, "unverifiable_kept": 0, "header": 0}
dropped, rekeyed = [], []
lines_out, seen = [], set()
for raw in (repo / ADJ).read_text(encoding="utf-8").split("\n"):
    s = raw.strip()
    if not s or s.startswith("#"):
        lines_out.append(raw); stats["header"] += 1; continue
    path, ln, reason = (x.strip() for x in s.split(":", 2))
    n = int(ln)
    cur = cur_lines(path)
    if cur is None:
        stats["dropped_nofile"] += 1; dropped.append(s); continue
    key = (path, n)
    if n == 0:
        new = n
    else:
        old = base_lines(path)
        if old is None or n > len(old):
            # added after BASE_REF: cannot prove what was reviewed, so keep it unchanged
            stats["unverifiable_kept"] += 1; new = n
        else:
            text = old[n - 1]
            if n <= len(cur) and cur[n - 1] == text:
                stats["kept"] += 1; new = n
            else:
                hits = [i + 1 for i, l in enumerate(cur) if l == text]
                if not hits:
                    stats["dropped_gone"] += 1; dropped.append(s); continue
                new = min(hits, key=lambda i: abs(i - n))
                stats["rekeyed"] += 1; rekeyed.append(f"{path}:{n} -> {new}")
    if (path, new) in seen:
        continue
    seen.add((path, new))
    lines_out.append(f"{path}:{new}: {reason}")
out.write_text("\n".join(lines_out), encoding="utf-8")
print(stats)
print("re-keyed (first 40):"); [print("  ", r) for r in rekeyed[:40]]
print("dropped (first 40):"); [print("  ", d[:150]) for d in dropped[:40]]
