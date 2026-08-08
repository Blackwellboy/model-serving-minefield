# Playbooks

Ordered checklists for jobs people are actually doing when they arrive here.
Symptom playbooks name the entry each step guards and the check to run.

Nothing in a **symptom** playbook invents a new trap. Every step is a published
entry in this registry, sequenced. If a step surprises you, follow its link:
the entry carries the mechanism, the status label, and what was and was not
measured.

Research-integrity playbooks document how to keep **target bugs** distinct from
**research-stack bugs** (harness, scorer, agent evidence). They do not allocate
trap numbers.

| Playbook | Use it when |
|---|---|
| [Before you publish an A/B](before-you-publish-an-ab.md) | You have a delta between two arms and you are about to write it down |
| [Thinking died when I made it multi-turn](thinking-died-multi-turn.md) | Single-turn reasons, multi-turn does not, and the model still sounds fine |
| [Porting a harness to a new server](porting-a-harness.md) | Code that measured correctly on one stack is now pointed at another |
| [Long context looks broken](long-context-looks-broken.md) | A long window accepts your prompt and answers from nowhere near the start |
| [Reading a soak](reading-a-soak.md) | One configuration ran for hours and you are about to call a moving aggregate "drift" |
| [Agentic research integrity](agentic-research-integrity.md) | Agent/harness evidence must not self-certify; lifecycle and Evidence Packet |
| [Minefield repro loop](minefield-repro-loop.md) | Pin → hypothesise → control → attribute → promote (doctrine only) |

**One caveat on the newest of the five.** [Reading a soak](reading-a-soak.md) is
the only playbook whose steps are not all previously published entries: its
weighted-aggregate reasoning is adapted from
[Hikari's per-domain evaluation discipline](https://github.com/hikarioyama/Hikari-knowledge)
(MIT), and the measured Simpson's-paradox example in it is ours and new. It is
credited in the playbook text.

## One rule that belongs to all seven

**Readiness is a completed generation, not an endpoint answering.** Wherever a
playbook says "wait for the lane", that means one small request with a real
token budget that returns content. `/v1/models` answering is not readiness: on
most stacks that route responds as soon as the HTTP server binds, which is
minutes before a large checkpoint can generate. The full statement, and the two
things it has already cost, are in
[doctor/README.md](../doctor/README.md#readiness-is-a-completed-generation-not-an-endpoint-answering).

## If you would rather not work through a list

[Run the doctor](../doctor/) against the endpoint. It implements checks for
19 of this registry's 116 numbered entries, it is a thinking-stack preflight
rather than a broad bill of health, and it prints its own coverage every run.
