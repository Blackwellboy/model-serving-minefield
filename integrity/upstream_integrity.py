#!/usr/bin/env python3
"""upstream_integrity.py - the fourth tier has requirements, and they are not
optional.

WHY THIS EXISTS
---------------
`upstream/` publishes material nobody here has reproduced. That is a deliberate
loosening of the registry's central promise, and the only thing that makes it
safe is that every entry names the primary source, the reporter, and the issue
state, and says plainly that we have not run it. Those three facts are the
entire difference between a useful pointer and a rumour with a URL.

A tier whose requirements are honoured by convention decays to a tier of
rumours, because the requirement that gets dropped first is always the one that
was only ever in a document. So they are asserted here, per entry:

  US-STATUS     the entry carries **Status: upstream-reported**, and carries
                NO other tier label. A compound status would let an entry claim
                measurement from inside the unmeasured tier.
  US-PRIMARY    a **Primary source** section with at least one absolute http(s)
                link, and a "read on" date recording that a human opened it.
                A desk mining list is a lead; the tracker thread is the source.
  US-REPORTER   a **Reported by** line naming who reported it upstream. This is
                the whole reason the tier is publishable: the claim belongs to
                someone, and they are credited.
  US-ENGAGE     a **Maintainer engagement** line from a closed vocabulary. A
                maintainer-confirmed report and a report nobody answered are
                different claims and must not read alike.
  US-STATE      an **Issue state** line from a closed vocabulary. "Closed,
                fixed in 0.20.7" and "open" are different claims; so are
                "closed as stale" and "closed as fixed", and conflating those
                two is the specific error this check exists to prevent.
  US-NOTREPRO   an explicit sentence that nobody here has reproduced it. Not
                implied by the label; written, in the entry, where a reader who
                arrived by search will see it.
  US-INVITE     an **If you have this stack** section carrying a runnable
                procedure with CONFIRM and REFUTE criteria, so a reader with
                the hardware can settle it rather than admire the problem.

And repo-wide, the three separations that keep the tier from leaking into the
measured registry:

  US-NOT-CORE   no upstream entry is cited by CORE.md
  US-NOT-DOCTOR no upstream id appears in the doctor's TRAP_PATHS, and the
                doctor does not read the upstream tree
  US-NOT-COUNTED no upstream entry has a row in the README symptom table, and
                no upstream file lives under traps/. The registry totals are
                derived from traps/<category>/NN-*.md, so an upstream entry
                cannot inflate a count by construction; this asserts the
                construction rather than trusting it.

  US-GRANDFATHER
                no NEW entry under traps/ may carry "reported by others". The
                24 that do predate this tier and are recorded by name in
                registry_config.json. Without this the tier is decorative: the
                easy path for the next upstream-sourced report would be to put
                it in traps/ with the old label, which is exactly the
                separation this directory exists to create.

Usage:
    python3 integrity/upstream_integrity.py [--root .] [--json] [--github]

Exit 0 clean, 1 on any failure.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ENTRY_RE = re.compile(r"^(U\d{2,})-.+\.md$")
ABS_LINK_RE = re.compile(r"https?://[^\s)>\]]+")
# \s+ and not " ": entries are hard-wrapped, so "read on" and its date land on
# different lines about a third of the time. A single-space version of this
# pattern failed 4 of the first 11 entries, every one of them correctly dated.
# This is the same line-wrap defect written up in contradiction_gate.py, and it
# reappeared in the next checker written after it.
READ_ON_RE = re.compile(r"read on\s+(\d{4}-\d{2}-\d{2})", re.I)

STATUS_RE = re.compile(r"^\*\*Status:\s*(.+?)\*\*", re.M)
REPORTER_RE = re.compile(r"^\*\*Reported by\b[^*]*\*\*\s*(.*)", re.M)
ENGAGE_RE = re.compile(r"^\*\*Maintainer engagement:\s*(.+?)\.?\*\*", re.M)
STATE_RE = re.compile(r"^\*\*Issue state:\s*(.+?)\.?\*\*", re.M)

SECTION_PRIMARY = re.compile(r"^\*\*Primary source", re.M)
SECTION_INVITE = re.compile(r"^##\s+If you have this stack", re.M)

CONFIRM_RE = re.compile(r"\*\*CONFIRM\b", re.M)
REFUTE_RE = re.compile(r"\*\*REFUTE\b", re.M)

# The non-reproduction sentence. Several phrasings are allowed because forcing
# one exact string would produce entries that all open with the same sentence
# and stop being read. What is NOT allowed is leaving it out.
NOT_REPRO_RE = re.compile(
    r"(nobody here has reproduced|we have not reproduced|not reproduced here|"
    r"no one here has reproduced|has not been reproduced here)", re.I)

# The other tier labels. An upstream entry carrying one of these is claiming
# measurement from inside the tier that exists for unmeasured material.
FOREIGN_LABELS = [
    "reproduced here",
    "contributor-measured",
    "measured here, raw not published",
    "under test",
    "reported by others",
]

LABEL = "upstream-reported"


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def load_config(root):
    path = os.path.join(root, "integrity", "registry_config.json")
    if not os.path.exists(path):
        return {}
    return json.loads(read(path))


def gha(level, message, path=None, line=None, title=None):
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
        self.check = check
        self.where = where
        self.message = message

    def as_dict(self):
        return {"check": self.check, "where": self.where,
                "message": self.message}


def collect(root):
    """{id: relpath} for upstream entries."""
    out = {}
    d = os.path.join(root, "upstream")
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        m = ENTRY_RE.match(name)
        if m:
            out[m.group(1)] = "upstream/%s" % name
    return out


def section(text, header_re):
    """The body of a section, from its header to the next blank-line-separated
    bold lead-in or heading. Used only to scope the CONFIRM/REFUTE search."""
    m = header_re.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def check_entry(root, tid, rel, cfg, findings):
    text = read(os.path.join(root, rel))
    vocab = cfg.get("upstream_tier", {})
    engagements = [e.lower() for e in vocab.get("engagement_values", [])]
    states = [s.lower() for s in vocab.get("issue_state_values", [])]

    # US-STATUS
    m = STATUS_RE.search(text)
    if not m:
        findings.append(Finding("US-STATUS", rel, "no **Status:** line"))
    else:
        raw = m.group(1).strip().lower()
        if LABEL not in raw:
            findings.append(Finding(
                "US-STATUS", rel,
                "status %r does not carry the %r label; %s is the only tier "
                "valid in this directory" % (raw[:60], LABEL, LABEL)))
        for bad in FOREIGN_LABELS:
            # "reported by others" is a substring risk against nothing here,
            # but "reproduced here" appears inside the required
            # non-reproduction sentence, so match the STATUS LINE only.
            if bad in raw:
                findings.append(Finding(
                    "US-STATUS", rel,
                    "status carries %r as well as %r. An upstream entry may "
                    "not carry a second tier label: it would claim "
                    "measurement from the tier that exists for material "
                    "nobody measured" % (bad, LABEL)))

    # US-PRIMARY
    if not SECTION_PRIMARY.search(text):
        findings.append(Finding(
            "US-PRIMARY", rel,
            "no **Primary source** section. A mining list is a lead; the tier "
            "requires the thread itself"))
    else:
        if not ABS_LINK_RE.search(text):
            findings.append(Finding(
                "US-PRIMARY", rel,
                "**Primary source** section carries no absolute http(s) link"))
        if not READ_ON_RE.search(text):
            findings.append(Finding(
                "US-PRIMARY", rel,
                "no 'read on YYYY-MM-DD' date. The tier's requirement is that "
                "a human OPENED the source, and an undated link does not "
                "record that anyone did"))

    # US-REPORTER
    if not REPORTER_RE.search(text):
        findings.append(Finding(
            "US-REPORTER", rel,
            "no **Reported by ...** line. Crediting the reporter is the "
            "reason this tier is publishable at all"))

    # US-ENGAGE
    m = ENGAGE_RE.search(text)
    if not m:
        findings.append(Finding(
            "US-ENGAGE", rel, "no **Maintainer engagement:** line"))
    elif engagements and m.group(1).strip().lower() not in engagements:
        findings.append(Finding(
            "US-ENGAGE", rel,
            "engagement %r is not in the closed vocabulary %s"
            % (m.group(1).strip()[:60], engagements)))

    # US-STATE
    m = STATE_RE.search(text)
    if not m:
        findings.append(Finding(
            "US-STATE", rel,
            "no **Issue state:** line. A closed-as-fixed report and an open "
            "one are different claims"))
    elif states:
        got = m.group(1).strip().lower()
        # A state may carry a free qualifier after a comma or bracket, but must
        # OPEN with one of the closed values: "closed, fixed in v0.20.7".
        if not any(got.startswith(s) for s in states):
            findings.append(Finding(
                "US-STATE", rel,
                "issue state %r does not open with any value in the closed "
                "vocabulary %s" % (got[:60], states)))

    # US-NOTREPRO
    if not NOT_REPRO_RE.search(text):
        findings.append(Finding(
            "US-NOTREPRO", rel,
            "no explicit statement that nobody here has reproduced this. The "
            "label implies it; the tier requires it written where a reader "
            "who arrived by search will see it"))

    # US-INVITE
    if not SECTION_INVITE.search(text):
        findings.append(Finding(
            "US-INVITE", rel,
            "no '## If you have this stack' section. An entry a reader cannot "
            "act on is an observation, not an invitation"))
    else:
        body = section(text, SECTION_INVITE)
        if not CONFIRM_RE.search(body):
            findings.append(Finding(
                "US-INVITE", rel,
                "the invitation states no **CONFIRM** criterion"))
        if not REFUTE_RE.search(body):
            findings.append(Finding(
                "US-INVITE", rel,
                "the invitation states no **REFUTE** criterion"))


def check_separation(root, entries, cfg, findings):
    ids = set(entries)
    id_re = re.compile(r"\bU\d{2,}\b")

    # US-NOT-CORE
    core = os.path.join(root, "CORE.md")
    if os.path.exists(core):
        ctext = read(core)
        for tid in sorted(ids):
            if tid in ctext:
                findings.append(Finding(
                    "US-NOT-CORE", "CORE.md",
                    "Core cites upstream entry %s. Core is the measured "
                    "reading list and the fourth tier never appears in it"
                    % tid))
        if "upstream/" in ctext.replace("upstream/README", ""):
            findings.append(Finding(
                "US-NOT-CORE", "CORE.md",
                "Core links into upstream/"))

    # US-NOT-DOCTOR
    doc = os.path.join(root, "doctor", "minefield_doctor.py")
    if os.path.exists(doc):
        dtext = read(doc)
        m = re.search(r"TRAP_PATHS\s*=\s*\{(.*?)\n\}", dtext, re.S)
        if m and id_re.search(m.group(1)):
            findings.append(Finding(
                "US-NOT-DOCTOR", "doctor/minefield_doctor.py",
                "an upstream id appears in TRAP_PATHS. Doctor coverage is a "
                "count over measured entries and the fourth tier never "
                "counts toward it"))
        if re.search(r"[\"']upstream/", dtext):
            findings.append(Finding(
                "US-NOT-DOCTOR", "doctor/minefield_doctor.py",
                "the doctor references the upstream/ tree"))

    # US-NOT-COUNTED
    readme = read(os.path.join(root, "README.md"))
    for line in readme.splitlines():
        if line.startswith("|") and "upstream/" in line and "](upstream/" in line:
            # A pointer to the directory from prose is fine; a SYMPTOM-TABLE
            # row is not, because that table is the measured registry's index.
            if re.search(r"\|\s*\[U\d{2,}\]\(upstream/", line):
                findings.append(Finding(
                    "US-NOT-COUNTED", "README.md",
                    "an upstream entry has a row in the symptom table"))
    traps = os.path.join(root, "traps")
    for dp, _dns, fns in os.walk(traps):
        for fn in fns:
            if ENTRY_RE.match(fn):
                findings.append(Finding(
                    "US-NOT-COUNTED",
                    os.path.relpath(os.path.join(dp, fn), root),
                    "an upstream entry file is inside traps/, where the "
                    "registry counts are derived from"))

    # US-GRANDFATHER
    grand = set(cfg.get("upstream_tier", {}).get(
        "reported_by_others_grandfathered", []))
    if grand:
        status_re = re.compile(r"^\*\*Status:\s*(.+)", re.M)
        for dp, _dns, fns in os.walk(traps):
            for fn in sorted(fns):
                if not fn.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
                m = status_re.search(read(os.path.join(dp, fn)))
                if not m:
                    continue
                if "reported by others" in m.group(1).lower() and rel not in grand:
                    findings.append(Finding(
                        "US-GRANDFATHER", rel,
                        "a NEW entry under traps/ carries 'reported by "
                        "others'. That label is frozen to the %d entries that "
                        "predate the upstream-reported tier; new "
                        "upstream-sourced material goes to upstream/ so the "
                        "measured and the reported stay visibly separate"
                        % len(grand)))


def run(root):
    findings = []
    cfg = load_config(root)
    entries = collect(root)
    for tid in sorted(entries):
        check_entry(root, tid, entries[tid], cfg, findings)
    check_separation(root, entries, cfg, findings)
    return findings, len(entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--github", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(args.root))

    findings, n = run(root)

    if args.json:
        print(json.dumps({"upstream_entries": n,
                          "findings": [f.as_dict() for f in findings]},
                         indent=2))
        return 1 if findings else 0

    if args.github:
        for f in findings:
            where = f.where.split(":")
            gha("error", "%s: %s" % (f.where, f.message),
                os.path.join(root, where[0]), None,
                "upstream tier: %s" % f.check)

    print("upstream tier integrity: %s" % root)
    print("  upstream-reported entries: %d   (never Core, never doctor "
          "coverage, never a registry count)" % n)
    if not findings:
        print("  CLEAN: %d per-entry assertions over %d entries, plus 5 "
              "separation assertions" % (7 * n, n))
        return 0
    print("")
    by = {}
    for f in findings:
        by.setdefault(f.check, []).append(f)
    for check in sorted(by):
        print("%s (%d)" % (check, len(by[check])))
        for f in by[check]:
            print("  %-52s %s" % (f.where, f.message))
        print("")
    print("FAIL: %d findings" % len(findings))
    return 1


if __name__ == "__main__":
    sys.exit(main())
