# U15: the checkpoint says MTP, but the loader discards the MTP weights

**Reported by @druide67.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: none.** The issue contains useful contributor/source analysis and related PR work, but this entry does not elevate that to maintainer reproduction.

**Issue state: open.** Issue #1292 remains open. Related native-MTP PR [#990](https://github.com/ml-explore/mlx-lm/pull/990) is also open as of this audit.

**Primary source.** [ml-explore/mlx-lm issue #1292](https://github.com/ml-explore/mlx-lm/issues/1292) and related [PR #990](https://github.com/ml-explore/mlx-lm/pull/990), read on 2026-08-14.

**Symptom.** Qwen3.6 checkpoints labelled as MTP variants behave very differently from their non-MTP MLX counterparts in a repeated-prefix/new-user pattern: the first/cold and exact-repeat requests can complete normally, while a request reusing the system prefix with a different user message can terminate after only a handful of tokens despite a much larger requested cap. The response JSON and completion-token count remain internally consistent, so this is not merely an output parser dropping text.

The original report suspected a speculative-EOS path. Later source inspection in the issue changed the important part of the diagnosis.

**Mechanism boundary from source inspection.** Contributors inspecting `mlx_lm/models/` found multiple loaders filtering out keys containing `mtp.` rather than using those tensors at runtime. In the affected Qwen path, MTP-weight presence could also participate in a sanitation predicate that shifted norm weights. Discussion around PR #990 separates that norm-shift condition from mere MTP presence while adding native MTP support.

That establishes a strong loader/runtime mismatch: **an MTP-labelled checkpoint did not imply that MLX-LM was actually executing its MTP head.** It does **not** by itself prove that discarded MTP weights or the norm-shift predicate is the sole cause of every truncated response in #1292.

**Why this is worth an entry.** Capability labels belong to artifacts; benchmark claims belong to executed paths. If a loader silently drops the feature weights, comparing "MTP model" against "non-MTP model" is not a speculative-decoding A/B. It may instead be comparing two differently sanitized ordinary autoregressive loads.

This is the same Minefield discipline as quantization-path verification: inspect what the runtime actually consumed, not what the file name promises.

**What we have not done.** We have not run MLX-LM with these checkpoints and have not reproduced the prefix-dependent truncation. We also have not independently adjudicated every loader named in the issue comments. The source/PR state is recorded as upstream evidence only.

## If you have this stack

Use an affected MLX-LM revision and matched MTP/non-MTP variants of the same model family. First inspect/load logs or instrument sanitation to count whether `mtp.*` tensors are retained. Then run the issue's four-phase pattern: cold `(system A, user X)`, exact warm repeat, same system with user Y, then return to user X.

**CONFIRM.** On the affected path, MTP tensors are discarded or otherwise not executed as a draft head, and the MTP-labelled variant reproduces the short cross-user completion while the matched base does not. Preserve the sanitation path and EOS set separately so one observation is not silently used to prove the other.

**REFUTE.** The allegedly affected revision actually retains/executes the MTP head and the matched MTP/base variants behave the same on the four-phase request pattern. Report the exact conversion and loader revision because PR #990 changes this area materially.

## Attribution

Reported by @druide67. Source investigation in the issue includes contributions from @kru2710shna and @AirRunner; native-MTP work is tracked in PR #990.
