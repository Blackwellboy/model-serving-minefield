# Trap 42: a single-turn eval harness scores tool calls as wrong answers, and systematically understates agent-configured models

**Found by [@apollo-mg](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067).**

**Status: reported and measured at scale by its finder (n=492), with raw
published; the underlying exit-path mechanism independently measured on a
second stack.**

**Symptom.** You attach an agent system prompt and tool schemas to a model,
re-run your benchmark, and the score falls by a large margin. The obvious
reading is that the apparatus made the model dumber. Check the wrong-answer
count before you accept that reading: if wrong answers are flat while the
score dropped, the model did not get worse at answering. It stopped
answering, because it routed to a tool and your harness has no bucket for
that, so a tool call lands in the same bin as a wrong answer.

**Mechanism.** A single-turn harness has exactly two outcomes: the sample
scores, or it does not. A model given tool schemas has a third legal exit,
`finish_reason=tool_calls`, which is neither a right answer nor a wrong one.
It is the model doing what you configured it to do. Fold that third exit
into the failure bucket and every agent-configured evaluation you run is
biased downward by whatever fraction of samples route, which is a property
of your system prompt, not of the model's capability.

The same structural fact bites the reasoning-depth measurement, which is why
this is one trap and not two. A turn that exits via a tool call carries only
the reasoning the model produced before deciding to call, so the reasoning
episode is truncated at the tool boundary. Pool that with turns that answered
directly and the median reasoning length collapses for mechanical reasons.
Measured as score it looks like a capability loss; measured as depth it looks
like reasoning suppression. It is neither. It is one exit path being counted
as if it were another.

**Magnitude, with full conditions.** @apollo-mg, offlabel PR #10
([comment 5093534067](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067),
2026-07-27). Laguna S 2.1 UD-Q2_K_XL, llama.cpp, 4x Tesla P100 (sm_60) at
1063 MHz / 150 W, `-c 32768 -np 1 -ngl 99 -sm layer -ts 1,1,1,1 -fit off`.
HumanEval+, all 164 problems x K=3 = 492 samples, temperature 0.7 /
top_p 0.95 / top_k 20, max_tokens 16000, thinking at template default,
elapsed 58,300 s. Every parameter identical to his own 90.85% baseline
except the apparatus: a 752-byte agent system prompt plus 3 tool schemas.

| | baseline | with apparatus | delta |
|---|---|---|---|
| pooled pass@1 | 90.85% | 71.95% (354/492) | -18.90 points |
| WRONG | 30 | 31 | +1 |
| TOOL_CALL | 0 | 106 | +106 |
| no extractable answer | 11 | 0 | -11 |
| cap-hits / TRUNCATED | 12 | 1 | -11 |
| flaky problems | 11/164 | 73/164 | +62 |

Conditional on the sample attempting an answer: 354/386 = 91.71%, against
the 90.85% baseline, inside the +/- 1.49% per-sweep spread. So 18.9 points
of measured score, and approximately zero points of answering ability.
Thinking fired on 445/492 samples (90.4%), mean reasoning_content 4,686
chars, in the most coding-shaped cell in the thread.

**Raw is published**, which is what makes this reproducible rather than
quotable:
[laguna_apparatus_raw_20260727.tar.gz](https://github.com/user-attachments/files/30425710/laguna_apparatus_raw_20260727.tar.gz)
(12.7 KB, attached to
[comment 5094074898](https://github.com/TheTom/offlabel/pull/10#issuecomment-5094074898)):
the 752-byte system prompt verbatim, the 3 tool schemas, per-sample buckets
and token counts for all 164x3, the full run log, and the driver log with
clock state. The prompt is the piece you need to replicate the routing rate,
since routing is a property of the prompt.

Two limits he states himself and that belong with the number: the tools were
passed but never called back, so no tool output re-entered context and this
measures schema-presence routing rather than a real agent loop; and it is one
quant, one model, one system prompt, and that prompt is one point in a large
space that could route more or less aggressively. He has since sharpened the
first limit further: all three tools (`read_file`, `write_file`,
`run_command`) are useless for self-contained function-completion prompts, so
all 106 calls routed toward information that does not exist, which makes
21.5% a turn-1 transient rather than a floor or a ceiling
([comment 5094152476](https://github.com/TheTom/offlabel/pull/10#issuecomment-5094152476)).

Independent measurement of the same exit-path mechanism on the depth side, on
different hardware and runtime: Laguna S 2.1 NVFP4 under vLLM 0.25.1 on GB10
(sm_121), 200 turns, 5 arms x 4 tasks x 10 samples, in-run interleaved.
Reasoning depth among fired turns was statistically flat across arms with and
without tool schemas (all pairwise Mann-Whitney p >= 0.13; the tools arm
carried the highest median), while turns exiting via `tool_calls` carried
median 462 and 136 estimated reasoning tokens against 1293 and 847 for turns
that answered directly and roughly 3100 for turns that ran to ceiling
([c7-depth-collapse](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/c7-depth-collapse)).

**Stacks and builds bitten.** Stack-independent. It is a property of the
harness, not the server. Confirmed on llama.cpp with a GGUF build on P100
(sm_60) and on vLLM with an NVFP4 build on GB10 (sm_121). Any harness that
maps a completion to pass/fail without inspecting the exit path is exposed,
including harnesses that never attach tools, because the bias only appears
once someone else runs your harness against an agent-configured model and
compares to your published number.

**The detection fingerprint.** Two checks, both cheap and both offline:

1. **Conditional against pooled.** Compute accuracy conditional on the
   sample having attempted an answer, and compare it to pooled pass@1. If
   conditional accuracy is flat against your no-apparatus baseline while
   pooled dropped, the drop is routing, not capability. A flat or nearly
   flat wrong-answer count with a large pooled drop is the same signal seen
   from the other side, and it is visible without recomputing anything.
2. **Bucket by exit path, not by score.** Every sample lands in exactly one
   of: scored answer, wrong answer, tool call, truncated at the cap, no
   extractable output. Print the five counts. A harness that cannot produce
   this table is a harness that cannot tell you which of five different
   things happened, and the four non-answer buckets have four different
   fixes.

A useful secondary signal: per-problem flakiness that explodes while answers
stay stable. Bucket patterns like `T,P,P` and `P,T,P` across K seeds on one
problem are the route varying, not the answer varying. If your flakiness
metric cannot distinguish those, it will report answer instability that is
not there.

**The fix.** Any one of these, in increasing order of effort:

- Bucket tool-call exits separately and report both pooled and
  conditional-on-attempting accuracy, with the bucket counts alongside.
  Never report only pooled for an agent-configured arm.
- State the apparatus with the score. "pass@1 71.95%" and "pass@1 71.95%
  under a 752-byte agent prompt plus 3 tool schemas, 21.5% of samples
  routing to a tool" are different numbers, and only one of them can be
  compared to somebody else's run.
- Give the harness a tool-return path so the sample can continue after a
  call. This is the only option that actually measures the agent loop rather
  than measuring the routing decision, and it is the only one that tells you
  whether the termination result below survives a tool result coming back.

**What this does to comparisons.** Apparatus dose alone, with regime held
fixed at single-turn codegen, moved measured score by 18.9 points with
capability flat. So a comparison between a no-apparatus benchmark run and an
apparatus-bearing agentic run cannot attribute its difference to regime.
Apparatus alone accounts for a swing of that size. If you are running a
regime comparison, hold the apparatus fixed or you have confounded the two.

**A secondary result worth carrying, and it is open.** In the same cell the
termination failures disappeared: no extractable answer 11 -> 0, cap-hits
12 -> 1. Those 11 samples had been the entire ON-versus-OFF gap in the
original finding. Giving the model a legal exit that is not "keep
generating" appears to prevent the degeneration mode, which would be a
structurally different fix from detecting a loop after it starts (see the
loop-signature discussion on the same thread: unique-line ratio 0.086 on a
persistent looper against 0.5 to 0.6 on non-loopers).

This is untested with tool output fed back, and both parties have put a
prediction on record before the test rather than after it. The finder
predicts the termination benefit does not survive feedback, and would count
tool-call looping as the same non-termination wearing a different bucket
label. The counter-position is that the benefit survives per turn and fails
per task, because the tool boundary truncates the reasoning episode before a
degeneration loop can develop, so a cap-hit becomes structurally unreachable
inside one turn while the failure migrates to the turn axis. The
discriminating arm is cheap: return a fixed unhelpful result from every tool
(`{"error": "no such file"}`, empty stdout) and re-run the same cell. Until
that runs, cite the termination result as measured under
schema-presence-only, never as a general property of giving a model tools.

**Sibling trap.** See trap
[31](31-leftover-oracle-reranker.md) for the same class from a different
direction: your harness is measuring something other than what you think it
is measuring, and the aggregate looks plausible either way. In both cases the
number is not wrong arithmetically. It is answering a different question than
the one in your title. Related: trap
[16](16-finish-reason-is-not-a-failure-signal.md), which is the same mistake
one layer down, at the level of a single field.

**Found.** 2026-07-27, published in a public thread with full conditions;
raw published 2026-07-27.

**Attribution.** [@apollo-mg](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067)
(the cell, the magnitude, the conditional-accuracy framing, the published
raw, and the self-correction of his own earlier 15-problem 2x2 that had
overstated the effect at small n). Blackwellboy (the depth-side exit-path
measurement on a second stack).
