#!/usr/bin/env python3
"""contradiction_gate.py - an entry must not claim more than its own files admit.

THE DEFECT THIS EXISTS FOR
--------------------------
Trap 33 shipped for a day claiming "reproduced here" while the data README it
links to said, in as many words, "you cannot check our rows, and you can run
the study". Both statements are ours. Only one of them can be true, and the
weaker one was correct.

WHY THIS SHAPE AND NOT AN ABSENCE GATE
--------------------------------------
The obvious check is "does an entry claiming reproduced here NAME its
evidence". That was attempted twice and abandoned, and the write-up is in
integrity/README.md. Short version: CONTRIBUTING form 3 explicitly allows the
evidence to be a runnable procedure stated in PROSE, and prose is not
mechanically distinguishable from absence. Measured across all 81 entries, the
shape-matching version failed 36 of the 61 that claim the label, nearly all of
them honest. A guard that fires on two dozen good entries gets waved through,
which is worse than no guard.

This gate asks a different question, and it is one a machine can answer without
judging prose: **does the entry claim reproduced here while something it ships
or links to says the result is not checkable?** That is a contradiction between
two of our own statements. An honest entry whose evidence is a described
procedure never asserts non-checkability, so it never trips.

SCOPE
-----
  * Only entries whose Status line contains "reproduced here" are considered.
  * The entry file itself, plus every in-repo file it links to, ONE HOP.
    One hop is not incidental: trap 33's contradiction was not in the entry, it
    was in the data README the entry links to. A gate reading only the entry
    would have missed the case it was built for.
  * A compound status that already discloses the limit is NOT a contradiction.
    "reproduced here for the arithmetic, and measured here, raw not published
    for the curve" is the entry being precise, which is the behaviour we want.
"""
import os
import re

# Assertions that the result cannot be checked by a reader. Deliberately NOT
# the bare label fragment "raw not published": that string is half of a closed
# vocabulary label, and an entry carrying a compound status uses it correctly.
# Matching it fires on precision, which is the opposite of the intent. See
# measure notes in integrity/README.md.
NON_CHECKABLE = [
    (r"you cannot check (?:our|the) rows", "says the reader cannot check our rows"),
    (r"cannot be checked by (?:a|the) (?:stranger|reader)", "says a reader cannot check it"),
    (r"(?:can be |may be )?(?:produced|provided|supplied|made available)\s+on request",
     "offers the raw on request, which CONTRIBUTING says is not evidence"),
    (r"available to maintainers on request", "offers the raw on request"),
    (r"\bavailable on request\b", "offers the raw on request"),
    (r"held outside the tree(?![^.]{0,80}\bmeasured here)", "says the raw is held outside the tree"),
    (r"we do not ship the answer sheets", "says the answer sheets are not shipped"),
    (r"raw is private(?! and)", "says the raw is private"),
]
NON_CHECKABLE = [(re.compile(p, re.I), why) for p, why in NON_CHECKABLE]

STATUS_RE = re.compile(r"^\*\*Status:.*", re.M)
LINK_RE = re.compile(r"\[[^\]]*\]\((?!https?:|#)([^)\s#]+)")

# The closed-vocabulary labels, stripped before matching so a correctly stated
# compound status cannot be read as a confession.
LABELS = [
    "measured here, raw not published",
    "contributor-measured, conditions as reported",
    "reported by others",
    "reproduced here",
    "under test",
]


def status_line(text):
    m = STATUS_RE.search(text)
    return text[m.start():].split("\n\n", 1)[0] if m else ""


def claims_reproduced_here(text):
    return "reproduced here" in status_line(text).lower()


def discloses_the_limit(text):
    """A compound status that already names a weaker label for part of the
    entry is precision, not contradiction."""
    s = status_line(text).lower()
    return any(lbl in s for lbl in
               ("measured here, raw not published", "contributor-measured"))


def _strip_labels(s):
    out = s
    for lbl in LABELS:
        out = re.sub(re.escape(lbl), " ", out, flags=re.I)
    return out


# Files a hop must NOT follow into, and why. Both were measured: following
# into them fired on 12 entries, every one a false positive.
#
#   policy documents  discuss non-checkability generically. CONTRIBUTING's
#                     sentence "this holds whether your raw is private or
#                     published at a URL" is the rule being explained, not a
#                     confession about any entry. Every entry links CONTRIBUTING.
#
#   sibling entries   another entry's limits are not this entry's contradiction.
#                     Entries cross-link constantly, so following into them made
#                     one addendum inside trap 12 fire on eight unrelated
#                     entries that merely link to it.
#
# What a hop SHOULD reach is the material this entry ships AS its evidence: a
# data README, a mining writeup. That is where trap 33's contradiction lived.
POLICY_DOCS = {"CONTRIBUTING.md", "MAINTAINING.md", "README.md", "CHANGELOG.md",
               "HALL_OF_FAME.md"}
ENTRY_RE = re.compile(r"traps[/\\][a-z]+[/\\]\d+-")


def one_hop(path, text, root):
    """In-repo evidence files this entry links to. One hop, no recursion."""
    base = os.path.dirname(path)
    out = []
    for tgt in LINK_RE.findall(text):
        if tgt.startswith("../../issues"):
            continue
        p = os.path.normpath(os.path.join(base, tgt))
        if not p.startswith(root) or p == path:
            continue
        if os.path.isdir(p):
            p = os.path.join(p, "README.md")
        if not (os.path.isfile(p) and p.endswith(".md")):
            continue
        rel = os.path.relpath(p, root).replace("\\", "/")
        if rel in POLICY_DOCS or ENTRY_RE.search(rel):
            continue
        out.append(p)
    return sorted(set(out))


# The label and its value are frequently on different lines, because entries
# are hard-wrapped. A character class excluding newlines missed every one of
# them, which is the same line-wrap bug that broke an earlier attempt.
SECTION_RE = re.compile(r"^#{2,}\s", re.M)
SUBSECTION_LABEL = re.compile(
    r"(?i)(?:status of this (?:addendum|section)|\*\*status:)[^.]{0,120}?"
    r"(measured here, raw not published|contributor-measured|reported by others)")


def _section_discloses(body, pos):
    """A marker inside a sub-section that carries its OWN weaker label belongs
    to that sub-section. Folded contributor addenda are the common case: their
    raw is private, they say so, and they are labelled contributor-measured."""
    starts = [m.start() for m in SECTION_RE.finditer(body)]
    lo = max([s for s in starts if s <= pos], default=0)
    hi = min([s for s in starts if s > pos], default=len(body))
    return bool(SUBSECTION_LABEL.search(body[lo:hi]))


def check(path, root, read):
    """Return a list of (where, why, quote) contradictions for one entry."""
    text = read(path)
    if not claims_reproduced_here(text):
        return []
    if discloses_the_limit(text):
        return []
    found = []
    for p in [path] + one_hop(path, text, root):
        # Match on the RAW text. An earlier version stripped the closed
        # vocabulary first and then asked whether a sub-section carried a
        # label, which had already removed the answer; it also made every
        # reported line number wrong. Stripping is unnecessary because no
        # marker below is a label fragment: "raw not published" was
        # deliberately excluded for exactly that reason.
        body = read(p)
        for rx, why in NON_CHECKABLE:
            m = rx.search(body)
            if m:
                if _section_discloses(body, m.start()):
                    continue
                line = body[:m.start()].count("\n") + 1
                quote = re.sub(r"\s+", " ", body[max(0, m.start() - 40):m.end() + 40]).strip()
                rel = os.path.relpath(p, root).replace("\\", "/")
                found.append((f"{rel}:{line}", why, quote))
                break
    return found
