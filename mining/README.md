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

**[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) is the queue above all of this**: every
question currently unsettled, each with its source marked PRIMARY or secondary,
the hardware it needs, and its CONFIRM and REFUTE criteria written down **before**
anyone runs it. It also records settled dispositions, so a closed question stays
closed. Start there if you want to know what is open rather than what is done.

## Notes

| Date | Candidate | Result |
|---|---|---|
| 2026-07-27 | [R2-39 thinking plus tools yields empty output](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md) | Did not reproduce on vLLM; scoped to Ollama pending an Ollama-side test |
| 2026-07-27 | [R2-31 DeepSeek V4 system-message quality cliff](2026-07-27-r2-31-deepseek-v4-system-message-no-cliff-small-n.md) | Did not reproduce at small n; system-independent behavior measured; stays open pending an upstream recipe |
| 2026-07-27 | [R2-27 / R2-23 / R2-10 / R2-29 blocked](2026-07-27-r2-blocked-not-testable.md) | Not testable on current lanes; each note says what a test needs |
| 2026-07-28 | [Greedy is not reproducible on this stack: our agreement floor](2026-07-28-our-agreement-floor-greedy-not-reproducible.md) | Q2 answered. Pooled 3513/3600 = 97.58% item agreement between identical runs; cross-machine pairs straddle the within-process pair, so machine identity is not the variable. Promoted trap 35 to reproduced-here. Calibration: plus or minus 1.3 pts at n=600 for MMLU-style paired comparisons, and explicitly NOT transferable to binary-outcome results |
| 2026-07-28 | [qwen36-a6b traps 33 to 41: verification queue](2026-07-28-qwen36-a6b-verification-queue.md) | Landed as reported-by-others; confirm/refute criteria recorded before running. Trap 33 on NVFP4 is the priority candidate for a reproduced-here upgrade; first-N subsetting bias held back as a candidate for want of a measured magnitude |
| 2026-07-28 | [Chunked prefill versus cache replay on DeepSeek-V4-Flash](2026-07-28-chunked-prefill-vs-cache-replay-experiment.md) | **NOT RUN, specification only.** Pre-registered design that would separate the two candidate mechanisms behind trap [60](../traps/runtime/60-cold-prefill-and-cache-hit-disagree.md). Needs a serve change, so it cannot run on the production lane it was written from; written to be executable by someone else on a scratch serve |
| 2026-07-28 | [R2-29 tool calls as raw text on Nemotron NVFP4](2026-07-28-r2-29-tool-calls-refuted-as-worded.md) | **Refuted as worded, reframed.** Not JSON: the family's call format is nested XML, and on vLLM a request carrying tools without the parser flags is rejected with HTTP 400 rather than degraded, so the plain claim is unreachable there. The reachable path is a request that bypasses the guard. Closes the R2-29 block |
| 2026-07-28 | [R2-39 on Ollama, the stack it was scoped to](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md#update-2026-07-28-tested-on-ollama-refuted-as-stated-and-re-scoped) | **Refuted as stated.** Empty content tracks tools alone, 5/5 with tools in both thinking states and 0/5 without, and every empty response carried a tool call. Not a defect: a harness reading `content` and ignoring `tool_calls`. Closes the Ollama scoping on this candidate |
| 2026-07-28 | [SGLang on GB10: feasibility](2026-07-28-sglang-on-gb10-feasibility.md) | **Not infeasible.** The arm64 wheel exists and `sglang[all]` resolves cleanly on CUDA 13; the open risk is that sm_121 is absent from the torch arch list. Packaging only, no server started |
| 2026-07-28 | [The blocked llama.cpp candidates, adjudicated](2026-07-28-r2-llamacpp-queue-dispositions.md) | Five deferred candidates dispositioned on one lane. R2-16 and R2-41 are **one effect with a prompt-length floor** and promote together to traps 91 and 92; R2-17 is **refuted as worded** and promotes to trap 93, because its mechanism is real at a different position and the received mitigation is inverted; R2-46 promotes to trap 97, stronger than claimed; R2-18's **reporting half** is no longer blocked for hardware and promotes to trap 96, with the cache-sizing half still open. R2-27 stays closed and this pass says why from the other direction. VL reranker and SGLang candidates unchanged |
| 2026-07-29 | [The check that did not check: four cases, one habit](2026-07-29-the-check-that-did-not-check.md) | **One habit, four instances, in a single day.** A defect class fixed in one file and reintroduced in the next by the same reflex; a mutation test that went red because of an older guard rather than the new one; a comment describing a failure it could not prevent; and a status field standing in for a capability probe across a full degradation. Each reads as a slip alone; together they are the pattern, which is why they are one document |
| 2026-07-29 | [Reading an upstream thread before citing it as a primary](2026-07-29-upstream-citation-vetting.md) | **Second instance of a mined candidate whose thread contradicts its own summary.** A hang report was proposed as a class primary on the strength of two flags recommended in the thread; the thread has zero project-affiliated commenters, was closed by the reporter three minutes after he said he had misunderstood the system, and the flag recommendation is a post-close comment from an unaffiliated account linking its own repo. Adds the three fields to read before citing: `author_association` on every comment, who closed it, and what they said immediately before closing |
| 2026-07-28 | [The round-2 queue, worked in full](2026-07-28-r2-queue-classified-upstream-tier.md) | **50 candidates classified with every primary source read.** 11 published into the new [upstream-reported tier](../upstream/), 9 named as already covered by a measured entry, 22 closed as too weak so they stop being re-queued. Six candidates across four classes (out of roughly thirty-five with a primary source we could read) were materially misdescribed by their own mining summaries: two live "engine bugs" had been closed upstream as usage, tracking-index and retracted-author cases among them. Forced corrections to the blocked-candidates note and to OPEN_QUESTIONS |
| 2026-07-28 | [Q1: the top-k expansion tax on NVFP4](2026-07-28-trap-33-q1-nvfp4-confirmed.md) | **CONFIRM.** Promotes trap [33](../traps/routing/33-moe-inference-topk-expansion-tax.md) to reported-by-others + reproduced-here. -4.50 pt at n=600 paired, discordant 37/10, exact McNemar p = 9.8e-05, monotone across four values of k, replicated on an independent pass and in both scoring protocols. Scripts ship; raw does not, because this is not a calibration constant |
