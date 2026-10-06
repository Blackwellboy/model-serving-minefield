# Trap 149: strict JSON schema can pass with thinking off and run to the cap with thinking on

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #158](https://github.com/Blackwellboy/model-serving-minefield/issues/158)).

**Symptom.** A strict `response_format=json_schema` probe looks healthy with thinking disabled, but with thinking enabled the reasoning closes, the answer opens with `{`, never closes, and generation runs to `max_tokens`.

**Mechanism.** On the measured TensorFold path the grammar becomes active only after the reasoning close marker. That establishes where constraint enforcement begins, but the exact reason the JSON never closes remains unproven. The important measurement failure is assuming a thinking-off structured-output probe certifies a thinking-on lane.

**Stacks and builds bitten.** TensorFold 0.5.0 with xgrammar 0.2.8, Qwen3.8-27B-family NVFP4, DFlash2, DGX Spark GB10.

**The check.** Run the same small strict schema with thinking on and off at a budget large enough to distinguish truncation from a short cap. Require `finish_reason=stop`, JSON parse success, and schema validation in both modes.

**The fix.** On the affected build, use strict `json_schema` only in the mode that passes the matched check, or gate thinking-on requests until the serving path is fixed.

**Found.** 2026-09, structured-output qualification.

**Attribution.** @scottleimroth.
