# Open trap issue governance

This is a **public governance surface only**. It does not contain raw evidence, unpublished mining notes, private source harvests, or private candidate packets. Those do not belong in this public repository.

Every currently open issue whose title begins `[trap]` must appear here with criteria written before adjudication. The integrity gate compares this file against live GitHub issue state.

Coverage snapshot: the doctor implements checks for **19 of 137** entries.  118 uncovered entries remain outside automated doctor checks.

## OPEN

### Q71. SGLang answers a request naming a model it does not serve

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/71
- **CONFIRM.** On a serve whose resolved server state proves model A is loaded, send an OpenAI-compatible request naming a different model B that is not served. Confirm the server returns ordinary HTTP-200 assistant content rather than rejecting the model mismatch, while a control stack that validates model identity rejects the same mismatch.
- **REFUTE.** The mismatched model request is rejected, or resolved server state shows the supposedly mismatched name is actually served.
- **Boundary.** This queue records the public issue and its adjudication criteria only; raw reproduction artifacts are not stored here.

### Q72. Omitted reasoning effort resolves to the most expensive setting on the reported SGLang path

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/72
- **CONFIRM.** On the same pinned lane, compare rendered/request accounting for omitted effort and the model's maximum effort setting, with at least one lower explicit effort control. Confirm omission matches the maximum while the explicit lower setting is measurably distinct, and separately verify any server-side default override if claimed.
- **REFUTE.** Omission does not match the maximum setting under the pinned protocol, or the alleged client effort knob is genuinely inert across the controls.
- **Boundary.** Generation wall time is supporting evidence, not the sole mechanism test; the public issue's deterministic prompt-token/rendering control is preferred.

### Q73. Reload-to-reload score drift is removed by deterministic/autotune pinning on the reported stack

- **Public issue.** https://github.com/Blackwellboy/model-serving-minefield/issues/73
- **CONFIRM.** Reproduce reload-to-reload teacher-forced score movement under the reported stock launch, then repeat matched reloads with deterministic inference enabled and FlashInfer autotune disabled. Confirm per-item score movement collapses to zero (or the preregistered deterministic tolerance) without a material quality or throughput regression.
- **REFUTE.** The stock reload drift cannot be reproduced under the pinned protocol, or the drift persists after deterministic/autotune pinning.
- **Boundary.** A successful pin establishes this stack-specific remedy; it does not prove the same flags solve within-load nondeterminism on other engines/models.

## Privacy rule

Raw candidate research and unpublished evidence are not a public-repository surface. Public promotion starts from a deliberately scrubbed/adjudicated change, not by copying a private research directory into this repository.
