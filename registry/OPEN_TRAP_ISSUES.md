# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **32 of 161** entries.  129 uncovered entries remain outside automated doctor checks.

## OPEN



### Q113. GB10 page cache can impose a large calibration slowdown while `MemAvailable` barely moves

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/113
- **CONFIRM.** On the reported GB10 unified-memory calibration path, use a byte-identical workload and run **counterbalanced repeated arms** with controlled cache seeding: hot-cache → cold-cache and cold-cache → hot-cache, with an untimed/discarded warm-up before each measured sequence and enough repeats to report a preregistered median or other repeated statistic. Preserve workload/manifest identity, `MemFree`, `MemAvailable`, `Cached`, elapsed time and driver-pressure messages for every arm. Confirm the hot-cache condition repeatedly shows materially higher elapsed time while `Cached` and `MemFree` move materially and `MemAvailable` remains nearly unchanged. Do not confirm from a single ordered hot/cold pair.
- **REFUTE.** The counterbalanced repeated hot/cold comparison does not reproduce a material slowdown, `MemAvailable` tracks the condition sufficiently to distinguish the arms, the effect reverses or disappears when order/warm-up is controlled, another launch/workload difference explains the elapsed-time delta, or the reported cache state is not actually present at launch.
- **Boundary.** Treat the reported 62% as one paired comparison on one box, not a universal page-cache tax or confirmation by itself. Do not claim reclaim contention or the driver's `NV_ERR_NO_MEMORY` line is the proven causal mechanism unless independently instrumented. Adjudicate as an extension or separate measurement trap only after semantic dedupe against trap 119's allocation-time page-cache mechanism and trap 54's run-order/warm-cache controls.

### Q172. vLLM Whisper can fail English-only defaults and separately collapse smaller checkpoints when a prompt is injected

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/172
- **Criteria provenance.** Drafted for maintainer review; not yet signed off.
- **CONFIRM.** Treat the issue's two mechanisms as separate matrices on pinned vLLM 0.26. Use the same shareable audio, deterministic settings and repeated requests across English-only and multilingual Whisper checkpoints. For the `.en` matrix, compare an omitted language field with explicit `language=en`, preserve HTTP status and traceback, and require the plain request to fail while the explicit-language control succeeds on the same checkpoint. For the prompt matrix, compare no prompt versus the exact vocabulary prompt across several checkpoint sizes, score transcript error and repetition/empty-output signatures, and include large-v3 as a control. If available, test the corrected previous-context token path and require it to remove the collapse without changing the audio.
- **REFUTE.** English-only checkpoints succeed without language; explicit language does not recover them; prompted and unprompted smaller checkpoints perform equivalently across repeated clips; the prompt body is malformed or exceeds a model limit; or the corrected token path does not change the result.
- **Boundary.** A single synthetic clip cannot support a general accuracy ranking, and the `.en` HTTP failure and prompt-induced transcript collapse may warrant separate canonical entries. Do not state that every checkpoint below large-v3 fails or that `language=en` is a measured fix until that control is run. Scope source claims to the pinned serving path and dedupe against any existing transcription-template or previous-context entries before promotion.

## Privacy rule

Raw candidate research and unpublished evidence are not a public-repository surface. Public promotion starts from a deliberately scrubbed/adjudicated change, not by copying a private research directory into this repository.
