# Playbooks

Four ordered checklists, for the four jobs people are actually doing when
they arrive here. Each step names the entry it guards against and the check
to run, so you can work top to bottom and stop when the lane is clean.

Nothing in a playbook is new. Every step is a published entry in this
registry, sequenced. If a step surprises you, follow its link: the entry
carries the mechanism, the status label, and what was and was not measured.

| Playbook | Use it when |
|---|---|
| [Before you publish an A/B](before-you-publish-an-ab.md) | You have a delta between two arms and you are about to write it down |
| [Thinking died when I made it multi-turn](thinking-died-multi-turn.md) | Single-turn reasons, multi-turn does not, and the model still sounds fine |
| [Porting a harness to a new server](porting-a-harness.md) | Code that measured correctly on one stack is now pointed at another |
| [Long context looks broken](long-context-looks-broken.md) | A long window accepts your prompt and answers from nowhere near the start |

## One rule that belongs to all four

**Readiness is a completed generation, not an endpoint answering.** Wherever a
playbook says "wait for the lane", that means one small request with a real
token budget that returns content. `/v1/models` answering is not readiness: on
most stacks that route responds as soon as the HTTP server binds, which is
minutes before a large checkpoint can generate. The full statement, and the two
things it has already cost, are in
[doctor/README.md](../doctor/README.md#readiness-is-a-completed-generation-not-an-endpoint-answering).

## If you would rather not work through a list

[Run the doctor](../doctor/) against the endpoint. It implements checks for
18 of this registry's 97 numbered entries, it is a thinking-stack preflight
rather than a broad bill of health, and it prints its own coverage every run.
