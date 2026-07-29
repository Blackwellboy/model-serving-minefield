#!/usr/bin/env python3
"""run_checks.py - every consistency check, one command.

    python3 integrity/run_checks.py

Runs, in order:

  1. registry integrity        entries complete, counts agree
  2. claim propagation         no surface carries a retracted claim
  3. do-not-cite               nothing on the list in added text
  4. sanitizer whole-tree      LOCAL ONLY, see below
  5. doctor + checks suites    the tool's own regression tests

Why the sanitizer is local only. Its pattern file is a list of the internal
hostnames, usernames, path fragments and codenames we are scanning FOR.
Committing it to a public repo publishes the thing it protects. So the
sanitizer runs from the private kit on this machine, is wired into the
pre-push hook, and is deliberately absent from the GitHub Actions workflow.
When the kit is not present this script says SKIPPED and says why, in those
words, rather than printing a pass it did not earn. Point it at the kit with
MINEFIELD_SANITIZER_KIT or --kit.

Exit 0 only if every check that ran passed.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_KIT = os.path.expanduser("~/staging/model-test-kit")


def run(title, cmd, cwd=None, optional_reason=None):
    print("=" * 72)
    print(title)
    print("  $ %s" % " ".join(cmd))
    print("=" * 72)
    try:
        rc = subprocess.call(cmd, cwd=cwd or ROOT)
    except OSError as e:
        if optional_reason:
            print("SKIPPED: %s (%s)" % (optional_reason, e))
            return None
        print("ERROR: %s" % e)
        return 1
    print("")
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT,
                    help="repo being checked. Defaults to the repo this file "
                         "lives in.")
    ap.add_argument("--peer", default=None,
                    help="path to the other public repo, so claim propagation "
                         "can see both. Without it the run says which repo was "
                         "NOT scanned.")
    ap.add_argument("--bbio", default=os.environ.get("MINEFIELD_BBIO_REPO"),
                    help="path to a clone of the Blackwellboy.github.io Pages "
                         "site. CI scans it and this script could not, so a "
                         "pre-push run passed while the most public surface "
                         "of the three went unchecked. Pass it, or set "
                         "MINEFIELD_BBIO_REPO.")
    ap.add_argument("--kit", default=os.environ.get("MINEFIELD_SANITIZER_KIT",
                                                    DEFAULT_KIT))
    ap.add_argument("--base", default=None, help="diff base for do-not-cite")
    ap.add_argument("--skip-sanitizer", action="store_true")
    ap.add_argument("--skip-suites", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    py = sys.executable or "python3"
    results = []

    is_registry = os.path.isdir(os.path.join(root, "traps"))
    if is_registry:
        results.append(("registry integrity",
                        run("1. REGISTRY INTEGRITY",
                            [py, os.path.join(HERE, "registry_integrity.py"),
                             "--root", root])))
        results.append(("reference integrity",
                        run("1b. REFERENCE INTEGRITY",
                            [py, os.path.join(HERE, "reference_integrity.py"),
                             "--root", root])))
        # Separate from registry integrity because it enforces a different
        # contract over a different directory: upstream/ is the fourth tier,
        # its entries are not registry entries, and folding the two together
        # would put unmeasured material inside the checker whose job is the
        # measured registry.
        results.append(("upstream tier",
                        run("1c. UPSTREAM TIER",
                            [py, os.path.join(HERE, "upstream_integrity.py"),
                             "--root", root])))
    else:
        print("1. REGISTRY INTEGRITY: not applicable, %s has no traps/ tree\n"
              % root)

    cmd = [py, os.path.join(HERE, "claim_propagation.py")]
    repos = {"minefield": None, "laguna": None}
    name = "minefield" if is_registry else "laguna"
    repos[name] = root
    if args.peer:
        other = "laguna" if name == "minefield" else "minefield"
        repos[other] = os.path.abspath(os.path.expanduser(args.peer))
    for k, v in repos.items():
        if v:
            cmd += ["--repo", "%s=%s" % (k, v)]
    if args.bbio:
        bb = os.path.abspath(os.path.expanduser(args.bbio))
        if os.path.isdir(bb):
            cmd += ["--repo", "bbio=%s" % bb]
        else:
            print("NOTE: --bbio %s is not a directory; the Pages site will "
                  "NOT be scanned by this run.\n" % bb)
    else:
        print("NOTE: no --bbio path given. The Pages site is the most public "
              "of the three surfaces and CI scans it; this run does not.\n")
    results.append(("claim propagation", run("2. CLAIM PROPAGATION", cmd)))

    dnc = [py, os.path.join(HERE, "do_not_cite.py"), "--root", root]
    if args.base:
        dnc += ["--base", args.base]
    results.append(("do-not-cite", run("3. DO-NOT-CITE", dnc)))

    if args.skip_sanitizer:
        print("4. SANITIZER: skipped by flag\n")
    else:
        scan = os.path.join(os.path.expanduser(args.kit), "sanitize_scan.py")
        supp = os.path.join(os.path.expanduser(args.kit), "supplementary_scan.py")
        if not os.path.exists(scan):
            print("=" * 72)
            print("4. SANITIZER WHOLE-TREE SCAN")
            print("=" * 72)
            print("SKIPPED: the private scanner kit is not at %s." % args.kit)
            print("This is NOT a pass. The pattern file lists the internal names")
            print("we scan for, so it cannot live in a public repo or a public")
            print("CI runner. Set MINEFIELD_SANITIZER_KIT or pass --kit, and run")
            print("this before every push.\n")
            results.append(("sanitizer", None))
        else:
            adj = os.path.join(HERE, "sanitizer_adjudicated.txt")
            extra = ["--adjudicated", adj] if os.path.exists(adj) else []
            # This repo IS a publish target, so a hit here blocks. The kit
            # refuses to run without being told, because the same hit means
            # different things on a private control-plane tree and it once
            # printed DO NOT PUSH over one it had no standing to gate.
            extra += ["--surface", "public"]
            r1 = run("4a. SANITIZER WHOLE-TREE SCAN",
                     [py, scan, "--dir", root] + extra)
            r2 = run("4b. SUPPLEMENTARY SHAPE SCAN",
                     [py, supp, "--dir", root] + extra)
            results.append(("sanitizer", max(r1 or 0, r2 or 0)))

    if not args.skip_suites and is_registry:
        for suite in ("integrity/tests", "doctor/tests", "checks/tests"):
            if os.path.isdir(os.path.join(root, suite)):
                # -t <suite> not -t . : doctor/tests and checks/tests carry
                # no __init__.py, so discovery rooted at the repo cannot import
                # them. Rooting at the suite works for all three and does not
                # require touching another session's files.
                rc = run("5. SUITE %s" % suite,
                         [py, "-m", "unittest", "discover", "-s", suite,
                          "-t", suite], cwd=root)
                # Python 3.12 returns 5 for "no tests collected". checks/tests
                # is a plain script that asserts at import and prints its own
                # verdict, so discovery finds nothing. Run it as written rather
                # than rewriting another session's test file.
                if rc == 5:
                    rc = 0
                    for fn in sorted(os.listdir(os.path.join(root, suite))):
                        if fn.startswith("test_") and fn.endswith(".py"):
                            rc = max(rc, run("5. SCRIPT %s/%s" % (suite, fn),
                                             [py, os.path.join(suite, fn)],
                                             cwd=root) or 0)
                results.append((suite, rc))

    # 6. Public surfaces. Local surfaces gate here; peer surfaces are printed
    # with a DEFERRED block naming the scheduled workflow that gates them.
    #
    # The peer half cannot gate a push. The site rebuilds AFTER the push that
    # moves HEAD, so at push time it cannot have caught up, and asserting that
    # it has would fail on every push. A missing peer still fails, in both
    # modes: absent is not stale.
    # --bbio, not --peer. --peer is the laguna lab, for claim propagation;
    # the Pages site is a different repo and already has its own flag. Passing
    # the site as --peer registers it as laguna and makes claim propagation
    # scan the wrong tree, which is how this was first written and how the
    # suite caught it.
    surf = [py, os.path.join(HERE, "verify_surfaces.py"),
            "--root", root, "--peer-mode", "defer"]
    if args.bbio:
        surf += ["--peer",
                 "bbio=%s" % os.path.abspath(os.path.expanduser(args.bbio))]
    results.append(("public surfaces (peers deferred)",
                    run("6. PUBLIC SURFACES", surf, cwd=root)))

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    bad = 0
    for name_, rc in results:
        if rc is None:
            print("  SKIPPED  %s" % name_)
        elif rc == 0:
            print("  PASS     %s" % name_)
        else:
            print("  FAIL     %s (exit %d)" % (name_, rc))
            bad += 1
    print("")
    if bad:
        print("%d check(s) failed" % bad)
        return 1
    print("all checks that ran passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
