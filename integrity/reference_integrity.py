#!/usr/bin/env python3
"""reference_integrity.py - the routing surfaces must agree with the tree.

WHY THIS EXISTS
---------------
registry_integrity.py checks entries thoroughly and checks a HARD-CODED list
of nine surfaces for broken links. Everything else that references entries by
number is unchecked: CORE.md, the four playbooks, the five stack pages, the
per-model page, and every mining note. Those files cite trap numbers
constantly, and a renumber or a retitle can leave them pointing at nothing
with a green run.

That is the same failure shape as a correction landing on one surface while
another keeps teaching the old thing. The fix is the same: assert it.

WHAT IT ASSERTS
---------------
  REF-EXISTS      every relative markdown link in EVERY tracked .md resolves
                  on disk, not just in the nine files the older checker knows
  REF-NUMBER      a link whose visible label is a bare [NN] points at a file
                  named NN-*.md, so a renumber cannot leave the text saying 42
                  while the href goes to 43
  ROUTING-ID      every trap id cited on a routing surface (CORE, playbooks,
                  stacks, models) resolves to an entry that exists. This is
                  the REVERSE of registry_integrity's INDEX check, which only
                  asserts entry -> index and never index -> entry
  STATUS-LEAD     the leading vocabulary stem in a surface's status cell
                  matches the leading stem of the entry's own Status line

WHAT IT DELIBERATELY DOES NOT ASSERT, AND WHY
---------------------------------------------
Full status agreement. Two earlier attempts are recorded in integrity/README.md
because both were wrong in instructive ways: matching the first bold-delimited
span truncates every compound status, and matching the whole status paragraph
fires on NEGATED mentions ("which is why this is not 'reproduced here'"),
producing 26 findings of which 25 were honest entries. The leading stem is the
primary label; everything after it is qualifier prose this check does not read.
A guard that fires on two dozen good entries gets waved through, which is worse
than no guard.

Usage:
    python3 integrity/reference_integrity.py [--root .] [--github]

Exit 0 clean, 1 on any finding.
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
ENTRY_FILE = re.compile(r"^(\d{2,})-.+\.md$")
STATUS_START = re.compile(r"^\*\*Status:.*", re.M)
BARE_ID = re.compile(r"^(\d{2,})$")

# Same skip rule registry_integrity uses for repo-relative GitHub namespaces:
# these are correct links with no on-disk target.
GH_NS = re.compile(r"^(?:\.\./)+(issues|pull|pulls|compare|wiki|releases"
                   r"|discussions|security)(/|$)")

STEMS = ["reproduced here", "contributor-measured", "reported by others",
         "measured here, raw not published", "under test"]

# Surfaces that route readers to entries by number. Each is (path, id-column,
# status-column or None). A status column of None means ids are checked for
# existence but no status comparison is made, because the surface does not
# restate a status.
ROUTING_TABLES = [
    ("README.md", 2, 3),
    ("CORE.md", 0, 1),
]
ROUTING_DIRS = ["playbooks", "stacks", "models", "mining"]


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def gha(level, message, path=None, line=None, title=None, root=None):
    def esc(v):
        return (str(v).replace("%", "%25").replace("\r", "%0D")
                .replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C"))
    props = []
    if path:
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
        self.check, self.where, self.message = check, where, message

    def __str__(self):
        return "%-12s %-56s %s" % (self.check, self.where, self.message)


def tracked_md(root):
    """Tracked .md files. Falls back to a walk when git is unavailable, so the
    checker still works on an exported tree."""
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "*.md"],
                             capture_output=True, text=True, timeout=60)
        files = [p for p in out.stdout.splitlines() if p.strip()]
        if files:
            return sorted(files)
    except Exception:
        pass
    files = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
        for f in fn:
            if f.endswith(".md"):
                files.append(os.path.relpath(os.path.join(dp, f), root))
    return sorted(files)


def collect_entries(root):
    """{id: relpath} for real entries. Flat traps/NN-*.md are redirect stubs
    and are not entries, which is the counting rule stated once in
    registry_integrity and not restated differently here."""
    entries = {}
    traps = os.path.join(root, "traps")
    if not os.path.isdir(traps):
        return entries
    for name in sorted(os.listdir(traps)):
        full = os.path.join(traps, name)
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            m = ENTRY_FILE.match(f)
            if m:
                entries[m.group(1)] = "traps/%s/%s" % (name, f)
    return entries


def lead_stem(text):
    t = re.sub(r"\s+", " ", (text or "").replace("**", "")).strip().lower()
    hits = [(t.index(s), s) for s in STEMS if s in t]
    return min(hits)[1] if hits else None


def entry_lead(root, rel):
    m = STATUS_START.search(read(os.path.join(root, rel)))
    if not m:
        return None
    para = read(os.path.join(root, rel))[m.start():].split("\n\n", 1)[0]
    return lead_stem(para)


def links_in(text):
    """(label, target, lineno) for every in-repo relative link."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for label, target in MD_LINK.findall(line):
            t = target.split(" ")[0].strip()
            if t.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if "?" in t or GH_NS.match(t):
                continue
            out.append((label, t, i))
    return out


def check_links_and_numbers(root, findings):
    for rel in tracked_md(root):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        base = os.path.dirname(path)
        for label, target, ln in links_in(read(path)):
            clean = target.split("#")[0]
            if not clean:
                continue
            resolved = os.path.normpath(os.path.join(base, clean))
            if not os.path.exists(resolved):
                findings.append(Finding(
                    "REF-EXISTS", "%s:%d" % (rel, ln),
                    "broken relative link -> %s" % target))
                continue
            m = BARE_ID.match(label.strip())
            if m and clean.endswith(".md"):
                fn = os.path.basename(clean)
                fid = re.match(r"^(\d{2,})-", fn)
                if fid and fid.group(1) != m.group(1):
                    findings.append(Finding(
                        "REF-NUMBER", "%s:%d" % (rel, ln),
                        "label [%s] points at %s: the text and the href "
                        "disagree, which is what a renumber leaves behind"
                        % (m.group(1), fn)))


def routing_surfaces(root):
    """Every routing surface: the two id/status tables plus every .md under
    the routing directories."""
    out = list(ROUTING_TABLES)
    for d in ROUTING_DIRS:
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for dp, dn, fn in os.walk(full):
            dn[:] = [x for x in dn if x not in (".git", "__pycache__")]
            for f in sorted(fn):
                if not f.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(dp, f), root)
                if not any(rel == t[0] for t in out):
                    out.append((rel, None, None))
    return out


def check_routing_ids(root, entries, findings):
    """Every trap id cited on a routing surface must exist. This is the
    direction registry_integrity does not check: it asserts every entry
    appears in the index, never that every id in the index is an entry."""
    for rel, _idcol, _st in routing_surfaces(root):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        for label, target, ln in links_in(read(path)):
            clean = target.split("#")[0]
            fn = os.path.basename(clean)
            m = ENTRY_FILE.match(fn)
            if not m:
                continue
            if "traps/" not in clean.replace("\\", "/"):
                continue
            tid = m.group(1)
            if tid not in entries:
                findings.append(Finding(
                    "ROUTING-ID", "%s:%d" % (rel, ln),
                    "cites trap %s, which is not an entry in the tree" % tid))


def parse_table(path, idcol, statuscol):
    rows = {}
    for i, line in enumerate(read(path).splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= max(idcol, statuscol):
            continue
        m = re.search(r"\[(\d{2,})[,\]]", cells[idcol])
        if m:
            rows[m.group(1)] = (cells[statuscol], i)
    return rows


def check_status_lead(root, entries, findings):
    for rel, idcol, statuscol in ROUTING_TABLES:
        path = os.path.join(root, rel)
        if not os.path.exists(path) or statuscol is None:
            continue
        for tid, (cell, ln) in sorted(parse_table(path, idcol, statuscol).items()):
            if tid not in entries:
                continue
            surface, entry = lead_stem(cell), entry_lead(root, entries[tid])
            if entry is None or surface is None:
                continue
            if surface != entry:
                findings.append(Finding(
                    "STATUS-LEAD", "%s:%d" % (rel, ln),
                    "trap %s leads %r here but %r in the entry itself"
                    % (tid, surface, entry)))


# ---------------------------------------------------------------------------
# The status vocabulary is defined in one file and restated in several, which
# is a drift class rather than a one-off bug. The PR template shipped for weeks
# teaching three labels out of five, missing exactly the two an external
# contribution needs, and that is the documentation bug that made the
# registry's first external contribution arrive mislabelled. CONTRIBUTING was
# corrected; the template that taught the wrong set was not, because nothing
# asserted the two agree.
#
# CONTRIBUTING.md's Status vocabulary table is canonical. Everything below
# compares against what is parsed out of it, so adding a sixth label there
# breaks every stale restatement instead of silently diverging from them.
VOCAB_HEADING = re.compile(r"^##+\s+Status vocabulary\s*$", re.M)
VOCAB_ROW = re.compile(r"^\|\s*\*\*([^*|]+)\*\*\s*\|", re.M)
VOCAB_MARKER = "status-vocabulary: full-set"
CANON_FILE = "CONTRIBUTING.md"


def tracked_text(root):
    """Tracked .md, .yml and .yaml. The forms under .github are yaml and can
    restate the vocabulary as easily as a markdown page can."""
    out = []
    for rel in tracked_md(root):
        out.append(rel)
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "*.yml", "*.yaml"],
                           capture_output=True, text=True, timeout=60)
        out += [p for p in r.stdout.splitlines() if p.strip()]
    except Exception:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
            for f in fn:
                if f.endswith((".yml", ".yaml")):
                    out.append(os.path.relpath(os.path.join(dp, f), root))
    return sorted(set(out))


def canonical_labels(root):
    """The closed set, read out of CONTRIBUTING's table. Returns [] when the
    heading or the table is missing, which is itself reported rather than
    quietly treated as 'no labels to check'."""
    path = os.path.join(root, CANON_FILE)
    if not os.path.exists(path):
        return []
    text = read(path)
    m = VOCAB_HEADING.search(text)
    if not m:
        return []
    section = text[m.end():]
    nxt = re.search(r"^##\s+", section, re.M)
    if nxt:
        section = section[:nxt.start()]
    return [lab.strip().lower() for lab in VOCAB_ROW.findall(section)]


# A stack page must declare whether we have measured on that stack, in a form a
# machine can read. This exists because the public site rendered "11 serving
# stacks measured first-hand" the first time its generator ran: the count of
# stack PAGES was correct and the label around it was false, because six of the
# eleven are pages about stacks we have not touched. They said so in their own
# prose, in two different phrasings, so nothing could derive the true number and
# the fix at the time was to weaken the label to "covered".
#
# The marker restores the stronger claim by making it checkable. Deriving it
# from prose instead would be a regex asserting something the tree does not
# declare, which is the failure this file exists to catch.
STACK_MARKER_RE = re.compile(r"^\*\*Measured here:\*\* (yes|no)\b", re.M)


def check_stack_markers(root, findings):
    d = os.path.join(root, "stacks")
    if not os.path.isdir(d):
        return
    for fn_ in sorted(os.listdir(d)):
        if not fn_.endswith(".md") or fn_ == "README.md":
            continue
        rel = "stacks/" + fn_
        m = STACK_MARKER_RE.search(read(os.path.join(d, fn_)))
        if not m:
            findings.append(Finding(
                "STACK-MARKER", rel,
                "no '**Measured here:** yes|no' line. Every stack page must "
                "declare first-hand status in a form the site generator can "
                "read, so a page count is never rendered as a measurement "
                "count"))


def check_vocabulary(root, findings):
    canon = canonical_labels(root)
    if not canon:
        findings.append(Finding(
            "VOCAB-DEFN", CANON_FILE,
            "no parsable Status vocabulary table; the canonical closed set "
            "cannot be read, so nothing downstream can be checked against it"))
        return
    if len(set(canon)) != len(canon):
        findings.append(Finding("VOCAB-DEFN", CANON_FILE,
                                "duplicate label in the canonical table"))
    canon_set = set(canon)

    # The stem list this checker uses for STATUS-LEAD is itself a restatement.
    for stem in STEMS:
        if not any(lab.startswith(stem) for lab in canon_set):
            findings.append(Finding(
                "VOCAB-DEFN", "integrity/reference_integrity.py",
                "STEMS carries %r, which leads no canonical label" % stem))
    for lab in sorted(canon_set):
        if not any(lab.startswith(s) for s in STEMS):
            findings.append(Finding(
                "VOCAB-DEFN", "integrity/reference_integrity.py",
                "canonical label %r is led by no stem in STEMS, so "
                "STATUS-LEAD cannot see it" % lab))

    # The gate enforces the set at runtime. If its list and the published
    # table disagree, one of them is lying to a contributor.
    #
    # Read from --root by TEXT, not by import. Importing resolves to whichever
    # copy of the module is on sys.path, which is this checker's own directory
    # and not the tree being checked; the mutation suite caught that by
    # planting a divergence in a copied tree and watching nothing fire.
    gate_rel = os.path.join("integrity", "contradiction_gate.py")
    gate_path = os.path.join(root, gate_rel)
    if not os.path.exists(gate_path):
        findings.append(Finding("VOCAB-GATE", gate_rel, "file is missing"))
    else:
        m = re.search(r"^LABELS\s*=\s*\[(.*?)\]", read(gate_path),
                      re.S | re.M)
        if not m:
            findings.append(Finding("VOCAB-GATE", gate_rel,
                                    "no parsable LABELS list"))
        else:
            gate = set(s.lower().strip() for s in
                       re.findall(r'"([^"]+)"|\'([^\']+)\'', m.group(1))
                       for s in (s[0] or s[1],))
            for lab in sorted(canon_set - gate):
                findings.append(Finding(
                    "VOCAB-GATE", gate_rel,
                    "LABELS is missing canonical label %r" % lab))
            for lab in sorted(gate - canon_set):
                findings.append(Finding(
                    "VOCAB-GATE", gate_rel,
                    "LABELS carries %r, which is not in the canonical table"
                    % lab))

    # Two ways a surface restates the set. The marker is the opt-in for prose
    # and tables; the slash form is the shape the PR template actually had,
    # and it is caught whether or not anyone remembered the marker.
    alt = "|".join(re.escape(l) for l in
                   sorted(canon_set, key=len, reverse=True))
    slash = re.compile(r"(?:%s)(?:\s*/\s*(?:%s))+" % (alt, alt))
    for rel in tracked_text(root):
        if rel == CANON_FILE:
            continue
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        text = read(path)
        low = text.lower()
        # A restatement is prose and wraps: MAINTAINING carries
        # "contributor-measured, conditions as\n   reported", which is the
        # label present and correct. Collapse whitespace before testing
        # containment, or the check reports a missing label that is there and
        # a maintainer learns to wave it through.
        flat = re.sub(r"\s+", " ", low)
        idx = low.find(VOCAB_MARKER)
        if idx >= 0:
            # Scope to the marked REGION, marker to the next heading, not to
            # the whole file. MAINTAINING names every label again in its
            # status-transitions section, so a file-wide containment test
            # passes even after a label is deleted from the enumeration
            # itself. That is the drift this check exists to catch, and the
            # first version of it could not see it.
            region = low[idx:]
            nxt = re.search(r"^#{1,6}\s", region, re.M)
            if nxt:
                region = region[:nxt.start()]
            region = re.sub(r"\s+", " ", region)
            missing = sorted(l for l in canon_set if l not in region)
            if missing:
                findings.append(Finding(
                    "VOCAB-FULL", rel,
                    "declares the full status vocabulary but the marked "
                    "region omits: %s" % "; ".join(repr(m) for m in missing)))
        for i, line in enumerate(low.splitlines(), 1):
            m = slash.search(line)
            if not m:
                continue
            if all(l in flat for l in canon_set):
                continue
            missing = sorted(l for l in canon_set if l not in flat)
            findings.append(Finding(
                "VOCAB-SLASH", "%s:%d" % (rel, i),
                "enumerates the vocabulary as %r but the file never mentions: "
                "%s" % (m.group(0), "; ".join(repr(x) for x in missing))))


def run(root):
    findings = []
    entries = collect_entries(root)
    check_links_and_numbers(root, findings)
    check_routing_ids(root, entries, findings)
    check_status_lead(root, entries, findings)
    check_vocabulary(root, findings)
    check_stack_markers(root, findings)
    return findings, len(entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--github", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(args.root))

    findings, n = run(root)

    if args.github:
        for f in findings:
            w = f.where.split(":")
            ln = int(w[1]) if len(w) > 1 and w[1].isdigit() else None
            gha("error", "%s: %s" % (f.where, f.message),
                os.path.join(root, w[0]), ln,
                "reference integrity: %s" % f.check)

    print("reference integrity: %s" % root)
    print("  entries: %d   markdown files scanned: %d"
          % (n, len(tracked_md(root))))
    if not findings:
        print("  CLEAN: no broken links, no dangling trap ids, no status "
              "disagreement on a routing surface")
        return 0
    print("")
    by = {}
    for f in findings:
        by.setdefault(f.check, []).append(f)
    for check in sorted(by):
        print("%s (%d)" % (check, len(by[check])))
        for f in by[check]:
            print("  %-56s %s" % (f.where, f.message))
        print("")
    print("FAIL: %d findings" % len(findings))
    return 1


if __name__ == "__main__":
    sys.exit(main())
