# Trap 139: system-prompt drift can turn a literal CLI command into an invented tool-discovery loop

**Found by Blackwellboy.**

**Status: measured here, raw not published.** First-party frozen-replay and live-agent measurements are retained in the private evidence archive under the 2026-09-14 Hermes CLI-intent regression finding. The public entry preserves the mechanism, bounded reproduction, affected commits, and fix without publishing private session transcripts.

**Symptom.** A user gives an explicit command such as `hermes doctor`, but the agent does not run it. Instead it invents or searches for adjacent control utilities (`hermes-ctl`, `which hermes-ctl`), inspects configuration, rereads files, and can eventually hit no-progress guardrails even though the literal command was valid and available.

The visible failure can look like a model suddenly losing tool competence: many `preparing terminal...` / `preparing read_file...` events, followed by `idempotent_no_progress_block` or another loop guard. The first wrong turn, however, can happen before any tool result, history compaction, retry, or guardrail exists.

**Mechanism.** The assembled agent system prompt changed its Hermes-help guidance. The regressed guidance told the agent to load a skill before configuring, modifying, or troubleshooting Hermes, while the prior prompt also carried positive examples of real `hermes <subcommand>` CLI syntax. On the measured Qwen3.8 controller, that wording changed the interpretation of the user text `hermes doctor` from a literal executable command into a troubleshooting concept. The model then invented `hermes-ctl` even though that string was not present in either compared prompt.

A frozen replay isolated the prompt as the first-action variable: same model, same server, same tool schema, same user message. Historical assembled prompt -> `hermes doctor`; regressed assembled prompt -> `hermes-ctl` / `which hermes-ctl`. Rewriting only the Hermes-help guidance to restore a short positive CLI catalog and the rule "if the user already supplied an explicit CLI command, execute that exact command first" flipped the first action back to `hermes doctor` 10/10. Three fresh live runs then passed with zero `read_file` loops and zero idempotent blocks.

**Stacks and builds bitten.** Measured on Hermes Agent with Qwen3.8-27B-OBLITERATED Q4_K_M served through llama.cpp/TurboQuant. The prompt-regression commit was `5241df3d4a`; the measured production repair landed as `269edce72e93db6111bfabe53dba0e0a41304e8b`. The finding is about agent prompt assembly and should not be read as a Qwen-only defect: Qwen was the measured controller and was sensitive enough to expose the drift.

**The check.** Use a literal-command intent fixture before shipping an agent-system-prompt change. Hold the model, server, tools, sampling, and user message constant, vary only the assembled system prompt, and record the first tool action.

Minimum regression set:

```text
user: hermes doctor       -> first command: hermes doctor
user: git status          -> first command: git status
user: python --version    -> first command: python --version
user: ls /tmp             -> first command: ls /tmp
```

Also keep one non-literal control such as `check whether Hermes is healthy`; it may reason or choose `hermes doctor`, but the fix must not reduce the agent to blind shell passthrough.

A failure is not "the agent eventually recovered". A failure is that an explicit executable command is replaced on the first action by command discovery, invented utilities, config inspection, or unrelated diagnosis without evidence that the literal command is unavailable.

**The fix.** Keep positive examples of the real CLI surface in the assembled agent guidance and state the precedence rule explicitly: when the user supplies an executable CLI invocation, run that exact command first unless it is unsafe or has already been proven unavailable. Test the final assembled prompt, not only SOUL/source fragments, because the causal block in this incident was injected by `prompt_builder.py` after SOUL assembly.

**Found.** 2026-09-14, while diagnosing repeated Hermes terminal/read-file loops that initially looked like a Qwen3.8 agent-policy regression.

**Attribution.** Blackwellboy.

**Related.** [140](140-exact-tool-signatures-miss-semantic-no-progress-loops.md) covers a different failure: the agent does execute tools, but near-duplicate failed strategies evade exact-signature loop guards. [53](../runtime/53-config-edit-never-took-effect.md) is the configuration analogue: an apparently correct change can fail because it never reaches the running path.
