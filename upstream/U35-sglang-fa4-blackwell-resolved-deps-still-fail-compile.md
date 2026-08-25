# U35: a dependency set can resolve cleanly and still make FA4 fail to compile on Blackwell

**Reported by @mmangkad.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The dependency fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #34372 is merged.

**Primary source.** [SGLang PR #34372](https://github.com/sgl-project/sglang/pull/34372), read on 2026-08-25.

**Symptom.** SGLang can resolve and install a valid-looking dependency combination, then fail while compiling an FA4 kernel on Blackwell during startup.

**Mechanism.** `quack-kernels==0.6.3` could resolve with `nvidia-cutlass-dsl==4.6.0`, but that pair exposed a CuTeDSL branch-scope/type-join compiler bug after Quack's AST rewrite. SGLang fixed the path by pinning a matched Quack/CuTeDSL pair containing the compiler fix.

**What we have not done.** We have not reproduced this dependency/compiler pair on Blackwellboy infrastructure and do not claim every FA4 startup failure has this cause.

## If you have this stack

Pin the affected SGLang dependency pair on Blackwell and compile the same FA4 relative-bias path, then repeat with the fixed matched versions. Record the exact resolved package versions rather than only the SGLang tag.

**CONFIRM.** The old dependency pair resolves successfully but reproduces the reported FA4 compile error, while the fixed matched pair compiles the same path.

**REFUTE.** The pinned allegedly affected pair compiles the target FA4 kernel successfully, or the failure persists identically on the fixed pair.

## Attribution

Reported and fixed upstream by @mmangkad in SGLang PR #34372. The registry has not independently reproduced the measurement.