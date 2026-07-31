# Issue #19 intake - unvalidated configuration surface (env accepted, engine ignores)

**Status:** contributor-measured intake (not yet a numbered trap)  
**Found by:** @scottleimroth  
**Diagnostic / registry framing:** @Blackwellboy  
**Primary evidence:** [issue #19](https://github.com/Blackwellboy/model-serving-minefield/issues/19)  
**Mechanism class:** `UNVALIDATED_CONFIGURATION_SURFACE`

## Scope (measured on this build)

- Stack: vLLM **0.26.0**
- Image: `vllm/vllm-openai:v0.26.0-aarch64-ubuntu2404` @ `sha256:3016f449…`
- Hardware: NVIDIA GB10 (SM121)
- Model example: `unsloth/Qwen3.6-35B-A3B-NVFP4-Fast` @ `1c3f884b…`
- FlashInfer 0.6.14

**MEASURED_ON_THIS_BUILD.**  
**NOT_A_GENERAL_CUTLASS_ALL_CLEAR** for every GB10 system or every vLLM release.

## Symptom

Operator sets `VLLM_FLASHINFER_MOE_BACKEND=latency` (community guidance for SM121).  
Server starts cleanly, health checks pass, service serves. Configuration appears active. It is not.

## Mechanism

1. Surrounding launch process accepts an invented / unsupported environment variable.
2. vLLM logs `Unknown vLLM environment variable detected: VLLM_FLASHINFER_MOE_BACKEND`.
3. Startup still succeeds; health checks pass.
4. Engine proceeds with the real control: `--moe-backend` (default `auto`), printed later as `moe_backend='auto'`.
5. Operator confidence diverges from resolved configuration.

## Runnable check

1. Launch with `-e VLLM_FLASHINFER_MOE_BACKEND=latency` and without an explicit `--moe-backend`.
2. Grep startup log for the unknown-env warning and for the resolved `NvFp4 MoE backend` / `moe_backend=` line.
3. Confirm the warning appears and the resolved backend is not forced by the env var.
4. Control: launch with `--moe-backend marlin` and confirm the selection line changes.
5. Follow-up (pending, **not blocking**): `auto` with the env var removed.

## Relationship to Trap 77

Trap [77](../traps/reasoning/77-only-one-request-field-is-validated.md) is the same **unvalidated-control** failure shape at the **request** surface.  
Issue #19 is the same shape at the **startup/configuration** surface.  

**Proposed cross-reference (not a silent rewrite of Trap 77):** add a “related surfaces” note pointing here when Trap 77 is next edited under evidence rules.

## Performance claims (separated; fully caveated)

Contributor noted ~70 tok/s single-stream decode with thinking ON. **Do not publish flat.**  
Caveats from the reporter: n=1, reasoning-token throughput not answer-token, prefix-cache effects.  
Core trap intake does **not** depend on that figure.

## Credits

- Measurement and report: **@scottleimroth**
- Diagnostic help and registry framing: **@Blackwellboy**

## Disposition

- Issue #19 remains **OPEN** until a numbered trap entry (if any) lands.
- Final auto-with-variable-removed control is useful follow-up, not a prerequisite for intake or credit.
