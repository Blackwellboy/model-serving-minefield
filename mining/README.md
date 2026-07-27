# Mined candidates: verification notes

Registry entries under `traps/` are verified traps. This directory is the
step before that: candidates mined from upstream issue trackers and community
reports get tested on real hardware, and the result is recorded here whether
or not it promotes.

Three outcomes land here:

- **Did not reproduce on our stacks.** A negative is information. It scopes
  the candidate (often to the stack the upstream report actually ran on) and
  saves the next tester the probe time.
- **Not testable on current lanes.** Recorded with exactly what is missing
  and what a test would look like, so anyone with the missing piece can run
  it.
- **Partial or small-n results** that do not meet the entry bar yet.

Candidates that verify get promoted into `traps/` per
[MAINTAINING.md](../MAINTAINING.md) and leave a pointer here. Candidate IDs
(R2-NN) refer to our mining rounds; the upstream source is linked in each
note.

## Notes

| Date | Candidate | Result |
|---|---|---|
| 2026-07-27 | [R2-39 thinking plus tools yields empty output](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md) | Did not reproduce on vLLM; scoped to Ollama pending an Ollama-side test |
| 2026-07-27 | [R2-31 DeepSeek V4 system-message quality cliff](2026-07-27-r2-31-deepseek-v4-system-message-no-cliff-small-n.md) | Did not reproduce at small n; system-independent behavior measured; stays open pending an upstream recipe |
| 2026-07-27 | [R2-27 / R2-23 / R2-10 / R2-29 blocked](2026-07-27-r2-blocked-not-testable.md) | Not testable on current lanes; each note says what a test needs |
