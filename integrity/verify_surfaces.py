#!/usr/bin/env python3
"""verify_surfaces.py - re-derive every public surface and compare it to what
that surface actually says.

Why this exists. Three incidents share one shape: a guard or a public surface
reporting success without a non-empty, tip-locked inspection of the thing it
certifies.

  1. A counts workflow that had never once executed. Green badge, zero runs.
  2. A build workflow red from birth, so the generated page it was supposed to
     keep fresh was whatever a human last committed by hand.
  3. The site drifting every time main moved, because nothing compared the
     page against the tree it describes.

Two of those were cross-repo staleness: one repo writes a number in prose and
another repo parses it. That is an interface, and it was being maintained as
prose.

The rules that fall out, and they are the whole design:

  * A surface that inspected NOTHING is a failure. Zero inspected is the
    signature of every incident above.
  * A derived value that disagrees with the committed artifact is a failure.
  * A peer repo that is absent is a FAILURE, not a skip. "I could not look"
    reported as green is the same defect one level up, and it is exactly how
    incident 1 stayed invisible.

Usage:
    python3 integrity/verify_surfaces.py [--root .] [--peer bbio=/path] [--github]

Exit 0 clean, 1 on any failure.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORDNUM = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
           "eight": 8, "nine": 9, "ten": 10}


def read(p):
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def as_int(tok):
    if tok.isdigit():
        return int(tok)
    return WORDNUM.get(tok.lower())


# ---- derivations: every one counts something in the tree, from the tree ----

def derive_entries(root):
    n = 0
    d = os.path.join(root, "traps")
    for cat in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = os.path.join(d, cat)
        if os.path.isdir(p):
            n += len([f for f in os.listdir(p) if f.endswith(".md")])
    return n


def derive_trap_paths(root):
    t = read(os.path.join(root, "doctor", "minefield_doctor.py"))
    m = re.search(r"TRAP_PATHS\s*=\s*\{(.*?)\n\}", t, re.S)
    if not m:
        return None
    return len(re.findall(r'"\d{2,}"\s*:', m.group(1)))


def derive_playbooks(root):
    d = os.path.join(root, "playbooks")
    if not os.path.isdir(d):
        return None
    return len([f for f in os.listdir(d)
                if f.endswith(".md") and f != "README.md"])


DERIVERS = {"entries": derive_entries,
            "trap_paths": derive_trap_paths,
            "playbooks": derive_playbooks}


def head_sha(root):
    r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--peer", action="append", default=[],
                    help="name=path, e.g. bbio=../Blackwellboy.github.io")
    ap.add_argument("--github", action="store_true")
    ap.add_argument("--peer-mode", choices=("gate", "defer"), default="gate",
                    help="gate: peer value lag fails (scheduled runs). "
                         "defer: peer value lag is reported and does not fail "
                         "(push-time runs). Structural peer problems, a missing "
                         "peer or an artifact that inspects nothing, fail in "
                         "BOTH modes: absent is not stale.")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    peers = {}
    for spec in a.peer:
        if "=" in spec:
            k, v = spec.split("=", 1)
            peers[k.strip()] = os.path.abspath(v.strip())

    cfg = json.loads(read(os.path.join(HERE, "surfaces.json")))
    fails, inspected, deferred = [], 0, []
    SCHEDULED_JOB = "the 'surfaces' workflow (.github/workflows/surfaces.yml)"
    out = ["verify-public-surfaces: %s" % root,
           "HEAD: %s" % (head_sha(root) or "unknown"), ""]

    for s in cfg["surfaces"]:
        art = os.path.join(root, s["artifact"])
        if not os.path.exists(art):
            fails.append("%s: artifact %s is missing" % (s["id"], s["artifact"]))
            continue
        want = DERIVERS[s["derive"]](root)
        if want is None:
            fails.append("%s: could not derive from the tree" % s["id"])
            continue
        found = re.findall(s["pattern"], read(art))
        if not found:
            fails.append("%s: pattern matched NOTHING in %s. A surface that "
                         "inspects nothing cannot certify anything"
                         % (s["id"], s["artifact"]))
            continue
        for tok in found:
            inspected += 1
            got = as_int(tok)
            if got != want:
                fails.append("%s: %s says %s, tree derives %d"
                             % (s["id"], s["artifact"], tok, want))
        out.append("  %-24s %s says %s, tree derives %d  (%d occurrence(s))"
                   % (s["id"], s["artifact"], found[0], want, len(found)))

    for s in cfg["peer_surfaces"]:
        name = s["peer"]
        # A missing peer is a FAILURE. This is the rule the whole file exists
        # for: a check that could not look is not a check that passed.
        if name not in peers:
            fails.append("%s: peer %r was not supplied, so this surface was "
                         "NOT inspected. That is a failure, not a skip: an "
                         "uninspected surface reported green is the defect "
                         "this job exists to catch" % (s["id"], name))
            continue
        art = os.path.join(peers[name], s["artifact"])
        if not os.path.exists(art):
            fails.append("%s: peer artifact %s is missing" % (s["id"], art))
            continue
        found = re.findall(s["pattern"], read(art))
        if not found:
            fails.append("%s: pattern matched NOTHING in the peer artifact"
                         % s["id"])
            continue
        inspected += len(found)
        if s.get("assert") == "equals_head":
            h = head_sha(root)
            for tok in found:
                if not (h and h.startswith(tok)):
                    msg = ("%s: site pins registry %s, HEAD is %s. The page "
                           "describes a tree that has moved"
                           % (s["id"], tok, (h or "unknown")[:12]))
                    (deferred if a.peer_mode == "defer" else fails).append(msg)
            out.append("  %-24s pins %s, HEAD %s" % (s["id"], found[0], (h or "?")[:12]))
        else:
            want = DERIVERS[s["derive"]](root)
            for tok in found:
                if as_int(tok) != want:
                    msg = ("%s: site says %s, tree derives %d"
                           % (s["id"], tok, want))
                    (deferred if a.peer_mode == "defer" else fails).append(msg)
            out.append("  %-24s site says %s, tree derives %d"
                       % (s["id"], found[0], want))

    out.append("")
    if deferred:
        out.append("DEFERRED: checked on schedule, not here. %d peer surface(s) "
                   "lag the tree. This does NOT gate the push." % len(deferred))
        for d in deferred:
            out.append("  " + d)
        out.append("  Where this IS checked: %s, which runs the same job with "
                   "--peer-mode gate and hard-fails." % SCHEDULED_JOB)
        out.append("  A peer that is ABSENT still fails here. Only value lag "
                   "defers, because the site rebuilds after the push that moves "
                   "HEAD and cannot have caught up at push time.")
        out.append("")
    out.append("inspected_count: %d" % inspected)
    if inspected == 0:
        fails.append("inspected_count is 0. Nothing was actually looked at, "
                     "so a clean result here would certify nothing. This is "
                     "the exact shape of the counts workflow that never ran.")

    if fails:
        out.append("")
        out.append("FAIL: %d finding(s)" % len(fails))
        for f in fails:
            out.append("  " + f)
            if a.github:
                print("::error title=surfaces::%s" % f)
    else:
        out.append("CLEAN: %d surface occurrence(s) re-derived and matched%s"
                   % (inspected,
                      (", %d deferred to %s" % (len(deferred), SCHEDULED_JOB))
                      if deferred else ""))
    print("\n".join(out))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()