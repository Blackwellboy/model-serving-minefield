# Trap 17: "each arm at its recommended settings" is a hidden confound

**Found by @apollo-mg; replicated by Blackwellboy.**

**Status: reported by others (disclosed by the author) and the confound's effect reproduced here.**

**Symptom.** An A/B comparison shows a clean effect (thinking on beats
thinking off, mode X beats mode Y), and the effect will not replicate under
tighter control. Nothing was hidden; each arm simply ran at its own
"card-recommended" settings, and the settings difference did the work.

**Mechanism.** Model cards recommend different sampling per mode (the case
in point: t0.7 for thinking on, t0.6 for thinking off). Running each arm
"as recommended" is defensible for measuring shipped defaults, but it means
the comparison has two variables. The original finding here was a +2.64
point HumanEval+ win for thinking-on, measured honestly and with the
sampling difference **disclosed in the data drop**
([the disclosure](https://github.com/TheTom/offlabel/pull/10#issuecomment-5083959940)).
Our replication with sampling identical across arms (t0.7 both, 3 seeds,
164 problems, 984 requests): **the accuracy effect vanishes** (paired per
problem: 10 favor ON, 13 favor OFF, 141 tied), while the flakiness
reduction survives
([pr10-replication](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/pr10-replication)).

The general form: any per-arm difference that rides along with the variable
under test (sampling, budget, template, quant) becomes the finding. Trap 12
is the budget version; this is the sampling version.

**Stacks and builds bitten.** llama.cpp fork, Q2_K_XL on quad P100
(original); vLLM NVFP4 on GB10 (replication). Cross-quant, cross-stack.

**The check.** For every A/B, list every request parameter that differs
between arms. If the list is not exactly the variable under test, either
fix the parameters or state the comparison as "shipped-defaults versus
shipped-defaults", which is a different claim than "X versus Y".

**The fix.** Control the confound and re-run before publishing a mode
effect. When you cannot, publish the parameter table next to the result so
the reader can see both variables, which is what the original author did
and what made the clean replication possible at all.

**Found.** 2026-07-26, in the public thread.

**Attribution.** @apollo-mg (original data with the disclosure that made
this checkable); Blackwellboy (controlled replication).

## Added 2026-07-28: a family where the card-versus-config answer differs per member

**NVIDIA Nemotron 3 family, three checkpoints (Nano 30B A3B NVFP4, Nano Omni 30B A3B NVFP4, Super 120B A12B NVFP4), GB10-class single nodes, vLLM 0.20.0 and 0.25.1.** That the answer differs by member *is* the trap:

| Member | Card | `generation_config.json` | Agree |
|---|---|---|---|
| 30B | temp 1.0 / top_p 1.0 reasoning; 0.6 / 0.95 for tool calling | temp 1.0 / top_p 1.0 | reasoning yes; the tool-calling recommendation exists **only in card prose**, and clients must apply it per request |
| 120B | temp 1.0 / top_p 0.95 for everything | temp 1.0 / top_p 0.95 | yes |
| 30B multimodal | thinking mode `max_tokens` 20480, grace 1024 | `max_tokens` 16384, grace 512 | **no** |

The multimodal member logs the override at startup: `Default vLLM sampling
parameters have been overridden by the model's generation_config.json`. A
request that omits `max_tokens` is therefore capped below the card's own
recommendation, which interacts directly with
[trap 12](12-empty-content-at-token-ceiling.md).

Checked and **not** a finding: the file at the default branch is byte-identical
to the file at the pinned revision, so this is a card-versus-file disagreement
and not revision drift. Recorded because drift is the obvious first hypothesis
and ruling it out is what makes the rest of this readable.

The generalisable point: **"this family's card and config agree" is not a family
property.** Check per member, per revision.

*Status of this addendum: reproduced here. Cards, configs and revisions are all
public.*
