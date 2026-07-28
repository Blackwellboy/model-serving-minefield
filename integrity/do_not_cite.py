#!/usr/bin/env python3
"""do_not_cite.py - flag added text that cites something on the do-not-cite list.

The list already existed and was consulted by convention. Convention means
somebody has to remember at the moment of writing, which is the moment they
are least likely to. This runs it instead.

Default scope is ADDED lines in a diff, not the whole tree, for two reasons.
The list is about what you are publishing now; and the archives that record
the banned items necessarily contain them, so a whole-tree run reports the
evidence file as a violation. --all exists for a deliberate audit and honours
the recorded exemptions.

Tuned for low false positives on purpose. A check that cries wolf gets
ignored, and an ignored check is worse than no check because it looks like
coverage. Items that cannot be matched without noise are recorded in the
manual_only block and printed every run rather than dropped.

Usage:
    python3 integrity/do_not_cite.py                      # vs origin/HEAD, else HEAD
    python3 integrity/do_not_cite.py --base main
    python3 integrity/do_not_cite.py --staged
    python3 integrity/do_not_cite.py --all

Exit 0 clean, 1 on a hit.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LIST = os.path.join(HERE, "do_not_cite.json")
SCAN_EXTS = (".md", ".txt")
SKIP_DIRS = {".git", "__pycache__", "node_modules", "_proofs", "_proof_archive"}


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()



# --- GitHub Actions annotations ------------------------------------------
# "Process completed with exit code 1" was the entire annotation on the first
# red run. A stranger reading a red badge learned nothing. These emit the
# workflow-command form so the annotation names the file, the line and the
# missing thing, on the commit and in the PR diff.
def gha(level, message, path=None, line=None, title=None):
    def esc(v):
        return (str(v).replace("%", "%25").replace("\r", "%0D")
                .replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C"))
    props = []
    if path:
        # Only annotate files inside the workspace; GitHub cannot anchor an
        # annotation to a path outside the checkout, and a bogus path silently
        # drops the annotation rather than erroring.
        try:
            rel = os.path.relpath(os.path.abspath(path), os.getcwd())
        except ValueError:
            rel = None
        if rel and not rel.startswith(".."):
            props.append("file=%s" % esc(rel))
            if line:
                props.append("line=%d" % int(line))
    if title:
        props.append("title=%s" % esc(title))
    body = (str(message).replace("%", "%25")
            .replace("\r", "%0D").replace("\n", "%0A"))
    print("::%s %s::%s" % (level, ",".join(props), body) if props
          else "::%s::%s" % (level, body))


def git(root, *args):
    return subprocess.run(["git"] + list(args), cwd=root, capture_output=True,
                          text=True)


def pick_base(root, explicit):
    if explicit:
        return explicit
    for ref in ("origin/HEAD", "origin/main", "main"):
        if git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return "HEAD"


def added_lines(root, base, staged):
    """[(relpath, lineno_in_new_file, text)] for added lines only."""
    if staged:
        diff = git(root, "diff", "--cached", "--unified=0", "--no-color")
    else:
        diff = git(root, "diff", base, "--unified=0", "--no-color")
    if diff.returncode != 0:
        print("git diff failed: %s" % diff.stderr.strip(), file=sys.stderr)
        return None
    out = []
    rel = None
    newno = 0
    for line in diff.stdout.splitlines():
        if line.startswith("+++ b/"):
            rel = line[6:]
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            newno = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if rel and rel.endswith(SCAN_EXTS):
                out.append((rel, newno, line[1:]))
            newno += 1

    # A brand new file is entirely added text, and git diff does not show it
    # until it is tracked. Missing those would leave the single most likely
    # place for a fresh do-not-cite citation unchecked: the new writeup.
    ls = git(root, "ls-files", "--others", "--exclude-standard")
    if ls.returncode == 0:
        for rel in ls.stdout.splitlines():
            rel = rel.strip()
            if not rel.endswith(SCAN_EXTS):
                continue
            full = os.path.join(root, rel)
            if not os.path.exists(full):
                continue
            for i, text in enumerate(read(full).splitlines(), 1):
                out.append((rel, i, text))
    return out


# A nested checkout is a DIFFERENT repository. Walking into it reports its
# files under THIS repo's name, which silently voids every exemption keyed to
# the other repo and double-counts every hit. That is exactly what CI did:
# actions/checkout put the peer repo at .peer/laguna-s21-lab inside the
# workspace, laguna's gate-study README was scanned a second time as
# "minefield:.peer/laguna-s21-lab/gate-study/README.md", its laguna: exemption
# did not apply to that name, and a correctly exempt line was reported as a
# failure. The workflow now checks the peer out elsewhere; this function makes
# the tool right regardless of where anyone puts a clone.
def prune_nested_repos(dirpath, dirnames, pruned):
    keep = []
    for d in dirnames:
        if d in SKIP_DIRS:
            continue
        full = os.path.join(dirpath, d)
        # .git is a directory in a clone and a file in a worktree or submodule.
        if os.path.exists(os.path.join(full, ".git")):
            pruned.append(full)
            continue
        keep.append(d)
    dirnames[:] = keep


def all_lines(root, pruned=None):
    pruned = pruned if pruned is not None else []
    out = []
    for dp, dns, fns in os.walk(root):
        prune_nested_repos(dp, dns, pruned)
        for fn in sorted(fns):
            if not fn.endswith(SCAN_EXTS):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, root).replace("\\", "/")
            for i, line in enumerate(read(path).splitlines(), 1):
                out.append((rel, i, line))
    return out


def exempt(rel, exempts):
    for e in exempts:
        p = e["surface"]
        if rel == p or rel.startswith(p.rstrip("/") + "/") or rel.endswith("/" + p):
            return e["reason"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default=DEFAULT_LIST)
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", default=None)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--github", action="store_true",
                    help="also emit GitHub Actions annotations")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    cfg = json.loads(read(args.list))
    rules = [(r, re.compile(r["pattern"], re.I)) for r in cfg["enforced"]]
    exempts = cfg.get("exempt_paths", [])

    if args.all:
        lines = all_lines(root)
        scope = "whole tree"
    else:
        base = pick_base(root, args.base)
        lines = added_lines(root, base, args.staged)
        scope = "staged changes" if args.staged else "added lines vs %s" % base
        if lines is None:
            return 1

    hits = []
    skipped = []
    for rel, no, text in lines:
        reason = exempt(rel, exempts)
        for rule, rx in rules:
            m = rx.search(text)
            if not m:
                continue
            rec = {"id": rule["id"], "path": rel, "line": no,
                   "match": m.group(0), "text": text.strip()[:160],
                   "why": rule["why"], "instead": rule["instead"]}
            if reason:
                rec["exempt_reason"] = reason
                skipped.append(rec)
            else:
                hits.append(rec)

    if args.json:
        print(json.dumps({"scope": scope, "hits": hits, "exempt": skipped,
                          "manual_only": cfg.get("manual_only", [])}, indent=2))
        return 1 if hits else 0

    if args.github:
        for h in hits:
            gha("error",
                "do-not-cite item %r: matched %r. %s Instead: %s"
                % (h["id"], h["match"], h["why"], h["instead"]),
                os.path.join(root, h["path"]), h["line"],
                "do-not-cite: %s" % h["id"])

    print("do-not-cite: %s, %d enforced rules, %d lines examined"
          % (scope, len(rules), len(lines)))
    print("")
    if skipped:
        print("EXEMPT (%d) - recorded paths that carry the banned item on purpose"
              % len(skipped))
        for h in skipped:
            print("  %-24s %s:%d  %s" % (h["id"], h["path"], h["line"],
                                         h["exempt_reason"]))
        print("")
    print("MANUAL, not mechanisable (%d) - yours to check by eye:"
          % len(cfg.get("manual_only", [])))
    for m in cfg.get("manual_only", []):
        print("  %-24s %s" % (m["id"], m["rule"]))
    print("")
    if not hits:
        print("PASS: no do-not-cite item in %s" % scope)
        return 0
    print("HITS (%d)" % len(hits))
    for h in hits:
        print("  %s  %s:%d" % (h["id"], h["path"], h["line"]))
        print("      matched: %r" % h["match"])
        print("      %s" % h["text"])
        print("      why:     %s" % h["why"])
        print("      instead: %s" % h["instead"])
        print("")
    print("FAIL: %d do-not-cite hits" % len(hits))
    return 1


if __name__ == "__main__":
    sys.exit(main())
