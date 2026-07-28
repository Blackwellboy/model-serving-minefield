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
    REGRESSION_ASSERTS = [(name, callable), ...]  # optional; MUST return True

Each callable runs the check in-process against a fixture and returns the
exit code the check would use. No lane, no network, no weights.

REGRESSION_ASSERTS exists because a contributor found the hole. A guard for a
specific past defect is not a negative control: it does not feed an input to
the check and read the check's verdict, it asserts that a helper still refuses
something. Expressed as a negative control it has to be written inverted, so
that CORRECT behaviour "fails" the control, which makes NEGATIVE_CONTROLS lie
to anyone reading it as "inputs that make this check fail". Each callable here
returns True if the defect is still dead. Optional: most checks have none.

**Non-Python checks are covered too.** A shell check cannot declare Python
callables, so it declares them in a sidecar at
`checks/tests/controls_<stem>.py`, which drives the script out-of-process and
returns its exit code. A non-Python check with no sidecar is a CONTRACT
VIOLATION, not a skip: discovery used to glob "*.py" only, so
util_vs_power_tell.sh was never contract-tested and the harness still reported
"ALL PASS (8 checks conform)". A clean verdict over a set that silently
excludes a member is the same defect this file exists to catch, one level up.

Exit codes across checks in this directory:
    0  ran, nothing blocking      2  ran, blocking finding
    1  target unreachable         3  ran, but inspected nothing (NOT a pass)

    python3 checks/tests/test_check_contract.py
"""
import json
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


TESTS_DIR = Path(__file__).resolve().parent
NON_PYTHON_GLOBS = ("*.sh",)


def discover_python():
    return sorted(p for p in CHECKS_DIR.glob("*.py")
                  if not p.name.startswith("_"))


def discover_non_python():
    out = []
    for pattern in NON_PYTHON_GLOBS:
        out += [p for p in CHECKS_DIR.glob(pattern)
                if not p.name.startswith("_")]
    return sorted(out)


def controls_sidecar(path):
    """Where a non-Python check's controls live. Absence is a violation."""
    return TESTS_DIR / f"controls_{path.stem}.py"


def discover():
    """Every check the contract binds, Python or not.

    Returns a list of (display_name, source_path, controls_path). For a Python
    check the controls live in the check itself; for a non-Python check they
    live in its sidecar. A non-Python check whose sidecar is missing is still
    returned, with controls_path=None, so the harness reports it as a
    violation rather than passing over a set it quietly narrowed.
    """
    items = [(p.name, p, p) for p in discover_python()]
    for p in discover_non_python():
        side = controls_sidecar(p)
        items.append((p.name, p, side if side.exists() else None))
    return sorted(items, key=lambda t: t[0])


def _check_module(name, controls_path, fails):
    """Import the module holding this check's controls, or record why not."""
    if controls_path is None:
        fails.append(f"{name}: non-Python check with no controls sidecar at "
                     f"checks/tests/controls_{Path(name).stem}.py; it would "
                     f"otherwise escape the contract entirely")
        return None
    try:
        return load(controls_path)
    except Exception as e:
        fails.append(f"{name}: could not import controls ({e})")
        return None


def _run_controls(name, mod, fails, verbose=False):
    controls = getattr(mod, "NEGATIVE_CONTROLS", None)
    if not controls:
        fails.append(f"{name}: no NEGATIVE_CONTROLS declared")
        if verbose:
            print("   FAIL: declares no input that makes it fail. A check "
                  "with no failing case cannot be told apart from a check "
                  "that never fires.")
    else:
        for label, fn in controls:
            try:
                code = fn()
            except Exception as e:
                fails.append(f"{name}: negative control {label!r} raised ({e})")
                if verbose:
                    print(f"   FAIL negative control {label!r}: raised {e}")
                continue
            if code == OK:
                fails.append(f"{name}: negative control {label!r} PASSED")
                if verbose:
                    print(f"   FAIL negative control {label!r}: returned 0. "
                          f"This input was supposed to fail the check.")
            elif code == NOTHING_INSPECTED:
                fails.append(f"{name}: negative control {label!r} inspected nothing")
                if verbose:
                    print(f"   FAIL negative control {label!r}: returned 3 "
                          f"(inspected nothing). A negative control has to "
                          f"FAIL, not decline to look.")
            elif verbose:
                print(f"   ok  negative control {label!r} -> {code}")

    empty = getattr(mod, "EMPTY_SET_CONTROL", None)
    if not empty:
        fails.append(f"{name}: no EMPTY_SET_CONTROL declared")
        if verbose:
            print("   FAIL: declares no empty-comparison-set control, so a "
                  "pass over nothing would go unnoticed.")
    else:
        label, fn = empty
        try:
            code = fn()
        except Exception as e:
            fails.append(f"{name}: empty-set control {label!r} raised ({e})")
            if verbose:
                print(f"   FAIL empty-set control {label!r}: raised {e}")
        else:
            if code == OK:
                fails.append(f"{name}: empty-set control {label!r} PASSED")
                if verbose:
                    print(f"   FAIL empty-set control {label!r}: returned 0. "
                          f"The check reported success having compared "
                          f"nothing.")
            elif verbose:
                print(f"   ok  empty-set control {label!r} -> {code}")

    # Optional. A check with none declares nothing and is not penalised.
    for label, fn in getattr(mod, "REGRESSION_ASSERTS", []) or []:
        try:
            alive = fn()
        except Exception as e:
            fails.append(f"{name}: regression assert {label!r} raised ({e})")
            if verbose:
                print(f"   FAIL regression assert {label!r}: raised {e}")
            continue
        if not alive:
            fails.append(f"{name}: regression assert {label!r} FAILED; the "
                         f"defect it guards has come back")
            if verbose:
                print(f"   FAIL regression assert {label!r}: the defect it "
                      f"guards has come back.")
        elif verbose:
            print(f"   ok  regression assert {label!r}")


MANIFEST_PATH = CHECKS_DIR / "MANIFEST.json"


def manifest_failures(checks):
    """Two-way: what the manifest expects vs what discovery found.

    The harness already refuses to pass over an empty set. That is not enough:
    a set of one is not empty and is still wrong if the registry expects two.
    Coverage was silent, so discovery could narrow and nothing would say so.
    """
    fails = []
    if not MANIFEST_PATH.exists():
        return [f"{MANIFEST_PATH.name} is missing; coverage is unasserted and "
                f"a narrowed discovery set would pass silently"]
    try:
        expected = set(json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["checks"])
    except Exception as e:
        return [f"{MANIFEST_PATH.name} is unreadable ({e}); coverage is unasserted"]
    found = {name for name, _src, _c in checks}
    for missing in sorted(expected - found):
        fails.append(f"{missing}: in {MANIFEST_PATH.name} but NOT discovered. "
                     f"Either it moved or its extension stopped matching, and "
                     f"the harness would otherwise report ALL PASS without it")
    for extra in sorted(found - expected):
        fails.append(f"{extra}: discovered but NOT in {MANIFEST_PATH.name}. A "
                     f"check nobody recorded is a check nobody decided to "
                     f"cover; add it to the manifest deliberately")
    return fails


def conformance_failures():
    """Return the list of contract violations across every discovered check."""
    fails = []
    checks = discover()
    if not checks:
        return ["no checks discovered; this harness would pass vacuously over "
                "an empty set, which is the defect it tests for"], []
    fails += manifest_failures(checks)
    for name, _src, controls_path in checks:
        mod = _check_module(name, controls_path, fails)
        if mod is None:
            continue
        _run_controls(name, mod, fails)
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

    for f in manifest_failures(checks):
        print(f"MANIFEST: {f}")
        fails.append(f)

    for name, _src, controls_path in checks:
        print(f"== {name}")
        mod = _check_module(name, controls_path, fails)
        if mod is None:
            print(f"   FAIL: no controls for {name}. A check the harness "
                  f"cannot exercise is not a covered check.")
            continue
        _run_controls(name, mod, fails, verbose=True)

    print()
    if fails:
        print(f"{len(fails)} FAILURE(S):")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    n_sh = len(discover_non_python())
    detail = f" ({n_sh} non-Python)" if n_sh else ""
    print(f"ALL PASS ({len(checks)} check(s) conform{detail})")


if __name__ == "__main__":
    main()
