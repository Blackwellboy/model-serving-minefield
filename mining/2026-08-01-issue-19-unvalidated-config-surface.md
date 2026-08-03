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
Do **not** state that all unknown environment variables behave identically across all vLLM versions.

## Symptom

Operator sets `VLLM_FLASHINFER_MOE_BACKEND=latency` (community guidance for SM121).
Server starts cleanly, health checks pass, service serves. Configuration appears active. It is not.

## Mechanism (`UNVALIDATED_CONFIGURATION_SURFACE`)

**Core trap:** An unsupported `VLLM_`-prefixed environment variable can be accepted by the surrounding launch process while vLLM only logs a warning and continues with its real configured/default value.

On this measured path:

1. Surrounding launch process accepts an invented / unsupported environment variable.
2. vLLM logs `Unknown vLLM environment variable detected: VLLM_FLASHINFER_MOE_BACKEND` (e.g. `envs.py:2096`).
3. Startup still succeeds; health checks pass (default validation is warn-only).
4. Engine proceeds with the real control: `--moe-backend` (default `auto`), printed later as `moe_backend='auto'`.
5. Operator confidence diverges from resolved configuration.

## Environment-level control - COMPLETE (`ENV_CONTROL_COMPLETED=YES`)

Contributor @scottleimroth completed a matched absent/present control on the same image
`vllm/vllm-openai:v0.26.0-aarch64-ubuntu2404` (env validation runs before engine init; no GPU/downtime required):

| Condition | Result |
|---|---|
| variable **absent** | no unknown-variable warning |
| variable **present** | `WARNING [envs.py:2096] Unknown vLLM environment variable detected: VLLM_FLASHINFER_MOE_BACKEND` |

**Source confirmation (vLLM 0.26):**

- `VLLM_FLASHINFER_MOE_BACKEND` is **absent** from `vllm.envs.environment_variables` in vLLM 0.26;
- `validate_environ()` treats it as unknown;
- the serving path never reads it.

This completes the **environment-level** half of the control. It proves the candidate name is unknown and is not consumed by serving configuration on this build.

## Recommended fail-fast mitigation

vLLM 0.26 exposes **`--fail-on-environ-validation`** (default **false**).

When enabled, an unknown `VLLM_`-prefixed variable causes startup to fail (e.g. `ValueError: Unknown vLLM environment variable detected: …`) rather than a clean-looking start with only a buried warning.

**Primary mitigation for this trap class on builds that support the flag:** enable `--fail-on-environ-validation`.

## Engine-level backend-selection control - COMPLETE (`ENGINE_CONTROL_COMPLETED=YES`, 2026-08-02)

Contributor @scottleimroth completed the engine-level half
([issue #19 comment, 2026-08-02](https://github.com/Blackwellboy/model-serving-minefield/issues/19#issuecomment-5160329265)):

- `VLLM_FLASHINFER_MOE_BACKEND=latency` was **removed entirely** from the docker invocation;
- the container was **recreated fresh** (`docker rm -f` + `docker run`, not a container restart), forcing a real same-checkpoint engine initialisation;
- the startup log selected the **identical** backend: `Using 'FLASHINFER_CUTLASS' NvFp4 MoE backend out of potential backends: [...]`;
- **zero** `Unknown vLLM environment variable` warnings appeared (contributor confirmed the variable was genuinely absent, not merely unlogged).

**Conclusion (this checkpoint/backend combo, this build):** the variable is a **no-op**.
Backend resolution is identical with the variable present or absent.
`--moe-backend` is the actual engine-level control.

This closes the engine-level half of the control. It is still
**NOT_A_GENERAL_CUTLASS_ALL_CLEAR**: the no-op finding is scoped to this vLLM 0.26.0
image / checkpoint / backend configuration, not to every GB10 system or every vLLM release.

Issue remains open until trap promotion decisions are resolved.

## Supporting (non-primary) second checkpoint

Contributor reported that **Qwen3-Next-80B-A3B-NVFP4** on the same image/GPU also selected `FLASHINFER_CUTLASS` with the variable present. The original env warning was **not retained** for that removed container. Preserve as contributor-reported supporting context only - **not** equivalent raw evidence to the matched pair / source check above.

## Primary check (operators)

1. Compare logs with the candidate variable **absent** and **present**.
2. Inspect the resolved engine configuration (`moe_backend` / `NvFp4 MoE backend` line).
3. Enable `--fail-on-environ-validation` where supported.
4. Optional explicit control: launch with `--moe-backend marlin` and confirm the selection line changes.
5. Engine follow-up (completed 2026-08-02): `auto` with the env var removed on a real same-checkpoint fresh-container init resolved `FLASHINFER_CUTLASS` identically, with no unknown-variable warning.

## Original startup log provenance

The original intact issue #19 startup log remains primary provenance for the original symptom report (unknown-env warning while service looks healthy). Env matched-pair + source confirmation above strengthen the environment-level half; they do not replace the original log for the production-looking failure shape.

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

- Issue #19 remains **OPEN** (trap promotion unresolved).
- **No numbered trap assigned.**
- Environment-level matched control: **complete**.
- Engine-level backend-selection control: **complete** (2026-08-02; this checkpoint/backend combo only).
- Both controls are useful evidence, **not** a prerequisite for retaining contributor credit or the intake record.
