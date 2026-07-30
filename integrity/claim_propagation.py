#!/usr/bin/env python3
"""claim_propagation.py - flag any surface still carrying a retracted or
corrected claim.

This is the check for the failure that cost the most: a correction lands in
one place and another surface keeps teaching the old thing. It happened with
the depth claim (retracted in the study, then found surviving in the operator
advice four lines below its own correction), with the field-name scoping, and
with the trap 42 capability reading.

It cannot police prose. It does not try. It greps for the distinctive
phrasings recorded WITH each retraction, and the ledger validator refuses any
retraction that did not record them. That requirement is the actual fix: a
retraction is not complete until its search terms are written down.

Three verdicts per hit:

  FLAGGED   the superseded wording, with no correction marker anywhere in the
            context window. This is the failure. Exit 1.
  CONTEXT   the superseded wording with a correction attached nearby, which is
            this project's visible-corrections convention working correctly.
            Printed every run, never hidden, never fatal.
  EXEMPT    a path the ledger records as carrying the old wording on purpose:
            a verbatim archive of what was posted, or the retraction record
            itself, which has to quote what it retracts.

Remote surfaces (upstream comments, third-party guides that cite us) cannot be
edited from here and are not fetched by default. They are printed as MANUAL
every run with their URL and the phrasing to look for, so they cannot quietly
fall off the list.

Usage:
    python3 integrity/claim_propagation.py --repo minefield=. --repo laguna=../laguna-s21-lab
    python3 integrity/claim_propagation.py --repo laguna=. --ledger ../model-serving-minefield/integrity/claims.json

Exit 0 clean, 1 on a FLAGGED hit or an invalid ledger, 3 if the run
scanned no files at all. A bare run with no --repo defaults to the
repo this file lives in, and never reports PASS over nothing.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LEDGER = os.path.join(HERE, "claims.json")

# .html is here because the most public surface we own is a single-page site
# (Blackwellboy.github.io/index.html) and it is not markdown. Scanning only
# .md and .txt meant the ledger could be pointed at that repo and return a
# confident CLEAN having read nothing but its README: a false CLEAN on the
# surface that carried a retracted claim for a day longer than any other.
SCAN_EXTS = (".md", ".txt", ".html")
SKIP_DIRS = {".git", "__pycache__", "node_modules", "_proofs", "_proof_archive"}

ENFORCED_STATES = {"retracted", "corrected", "scope-limited"}


def console_safe(value, encoding=None):
    """Render evidence without crashing a legacy Windows console."""
    encoding = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return str(value).encode(
        encoding, errors="backslashreplace"
    ).decode(encoding)


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


def validate_ledger(ledger):
    """The rule that makes the rest of this work. Returns a list of errors."""
    errs = []
    seen = set()
    for c in ledger.get("claims", []):
        cid = c.get("id")
        if not cid:
            errs.append("a claim has no id")
            continue
        if cid in seen:
            errs.append("%s: duplicate claim id" % cid)
        seen.add(cid)
        state = c.get("state")
        if state not in ENFORCED_STATES | {"current"}:
            errs.append("%s: unknown state %r" % (cid, state))
        if state in ENFORCED_STATES:
            phr = c.get("search_phrasings") or []
            if not phr:
                errs.append(
                    "%s: state is %r but no search_phrasings recorded. A "
                    "retraction is not complete until its search terms are "
                    "written down." % (cid, state))
            for p in phr:
                if not p.get("pattern"):
                    errs.append("%s: a search phrasing has no pattern" % cid)
                if not p.get("note"):
                    errs.append("%s: phrasing %r has no note saying what it "
                                "looks for" % (cid, p.get("pattern")))
                try:
                    re.compile(p.get("pattern", ""))
                except re.error as e:
                    errs.append("%s: phrasing %r does not compile: %s"
                                % (cid, p.get("pattern"), e))
            if not c.get("superseded_by"):
                errs.append("%s: no superseded_by: the reader is told the old "
                            "form is wrong and not what is right" % cid)
            if not c.get("authority"):
                errs.append("%s: no authority: nothing says where the "
                            "retraction is on record" % cid)
        if state == "scope-limited" and not c.get("requires_near"):
            errs.append("%s: scope-limited with no requires_near, so no hit "
                        "could ever be judged acceptable" % cid)
        if state in ("retracted", "corrected") and not c.get("correction_anchors"):
            errs.append(
                "%s: no correction_anchors. Without them any correction "
                "anywhere in the window vouches for this claim, including a "
                "correction about something else entirely, which is how a "
                "surviving claim gets scored as corrected." % cid)
    return errs


def marker_is_about_claim(lines, marker_idx, anchors, radius=6):
    """A correction marker only counts if the correction is about THIS claim.

    Found the hard way: the lab README's uncorrected Qwen dose-depth paragraph
    was scored as corrected because an unrelated PR-10 correction sat 30 lines
    below it. A marker now has to sit next to something that names the claim.
    """
    lo = max(0, marker_idx - radius)
    hi = min(len(lines), marker_idx + radius + 1)
    blob = "\n".join(lines[lo:hi])
    return any(a.search(blob) for a in anchors)


def surface_repo_path(surface):
    if ":" in surface:
        repo, rest = surface.split(":", 1)
        return repo, rest
    return None, surface


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


def walk_files(root, pruned=None):
    pruned = pruned if pruned is not None else []
    for dp, dns, fns in os.walk(root):
        prune_nested_repos(dp, dns, pruned)
        for fn in sorted(fns):
            if fn.endswith(SCAN_EXTS):
                yield os.path.join(dp, fn)


class Hit(object):
    def __init__(self, verdict, claim, repo, rel, lineno, pattern, line, why=""):
        self.verdict = verdict
        self.claim = claim
        self.repo = repo
        self.rel = rel
        self.lineno = lineno
        self.pattern = pattern
        self.line = line.strip()
        self.why = why

    def as_dict(self):
        return {"verdict": self.verdict, "claim": self.claim, "repo": self.repo,
                "path": self.rel, "line": self.lineno, "pattern": self.pattern,
                "text": self.line[:200], "why": self.why}


def scan(ledger, repos):
    win = ledger.get("context_window", {"before": 8, "after": 30})
    markers = re.compile("|".join(re.escape(m) for m in ledger["correction_markers"]),
                         re.I)
    hits = []
    manual = []
    pruned = []

    for claim in ledger["claims"]:
        state = claim.get("state")
        if state not in ENFORCED_STATES:
            continue
        pats = [(p["pattern"], re.compile(p["pattern"], re.I), p["note"])
                for p in claim["search_phrasings"]]
        near = [(q["pattern"], re.compile(q["pattern"], re.I))
                for q in claim.get("requires_near", [])]
        anchors = [re.compile(a, re.I) for a in claim.get("correction_anchors", [])]
        exempts = []
        for e in claim.get("exempt_paths", []):
            repo, rest = surface_repo_path(e["surface"])
            exempts.append((repo, rest, e["reason"]))

        for repo_name, root in repos.items():
            for path in walk_files(root, pruned):
                rel = os.path.relpath(path, root).replace("\\", "/")
                lines = read(path).splitlines()
                ex_reason = None
                for erepo, erest, ereason in exempts:
                    if erepo not in (None, repo_name):
                        continue
                    if rel == erest or rel.startswith(erest.rstrip("/") + "/"):
                        ex_reason = ereason
                        break
                for i, line in enumerate(lines):
                    for raw, rx, note in pats:
                        if not rx.search(line):
                            continue
                        lo = max(0, i - win["before"])
                        hi = min(len(lines), i + win["after"] + 1)
                        window = "\n".join(lines[lo:hi])
                        if ex_reason:
                            v, why = "EXEMPT", ex_reason
                        elif state == "scope-limited":
                            if any(rx2.search(window) for _, rx2 in near):
                                v, why = "CONTEXT", "scope qualifier present in window"
                            else:
                                v, why = "FLAGGED", ("no scope qualifier within "
                                                     "%d/%d lines" % (win["before"], win["after"]))
                        else:
                            ok = None
                            for j in range(lo, hi):
                                if markers.search(lines[j]) and marker_is_about_claim(
                                        lines, j, anchors):
                                    ok = j + 1
                                    break
                            if ok:
                                v, why = "CONTEXT", ("correction about this claim at "
                                                     "line %d" % ok)
                            else:
                                v, why = "FLAGGED", (
                                    "no correction ABOUT THIS CLAIM within %d/%d "
                                    "lines (a correction about something else does "
                                    "not count)" % (win["before"], win["after"]))
                        hits.append(Hit(v, claim["id"], repo_name, rel, i + 1,
                                        raw, line, why))

        for r in claim.get("remote_surfaces", []):
            manual.append({"claim": claim["id"], "url": r["url"],
                           "what": r.get("what", ""), "state": r.get("state", ""),
                           "phrasings": [p["pattern"] for p in claim["search_phrasings"]]})

    return hits, manual, sorted(set(pruned))


def check_carried_by(ledger, repos):
    """A surface listed in the ledger that no longer exists is a stale ledger.
    That is the same failure class the ledger exists to catch, one level up."""
    errs = []
    for claim in ledger["claims"]:
        for s in claim.get("carried_by", []):
            repo, rest = surface_repo_path(s["surface"])
            if repo not in repos:
                continue
            if not os.path.exists(os.path.join(repos[repo], rest)):
                errs.append("%s: carried_by surface does not exist: %s"
                            % (claim["id"], s["surface"]))
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--repo", action="append", default=[],
                    help="name=path, repeatable. Names must match the ledger's "
                         "repos block. Repos you do not pass are simply not "
                         "scanned, and the run says so.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--github", action="store_true",
                    help="also emit GitHub Actions annotations")
    args = ap.parse_args()

    ledger = json.loads(read(args.ledger))
    repos = {}
    for spec in args.repo:
        name, _, path = spec.partition("=")
        repos[name] = os.path.abspath(os.path.expanduser(path))

    if not repos:
        # A bare run used to scan nothing and print PASS. It now defaults to
        # the repo this checker lives in, and says so, so that the default is
        # visible rather than assumed.
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repos["minefield"] = here
        if not args.json:
            print("NOTE: no --repo given, so this run defaults to the repo "
                  "this checker lives in: minefield=%s" % here)
            print("      Pass --repo explicitly to scan a peer repo as well. "
                  "Repos you do not pass are not scanned.")
            print("")

    # Inventory of what this run can actually open. Computed here rather than
    # inside scan() so that scan() keeps its signature and its own tests.
    scanned = {n: sum(1 for _ in walk_files(r, pruned=[]))
               for n, r in repos.items()}

    errs = validate_ledger(ledger)
    if errs:
        print("LEDGER INVALID")
        for e in errs:
            print("  %s" % e)
            if args.github:
                gha("error", e, os.path.abspath(args.ledger), None,
                    "claims ledger invalid")
        return 1
    errs = check_carried_by(ledger, repos)

    hits, manual, pruned = scan(ledger, repos)
    flagged = [h for h in hits if h.verdict == "FLAGGED"]

    # The empty-set guard. This project's own check contract names "a PASS
    # over an empty comparison set" as a defect shape, and this tool had it:
    # with no --repo, or with a --repo path holding no scannable file, every
    # loop in scan() is empty, nothing is FLAGGED, and the run printed PASS
    # and exited 0. A clean result over nothing is not a clean result, so it
    # is now an error with its own exit code rather than a pass.
    empty = [n for n, c in scanned.items() if not c]
    scanned_nothing = (not scanned) or bool(empty)

    if args.json:
        print(json.dumps({"hits": [h.as_dict() for h in hits],
                          "manual": manual, "ledger_errors": errs,
                          "scanned": scanned,
                          "scanned_nothing": scanned_nothing}, indent=2))
        if scanned_nothing:
            return 3
        return 1 if (flagged or errs) else 0

    if scanned_nothing:
        for n in (empty or ["<none>"]):
            msg = ("claim propagation scanned 0 files for repo %r (path: %s)"
                   % (n, repos.get(n, "not given")))
            print("REFUSING TO REPORT CLEAN: %s" % msg)
            if args.github:
                gha("error", msg, os.path.abspath(args.ledger), None,
                    "claim propagation scanned nothing")
        print("")
        print("A clean result over an empty set is not a clean result. Exit 3.")
        return 3

    print("SCANNED: %s" % ", ".join("%s=%d files" % (n, scanned[n])
                                    for n in sorted(scanned)))
    print("")

    if args.github:
        for h in hits:
            if h.verdict != "FLAGGED":
                continue
            gha("error",
                "%s still carries the %s claim: /%s/ matched, %s. Correct form: %s"
                % (h.rel, h.claim, h.pattern, h.why,
                   next((c["superseded_by"] for c in ledger["claims"]
                         if c["id"] == h.claim), "see integrity/claims.json")),
                os.path.join(repos.get(h.repo, ""), h.rel), h.lineno,
                "retracted claim still published: %s" % h.claim)
        for e in errs:
            gha("error", e, os.path.abspath(args.ledger), None,
                "claims ledger stale")

    print("claim propagation: %d claims, %d enforced, repos scanned: %s"
          % (len(ledger["claims"]),
             len([c for c in ledger["claims"] if c["state"] in ENFORCED_STATES]),
             ", ".join(sorted(repos)) or "(none)"))
    missing = [r for r in ledger.get("repos", {}) if r not in repos]
    if missing:
        print("  NOT SCANNED this run: %s" % ", ".join(sorted(missing)))
    for pth in pruned:
        print("  PRUNED, nested checkout of another repo: %s" % pth)
    print("")

    for verdict in ("FLAGGED", "CONTEXT", "EXEMPT"):
        group = [h for h in hits if h.verdict == verdict]
        print("%s (%d)" % (verdict, len(group)))
        for h in group:
            print("  %-26s %s:%s:%d" % (h.claim, h.repo, h.rel, h.lineno))
            print("      /%s/  %s" % (h.pattern, h.why))
            print("      %s" % console_safe(h.line[:150]))
        print("")

    print("MANUAL, remote surfaces (%d) - not fetched, check by hand when a "
          "claim changes:" % len(manual))
    for m in manual:
        print("  %-26s %s" % (m["claim"], m["url"]))
        print("      %s [%s]" % (m["what"], m["state"]))
    print("")

    if errs:
        print("LEDGER STALE")
        for e in errs:
            print("  %s" % e)
    if flagged or errs:
        print("FAIL: %d flagged hits, %d ledger errors" % (len(flagged), len(errs)))
        return 1
    print("PASS: no surface carries a retracted claim without its correction")
    return 0


if __name__ == "__main__":
    sys.exit(main())
