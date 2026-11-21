# Trap 174: system-prompt drift can turn a literal command into a tool-discovery detour

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Controlled prompt ablation,
frozen replay and live first-action tests on a first-party agent stack; the
raw sessions are not published.

**Symptom.** You ask an agent to run a literal command, such as `git status`.
Instead of running it, the agent searches for imagined wrappers, loads
unrelated skills, reads configuration and explores binaries. The endpoint,
model and tools are all healthy, and the same model did the obvious thing last
week.

**Mechanism.** Help text injected into the assembled system prompt can
override the literal-action path. A guidance paragraph telling the agent to
load a skill or discover helper commands before troubleshooting primes an
invented workflow, and the detour compounds into extra tool calls and
no-progress loops even though the request was unambiguous. The template, the
skills and any framework updates all write into the same assembled prompt, so
the change that caused it may not look like a prompt change.

**Stacks and builds bitten.** A first-party autonomous-agent stack with a
locally served tool-calling model, 2026-09-14. With the same weights, server,
tools and user message, the first action changed when only the assembled
system guidance changed. The fix was sealed with 23 assembled-prompt tests, 8
frozen replays, the existing 61 guardrail tests and a live smoke test.

**The check.** Freeze the model, server, tools and user input, and A/B only
the suspect guidance block. Record the first action for several literal
requests: a health command, `git status`, a Python version command and a
simple file listing. Confirmed when the suspect guidance consistently replaces
the requested action with discovery or detour behaviour and the fixed guidance
restores it. Refuted when the behaviour persists without the block.

**The fix.** Write the invariant into the prompt: when the user explicitly
asks to run a concrete, available command, run it first unless safety or a
missing capability blocks it. Do not name imaginary wrappers even in negative
guidance. Seal it with assembled-prompt tests and a live replay, and diff the
assembled prompt (not the template file) after every framework or skill
update.

**Found.** 2026-09-14, investigating an agent that stopped honouring literal
command requests.

**Attribution.** Blackwellboy.

**Related.** [06](../reasoning/06-identity-sentence-eviction.md),
[04](04-history-reasoning-stripping.md).
