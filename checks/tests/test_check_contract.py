#!/usr/bin/env python3
"""The contract every check in checks/ must satisfy: it has to be able to fail.

A check that cannot report a problem is worse than no check, because it emits
a clean verdict a reader will act on. Two shapes produce that, both of which
have been found in real checks in this project and in submissions to it:

  1. The unfailable assertion. The check greps for a sentinel that is also
     present in its own input, so a model that ignored the request entirely
     still passes.
  2. The vacuous PASS. The check succeeds over an EMPTY comparison set: zero
     tensors compared and a fidelity of 1.0, zero items scored and 100%
     agreement, nothing rendered and an exit code of 0. Every universal claim
     is true of the empty set, which is exactly why it must never be a pass.

This file is the mechanical half of that rule. Reviewing check code by hand
for shape 1 does not work, for the same reason reviewing the doctor's ok()
calls by hand did not: three passes each converted the false CLEANs they
happened to look at and each missed others. So the requirement is not "look
carefully", it is "produce the input that fails, and let the harness run it".
It is the same move as CLEAN_CONTRACT in doctor/tests/test_doctor_verdicts.py,
where every clean verdict is enumerated with the failure mode it rules OUT.

Each check declares, at module level:

    NEGATIVE_CONTROLS = [(name, callable), ...]   # each MUST report failure
    EMPTY_SET_CONTROL = (name, callable)          # MUST NOT report success

Each callable runs the check in-process against a fixture and returns the
exit code the check would use. No lane, no network, no weights.

Exit codes across checks in this directory:
    0  ran, nothing blocking      2  ran, blocking finding
    1  target unreachable         3  ran, but inspected nothing (NOT a pass)

    python3 checks/tests/test_check_contract.py
"""
import importlib.util
import sys
from pathlib import Path

CHECKS_DIR = Path(__file__).resolve().parent.parent
OK, UNREACHABLE, BLOCKING, NOTHING_INSPECTED = 0, 1, 2, 3


def load(path):
    spec = importlib.util.spec_from_file_location(f"check_{path.stem}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def discover():
    return sorted(p for p in CHECKS_DIR.glob("*.py")
                  if not p.name.startswith("_"))


def conformance_failures():
    """Return the list of contract violations across every discovered check."""
    fails = []
    checks = discover()
    if not checks:
        return ["no checks discovered; this harness would pass vacuously over "
                "an empty set, which is the defect it tests for"], []
    for path in checks:
        try:
            mod = load(path)
        except Exception as e:
            fails.append(f"{path.name}: could not import ({e})")
            continue
        controls = getattr(mod, "NEGATIVE_CONTROLS", None)
        if not controls:
            fails.append(f"{path.name}: no NEGATIVE_CONTROLS declared")
        else:
            for label, fn in controls:
                try:
                    code = fn()
                except Exception as e:
                    fails.append(f"{path.name}: negative control {label!r} raised ({e})")
                    continue
                if code == OK:
                    fails.append(f"{path.name}: negative control {label!r} PASSED")
                elif code == NOTHING_INSPECTED:
                    fails.append(f"{path.name}: negative control {label!r} inspected nothing")
        empty = getattr(mod, "EMPTY_SET_CONTROL", None)
        if not empty:
            fails.append(f"{path.name}: no EMPTY_SET_CONTROL declared")
        else:
            label, fn = empty
            try:
                code = fn()
            except Exception as e:
                fails.append(f"{path.name}: empty-set control {label!r} raised ({e})")
            else:
                if code == OK:
                    fails.append(f"{path.name}: empty-set control {label!r} PASSED")
    return fails, checks


def test_every_check_can_fail():
    """pytest entry point.

    Without this, the file is collected by pytest, contributes zero tests, and
    reports green. A test file that runs nothing is the same vacuous pass this
    harness exists to catch, so it gets a collected test of its own.
    """
    fails, checks = conformance_failures()
    assert checks, "no checks discovered; a green run over zero checks is vacuous"
    assert not fails, "check contract violated:\n  " + "\n  ".join(fails)


def main():
    fails = []
    checks = discover()
    if not checks:
        # This harness asserting "all checks conform" over zero checks would
        # be the very defect it exists to catch.
        print("FAILURE: no checks discovered; this harness would pass "
              "vacuously over an empty set, which is the defect it tests for")
        sys.exit(1)

    for path in checks:
        name = path.name
        print(f"== {name}")
        try:
            mod = load(path)
        except Exception as e:
            fails.append(f"{name}: could not import ({e})")
            print(f"   IMPORT FAILED: {e}")
            continue

        controls = getattr(mod, "NEGATIVE_CONTROLS", None)
        if not controls:
            fails.append(f"{name}: no NEGATIVE_CONTROLS declared")
            print("   FAIL: declares no input that makes it fail. A check "
                  "with no failing case cannot be told apart from a check "
                  "that never fires.")
        else:
            for label, fn in controls:
                try:
                    code = fn()
                except Exception as e:
                    fails.append(f"{name}: negative control {label!r} raised ({e})")
                    print(f"   FAIL negative control {label!r}: raised {e}")
                    continue
                if code == OK:
                    fails.append(f"{name}: negative control {label!r} PASSED")
                    print(f"   FAIL negative control {label!r}: returned 0. "
                          f"This input was supposed to fail the check.")
                elif code == NOTHING_INSPECTED:
                    fails.append(f"{name}: negative control {label!r} inspected nothing")
                    print(f"   FAIL negative control {label!r}: returned 3 "
                          f"(inspected nothing). A negative control has to "
                          f"FAIL, not decline to look.")
                else:
                    print(f"   ok  negative control {label!r} -> {code}")

        empty = getattr(mod, "EMPTY_SET_CONTROL", None)
        if not empty:
            fails.append(f"{name}: no EMPTY_SET_CONTROL declared")
            print("   FAIL: declares no empty-comparison-set control, so a "
                  "pass over nothing would go unnoticed.")
        else:
            label, fn = empty
            try:
                code = fn()
            except Exception as e:
                fails.append(f"{name}: empty-set control {label!r} raised ({e})")
                print(f"   FAIL empty-set control {label!r}: raised {e}")
            else:
                if code == OK:
                    fails.append(f"{name}: empty-set control {label!r} PASSED")
                    print(f"   FAIL empty-set control {label!r}: returned 0. "
                          f"The check reported success having compared "
                          f"nothing.")
                else:
                    print(f"   ok  empty-set control {label!r} -> {code}")

    print()
    if fails:
        print(f"{len(fails)} FAILURE(S):")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    print(f"ALL PASS ({len(checks)} check(s) conform)")


if __name__ == "__main__":
    main()
