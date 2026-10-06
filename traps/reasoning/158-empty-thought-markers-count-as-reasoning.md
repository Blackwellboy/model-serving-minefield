# Trap 158: empty thought markers can make thinking-off report two reasoning tokens after tools

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #175](https://github.com/Blackwellboy/model-serving-minefield/issues/175)); mechanism inspected in the checkpoint's own template.

**Symptom.** A verifier asserts `reasoning_tokens == 0` for thinking-off requests and fails on some multi-turn tool interactions even though the reasoning field is empty and no reasoning text is visible.

**Mechanism.** On the measured Gemma 4 template branch, a post-tool generation boundary may omit the empty thought shell the template supplies elsewhere. The model then emits the opening and closing thought-channel tokens itself with nothing between them, and the reasoning parser counts the two marker tokens.

**Stacks and builds bitten.** vLLM 0.28.0, `nvidia/Gemma-4-26B-A4B-NVFP4` revision `a19cfe00`, Gemma4 reasoning/tool parsers, DGX Spark. Observed 39/157 agent requests; single-turn and no-tool controls stayed at zero.

**The check.** Inspect both parsed reasoning text and raw/reported reasoning-token count across single-turn, ordinary multi-turn and post-tool-turn cases. Treat exactly an empty marker pair differently from substantive reasoning.

**The fix.** Verify thinking-off from semantic reasoning content, or explicitly allow the exact empty two-marker case on the matched template/parser revision. Non-empty reasoning must still fail.

**Found.** 2026-10, Gemma 4 agent verification.

**Attribution.** @scottleimroth.
