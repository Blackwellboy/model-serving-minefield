#!/usr/bin/env python3
"""registry_integrity.py - assert every registry entry is complete and every
stated trap count agrees with the tree.

Why this exists. Three independent audits found the same class of problem: a
correction lands on one surface and another surface keeps teaching the old
thing, a status word means different things in different entries, a count goes
stale in a launch document. Every instance was caught by a human reading
carefully. This file is the part of that reading that a machine can do.

What it asserts, per numbered entry:

  README-ROW       a row in the README "Find your symptom" table
  README-STATUS    that row's status cell is in the allowed vocabulary
  FILE-STATUS      the entry file carries a **Status:** line, in vocabulary
  FOUND-BY         the entry file names its finder on the first lines
  CREDIT           a third-party finder is credited in HALL_OF_FAME.md
  INDEX            the entry appears in models/README.md (per-model or
                   per-stack), unless registry_config.json records why not
  CHANGELOG        the entry is announced in CHANGELOG.md
  LINKS            every relative link in the entry file resolves on disk

And repo-wide:

  STUBS            each flat traps/NN-*.md redirect stub points at a file
                   that exists
  COUNT            every declared registry total agrees with the number of
                   entries in the tree, and every declared doctor-coverage
                   numerator agrees with len(TRAP_PATHS) in the doctor

Counting rule, stated once because getting it wrong is itself a historical
failure: an ENTRY is a file matching traps/<category>/NN-*.md. The seven flat
traps/NN-*.md files are redirect stubs left behind by the category
reorganisation. They are not entries and are never counted.

CHANGELOG.md is deliberately exempt from COUNT. It is an append-only record of
what was true on a date; a 2026-07-28 line reading "corrected to 17 of 42" must
keep saying 42 after the tree grows, or the log stops being a log.

Usage:
    python3 integrity/registry_integrity.py [--root .] [--json]

Exit 0 clean, 1 on any failure.
"""
import argparse
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contradiction_gate as _contradiction

HERE = os.path.dirname(os.path.abspath(__file__))

ENTRY_RE = re.compile(r"^(\d{2})-.+\.md$")
STUB_RE = re.compile(r"^(\d{2})-.+\.md$")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
STATUS_LINE_RE = re.compile(r"^\*\*Status:\s*(.+?)\*\*", re.M)
STATUS_LOOSE_RE = re.compile(r"^\*\*Status:\s*(.+)$", re.M)
FOUND_BY_RE = re.compile(r"^\*\*Found (?:by|and measured by|and reported by)\b", re.M)

# The allowed vocabulary is a closed set, defined once in
# CONTRIBUTING.md#status-vocabulary. It lives in integrity/registry_config.json
# rather than here so that a maintainer changing the vocabulary edits data and
# a doc, not code, and so the COMPOUND check below can assert the config still
# matches CONTRIBUTING.md. Hard-coding it in this file is how the two would
# drift, which is the exact failure class this whole layer exists to stop.
FALLBACK_STATUS_STEMS = [
    "reproduced here",
    "contributor-measured",
    "reported by others",
    "measured here, raw not published",
    "under test",
]


def norm_status(text):
    return text.strip().replace("**", "").strip().lower()


def status_ok(text, stems):
    """A status may be compound: 'A + B', and each part may carry free prose
    after a comma, semicolon or bracket. Every plus-joined part must open with
    an allowed stem; the prose that follows is the qualifier and is free."""
    t = norm_status(text)
    if not t:
        return False
    for part in t.split(" + "):
        part = part.strip()
        if not any(part.startswith(s) for s in stems):
            return False
    return True



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


class Finding(object):
    def __init__(self, check, where, message):
        self.check = check
        self.where = where
        self.message = message

    def __str__(self):
        return "%-14s %-58s %s" % (self.check, self.where, self.message)

    def as_dict(self):
        return {"check": self.check, "where": self.where, "message": self.message}


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def load_config(root):
    path = os.path.join(root, "integrity", "registry_config.json")
    if not os.path.exists(path):
        return {}
    return json.loads(read(path))


def collect_entries(root):
    """Return {id: relpath} for real entries, and {id: relpath} for stubs."""
    entries = {}
    stubs = {}
    traps = os.path.join(root, "traps")
    for name in sorted(os.listdir(traps)):
        full = os.path.join(traps, name)
        if os.path.isdir(full):
            for f in sorted(os.listdir(full)):
                m = ENTRY_RE.match(f)
                if m:
                    entries[m.group(1)] = "traps/%s/%s" % (name, f)
        elif STUB_RE.match(name):
            stubs[STUB_RE.match(name).group(1)] = "traps/%s" % name
    return entries, stubs


def readme_rows(root):
    """Parse the README symptom table into {id: (status_cell, line_no)}."""
    rows = {}
    text = read(os.path.join(root, "README.md"))
    started = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("| You are seeing"):
            started = True
            continue
        if started:
            if not line.startswith("|"):
                if line.strip() == "":
                    continue
                break
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4 or set(cells[0]) <= set("- "):
                continue
            m = re.search(r"\[(\d{2})\]\(traps/", cells[2])
            if m:
                rows[m.group(1)] = (cells[3], i)
    return rows


# GitHub resolves a link like ../../issues/new?template=x.yml against the repo,
# not against the checkout. Those are correct links that have no on-disk target,
# so they are skipped rather than reported. The rule is narrow on purpose: only
# the repo-level GitHub namespaces, and anything carrying a query string.
GH_REPO_RELATIVE_RE = re.compile(
    r"^(?:\.\./)+(issues|pull|pulls|compare|wiki|releases|discussions)(/|$)")


def relative_links(text):
    out = []
    for raw in MD_LINK_RE.findall(text):
        target = raw.split(" ")[0].strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if "?" in target or GH_REPO_RELATIVE_RE.match(target):
            continue
        out.append(target)
    return out


def check_links(root, relpath, findings):
    base = os.path.dirname(os.path.join(root, relpath))
    text = read(os.path.join(root, relpath))
    for target in relative_links(text):
        clean = target.split("#")[0]
        if clean == "":
            continue
        resolved = os.path.normpath(os.path.join(base, clean))
        if not os.path.exists(resolved):
            findings.append(Finding("LINKS", relpath, "broken link -> %s" % target))


# --- count consistency -----------------------------------------------------

TOTAL_PATTERNS = [
    # REGISTRY_TRAP_COUNT = 42
    (re.compile(r"REGISTRY_TRAP_COUNT\s*=\s*(\d+)"), 1, None),
    # "17 of these 42 entries", "17 of this registry's 42 entries",
    # "17 of the registry's 42 numbered entries"
    (re.compile(r"(\d+)\s+of\s+(?:these|this registry's|the registry's)\s+"
                r"\*{0,2}(\d+)\s*(?:numbered\s+)?entries"), 2, 1),
    # "**17 of these 42 entries**" with the bold outside the number
    (re.compile(r"\*\*(\d+)\s+of\s+(?:these|this registry's|the registry's)\s+"
                r"(\d+)\s*(?:numbered\s+)?entries\*\*"), 2, 1),
    # doctor coverage line: "implemented 17/42"
    (re.compile(r"implemented\s+(\d+)\s*/\s*(\d+)"), 2, 1),
    # the same line built in a test f-string: implemented {len(md.TRAP_PATHS)}/42
    (re.compile(r"implemented\s+\{[^}]*\}\s*/\s*(\d+)"), 1, None),
]

# Counts that state neither the total nor the implemented count, but their
# DIFFERENCE. These are the ones that fossilise: "not implemented 25" was
# 42 minus 17 and survived two registry expansions, because every pattern above
# looks for a total and this number is not one. A reader takes it for current
# coverage, which is exactly what it is not.
#
# Asserted as total minus implemented rather than against a literal, so it
# cannot go stale again.
ORPHAN_PATTERNS = [
    re.compile(r"not\s+implemented\s+\*{0,2}(\d+)\*{0,2}\b"),
    re.compile(r"remaining\s+\*{0,2}(\d+)\*{0,2}\s+numbered\s+traps"),
]

COUNT_SCAN_EXTS = (".md", ".py")
COUNT_SKIP_FILES = {"CHANGELOG.md"}
COUNT_SKIP_DIRS = {".git", "__pycache__", "integrity"}


RANGE_RE = re.compile(r"(?:\[)?(\d{2})(?:\][^)]*\))?\s+through\s+(?:\[)?(\d{2})")


def changelog_covered(changelog, cfg):
    """Ids the CHANGELOG announces.

    Three mechanisms, all of them ones the log already uses:
      1. a direct link to the entry file,
      2. a batch announced as a range, "08 through 19", with or without link
         markup on the endpoints,
      3. a prose-only batch line with no ids in it at all, which cannot be
         parsed and must therefore be written down in registry_config.json
         with the line it refers to. That is the whole point: an exemption
         someone had to type is auditable, a silent pass is not.
    """
    covered = set()
    for a, b in RANGE_RE.findall(changelog):
        for n in range(int(a), int(b) + 1):
            covered.add("%02d" % n)
    for rng, _reason in cfg.get("changelog_batches", {}).items():
        a, b = rng.split("-")
        for n in range(int(a), int(b) + 1):
            covered.add("%02d" % n)
    return covered


def doctor_implemented_count(root):
    path = os.path.join(root, "doctor", "minefield_doctor.py")
    if not os.path.exists(path):
        return None
    text = read(path)
    m = re.search(r"TRAP_PATHS\s*=\s*\{(.*?)\n\}", text, re.S)
    if not m:
        return None
    return len(re.findall(r'"\d{2}"\s*:', m.group(1)))


def check_counts(root, n_entries, findings):
    implemented = doctor_implemented_count(root)
    for dp, dns, fns in os.walk(root):
        # Same reason as claim_propagation's prune: a nested checkout is a
        # different repo, and its count sentences are not this repo's to
        # enforce. Without this a peer clone inside the workspace makes the
        # count check argue with a document it does not own.
        dns[:] = [d for d in dns
                  if d not in COUNT_SKIP_DIRS
                  and not os.path.exists(os.path.join(dp, d, ".git"))]
        for fn in sorted(fns):
            if not fn.endswith(COUNT_SCAN_EXTS) or fn in COUNT_SKIP_FILES:
                continue
            rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
            text = read(os.path.join(dp, fn))
            for i, line in enumerate(text.splitlines(), 1):
                for rx, total_g, impl_g in TOTAL_PATTERNS:
                    for m in rx.finditer(line):
                        total = int(m.group(total_g))
                        if total != n_entries:
                            findings.append(Finding(
                                "COUNT", "%s:%d" % (rel, i),
                                "declares registry total %d, tree has %d entries "
                                "(%s)" % (total, n_entries, m.group(0).strip())))
                        if impl_g and implemented is not None:
                            got = int(m.group(impl_g))
                            if got != implemented:
                                findings.append(Finding(
                                    "COUNT", "%s:%d" % (rel, i),
                                    "declares doctor coverage %d, doctor "
                                    "TRAP_PATHS has %d (%s)"
                                    % (got, implemented, m.group(0).strip())))
                if implemented is None:
                    continue
                expected_orphan = n_entries - implemented
                for rx in ORPHAN_PATTERNS:
                    for m in rx.finditer(line):
                        got = int(m.group(1))
                        if got != expected_orphan:
                            findings.append(Finding(
                                "COUNT", "%s:%d" % (rel, i),
                                "declares %d not-implemented, tree has %d "
                                "entries minus %d implemented = %d (%s)"
                                % (got, n_entries, implemented,
                                   expected_orphan, m.group(0).strip())))
    return implemented


# --- main ------------------------------------------------------------------

def run(root):
    findings = []
    cfg = load_config(root)
    index_exempt = cfg.get("index_exempt", {})
    own_finder_names = [n.lower() for n in cfg.get("own_finder_names", ["blackwellboy"])]

    stems = [s.lower() for s in cfg.get("status_stems", FALLBACK_STATUS_STEMS)]
    labels = cfg.get("status_labels", [])

    # The vocabulary is declared canonical in CONTRIBUTING.md. If this config
    # and that document disagree, the check is enforcing a vocabulary nobody
    # documented, which is worse than no check.
    contributing = os.path.join(root, "CONTRIBUTING.md")
    if labels and os.path.exists(contributing):
        ctext = read(contributing).lower()
        for lab in labels:
            if lab.lower() not in ctext:
                findings.append(Finding(
                    "VOCAB", "CONTRIBUTING.md",
                    "status label %r is enforced by integrity/registry_config"
                    ".json but does not appear in CONTRIBUTING.md, which is "
                    "where the closed set is defined" % lab))

    entries, stubs = collect_entries(root)
    rows = readme_rows(root)
    hall = read(os.path.join(root, "HALL_OF_FAME.md"))
    changelog = read(os.path.join(root, "CHANGELOG.md"))
    models_index = read(os.path.join(root, "models", "README.md"))
    cl_covered = changelog_covered(changelog, cfg)

    for tid in sorted(entries):
        rel = entries[tid]
        text = read(os.path.join(root, rel))
        fname = rel.split("/")[-1]

        # README row
        if tid not in rows:
            findings.append(Finding("README-ROW", rel,
                                    "no row in the README symptom table"))
        else:
            cell, lineno = rows[tid]
            if not status_ok(cell, stems):
                findings.append(Finding(
                    "README-STATUS", "README.md:%d" % lineno,
                    "trap %s status cell %r is not in the allowed vocabulary"
                    % (tid, cell)))

        # file status
        m = STATUS_LINE_RE.search(text) or STATUS_LOOSE_RE.search(text)
        if not m:
            findings.append(Finding("FILE-STATUS", rel,
                                    "no **Status:** line in the entry"))
        elif not status_ok(m.group(1), stems):
            findings.append(Finding(
                "FILE-STATUS", rel,
                "status %r is not in the allowed vocabulary"
                % norm_status(m.group(1))[:70]))

        # An entry must not claim more than its own linked files admit.
        for where, why, quote in _contradiction.check(
                os.path.join(root, rel), root, read):
            findings.append(Finding(
                "CONTRADICTION", where,
                "entry claims 'reproduced here' but %s: ...%s..." % (why, quote[:90])))

        # found-by
        head = "\n".join(text.splitlines()[:8])
        if not FOUND_BY_RE.search(head):
            findings.append(Finding("FOUND-BY", rel,
                                    "no **Found by ...** line in the first 8 lines"))
        else:
            finder_block = head
            handles = set(re.findall(r"@[A-Za-z0-9_\-]+", finder_block))
            bare = set(re.findall(r"\bFound by ([A-Z][A-Za-z0-9_]+)", finder_block))
            for h in sorted(handles | bare):
                if h.lower().lstrip("@") in own_finder_names:
                    continue
                if h not in hall:
                    findings.append(Finding(
                        "CREDIT", rel,
                        "finder %s is not credited anywhere in HALL_OF_FAME.md" % h))

        # per-model / per-stack index
        if tid not in index_exempt and fname not in models_index:
            findings.append(Finding(
                "INDEX", rel,
                "not listed in models/README.md and no exemption recorded in "
                "integrity/registry_config.json"))

        # changelog
        if fname not in changelog and tid not in cl_covered:
            findings.append(Finding(
                "CHANGELOG", rel,
                "not announced in CHANGELOG.md: no link to this file, no "
                "range covering trap %s, no recorded batch" % tid))

        check_links(root, rel, findings)

    # stubs
    for tid, rel in sorted(stubs.items()):
        text = read(os.path.join(root, rel))
        targets = relative_links(text)
        if not targets:
            findings.append(Finding("STUBS", rel, "redirect stub links nowhere"))
        for t in targets:
            resolved = os.path.normpath(
                os.path.join(os.path.dirname(os.path.join(root, rel)), t.split("#")[0]))
            if not os.path.exists(resolved):
                findings.append(Finding("STUBS", rel,
                                        "redirect target does not exist -> %s" % t))

    # other surfaces whose links must resolve
    for rel in ["README.md", "CHANGELOG.md", "HALL_OF_FAME.md", "CONTRIBUTING.md",
                "MAINTAINING.md", "models/README.md", "mining/README.md",
                "checks/README.md", "doctor/README.md"]:
        if os.path.exists(os.path.join(root, rel)):
            check_links(root, rel, findings)

    implemented = check_counts(root, len(entries), findings)
    return findings, len(entries), len(stubs), implemented


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--github", action="store_true",
                    help="also emit GitHub Actions annotations, so a red badge "
                         "names the file and the missing thing")
    args = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(args.root))

    findings, n_entries, n_stubs, implemented = run(root)

    if args.json:
        print(json.dumps({
            "entries": n_entries,
            "stubs": n_stubs,
            "doctor_implemented": implemented,
            "findings": [f.as_dict() for f in findings],
        }, indent=2))
        return 1 if findings else 0

    if args.github:
        for f in findings:
            where = f.where.split(":")
            path = os.path.join(root, where[0])
            ln = int(where[1]) if len(where) > 1 and where[1].isdigit() else None
            gha("error", "%s: %s" % (f.where, f.message), path, ln,
                "registry integrity: %s" % f.check)

    print("registry integrity: %s" % root)
    print("  entries counted: %d   redirect stubs (not counted): %d   "
          "doctor TRAP_PATHS: %s" % (n_entries, n_stubs, implemented))
    if not findings:
        print("  CLEAN: %d checks over %d entries, no findings"
              % (8 * n_entries + n_stubs, n_entries))
        return 0
    print("")
    by_check = {}
    for f in findings:
        by_check.setdefault(f.check, []).append(f)
    for check in sorted(by_check):
        print("%s (%d)" % (check, len(by_check[check])))
        for f in by_check[check]:
            print("  %-58s %s" % (f.where, f.message))
        print("")
    print("FAIL: %d findings" % len(findings))
    return 1


if __name__ == "__main__":
    sys.exit(main())
