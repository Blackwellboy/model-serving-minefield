# U36: a warm restart can turn `sitecustomize` stdout into invalid launcher JSON

**Reported by @GraithSecurity.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The repository accepted a targeted fix and regression test for the reported failure.

**Issue state: closed, fixed.** MiaAI-Lab issue #15 was closed after fix commit `f68130a4365f648b4833b169d75ef1a4188bfcb8` landed.

**Primary source.** [MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks issue #15](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/15) and [fix commit `f68130a`](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/commit/f68130a4365f648b4833b169d75ef1a4188bfcb8), read on 2026-08-30.

**Symptom.** A GLM-5.3 EXL3 serve starts cleanly from a cold container, then a warm restart crash-loops in vLLM argument parsing because `--speculative-config` is no longer valid JSON.

**Mechanism.** The image uses Python `sitecustomize` to apply runtime overlays. On the already-patched warm path, an overlay diagnostic printed to stdout. The launcher generated `--speculative-config` with shell command substitution around `python3 -c '...json...'`, so startup-hook stdout was captured before the JSON and converted a valid machine-readable value into invalid input. The fix routes overlay diagnostics to stderr and invokes the JSON helper with `python3 -S` so `sitecustomize`/`.pth` startup output cannot enter the substitution.

**What we have not done.** We have not reproduced this cold-versus-warm launcher failure on Blackwellboy infrastructure. The source issue, fix diff and regression test establish the reported mechanism on that recipe, not a universal claim about every Python launcher.

## If you have this stack

On the affected revision, run the JSON-producing Python command in the same container once on a cold path and once after the overlay has already applied. Capture stdout and stderr separately, then repeat after the fix commit.

**CONFIRM.** The affected warm path prepends overlay text to stdout, the command-substituted `--speculative-config` becomes invalid, and either redirecting diagnostics to stderr or using the fixed `python3 -S` launcher restores clean JSON without changing the model/runtime.

**REFUTE.** The pinned affected revision produces byte-clean JSON on stdout after warm restart, or the crash persists after stdout is proven clean and the fixed launcher is used.

## Attribution

Reported by @GraithSecurity in MiaAI-Lab issue #15. The repository fixed it in commit `f68130a`; the registry has not independently reproduced the runtime failure.
