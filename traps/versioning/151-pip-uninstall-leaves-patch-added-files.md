# Trap 151: layering a new package version can leave patch-added files from the old image

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #161](https://github.com/Blackwellboy/model-serving-minefield/issues/161)).

**Symptom.** A new engine version installs cleanly over an older patched image, yet files that do not exist in the new release remain importable inside the package tree.

**Mechanism.** `pip uninstall` removes files listed in the installed distribution's RECORD. Files added later by in-place patches are absent from RECORD, so they survive uninstall and the new version is installed around them. They can remain inert, shadow renamed modules, or be discovered by package/plugin scans.

**Stacks and builds bitten.** TensorFold 0.3.6.3 patched in place, then 0.5.0 installed with `pip install --no-deps`; mechanism reproduced offline with a small package on pip/Python.

**The check.** Compare the final installed package tree with the pinned upstream tree, or enumerate package files not represented in RECORD and inspect every extra.

**The fix.** Build upgrades from a clean base, or explicitly remove patch-added files before installing the next version. Verify the final tree rather than trusting uninstall/install logs.

**Found.** 2026-09, layered inference image upgrade.

**Attribution.** @scottleimroth.
