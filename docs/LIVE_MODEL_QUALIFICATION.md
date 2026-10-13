# Live model-serving qualification: safe first-pass protocol

This procedure is for a **user-authorised endpoint**, not a default action performed by the registry. No system process, model, service, scheduler or configuration is changed by this playbook. Doctor and file scans are bounded diagnostics, **not** full performance or safety certification.

## 1. Declare the exact lane

Record one row for each independently served configuration, not just the model family:

| Field | What to record |
|---|---|
| Lane label | A non-identifying local alias such as `spark-a`, `tp2-pair` or `5090-vlm` |
| Endpoint | A local/private authenticated OpenAI-compatible `/v1` URL; never publish internal URLs or keys |
| Stack/build | vLLM, SGLang, llama.cpp, TabbyAPI/ExLlama, MLX or another named server, including image digest/commit |
| Model/artifacts | Exact served ID, checkpoint revision, quantization, tokenizer/processor revision, and any drafter |
| GPU/fabric | GPU class/count; single GPU vs TP topology; exact NCCL, CUDA/ROCm and driver versions when applicable |
| Current state | Production or disposable lane, uptime, memory headroom, active clients, known issues and allowed test window |
| Budget | Maximum generation requests, `max_tokens`, concurrency and acceptable interruption (normally none) |

Do not treat two nominally identical models on different images, templates or GPUs as the same test unit.

## 2. Prerequisites and hard safety limits

- Confirm authority to probe this endpoint, its rate limit, the availability window and whether active users are present.
- Start with **one** reachable lane, not the whole Spark fleet. Record pre-test health and a baseline model-list response.
- Never publish raw credentials, usernames, private addresses, private prompts, unredacted logs or customer content to public GitHub issues.
- First pass: read-only GET/render/tokenize plus a small number of synthetic chat completions. Avoid CUDA graph recapture, service restarts, driver changes, downloads of weights, forced context exhaustion or concurrent load.
- A failed check must not trigger an automatic fix or restart. Stop when transport errors, timeouts or unexpected resource pressure appear.
- Do not enable `trust_remote_code` just to bypass missing MiniCPM processor modules.

## 3. Budget the Doctor pass before network access

First preview the plan offline, without a host URL or credentials:

```bash
minefield doctor-plan --mode lite --max-requests 5 --text
minefield doctor-plan --mode doctor --max-requests 8 > doctor-plan.json
```

For a smaller targeted preview, select named probes explicitly:

```bash
minefield doctor-plan --mode doctor --probe generation_readiness --max-requests 1 --text
```

Use the same `--probe` and budget on a later authorised `minefield diagnose`
call. A MiniCPM-only example is `--mode doctor --probe minicpm_short_answer_channel
--max-requests 2`. When metadata comparisons are approved, `diagnose` now accepts
`--hf-revision` and passes that exact revision through to the checks.

This creates **no** live observations, requests or verdicts. It shows which
registered checks fit the declared chat-generation budget, and which checks
will be skipped. A zero-chat-cost check can still make GET/render/metrics/HF
requests **in a later live run**. The plan cannot prove endpoint capabilities
or hardware applicability. Do not treat planned trap IDs as checked or CLEAN.

For the **first authorised endpoint pass**, prefer the budget-enforced unified
front door to the uncapped standalone Doctor:

```bash
minefield diagnose "baseline endpoint readiness" \
  --base-url "$MINEFIELD_BASE_URL" --mode lite --max-requests 5 \
  --json > doctor-lane-a.json
```

Only the operator should set the trusted private URL and credential. Do not
paste endpoint addresses or unsanitised results into public issues.

## 4. Full standalone Doctor, dedicated test window only

From a checkout of the **exact Minefield main SHA being evaluated**, with an approved local tunnel or trusted endpoint. This standalone command does **not** apply the unified planner's five-chat-request default; use only after reviewing the full budget and confirming an appropriate test window:

```bash
export MINEFIELD_BASE_URL="http://127.0.0.1:8000/v1"
python3 doctor/minefield_doctor.py \
  --base-url "$MINEFIELD_BASE_URL" \
  --json "doctor-lane-a.json" \
  --report
```

For a user-approved public checkpoint comparison, pass `--hf-repo org/model` and **`--hf-revision` matching the served commit**. Do not infer the served checkpoint from its family name. The HF check makes external requests to read metadata; without those flags the public metadata checks remain unavailable.

When testing a declared server token limit or benchmark prompt length, opt in to `--server-max-tokens`, `--benchmark-target-tokens` and `--benchmark-prompt-text` only with known inputs. The check does not infer unreported flags or prove a real benchmark ran from a tokenizer response.

Run `minefield diagnose` with a redacted symptom and explicit public-safe configuration or log paths only when those files are approved for analysis.

## 5. Controlled matrix, only after first-pass health

| Phase | Evidence | Proceed when |
|---|---|---|
| A. Baseline | Authenticated model ID, one bounded completed generation, correct response envelope, usage and finish reason | No engine crash or unexplained HTTP failure |
| B. Template / reasoning | Thinking on/off, multi-turn replay, tool-schema render, reasoning/content separation | No unexpected content loss or parser mismatch |
| C. Multimodal where applicable | Synthetic image, short OCR/position/counting control, tokenizer and processor identities | Model actually supports the modality and correct assets are loaded |
| D. Cache and memory | Per-request cached tokens; KV utilization **and preemption deltas**, not occupancy alone | Metrics attributable to the lane, no live-user interference |
| E. Concurrency (separately authorised) | Matched C1/C2/C4 completed work, batch wall, tok/s, admission and worker overlap | Disposable window and explicit request/load budget |
| F. Multi-node (separately authorised) | Rank identities, collectives, actual library paths, NIC route/counters, sustained-load stacks | Single-node correctness first; no production restart |

Do not equate passing A–D with passing E–F. Likewise, a single idle Prometheus sample cannot certify absence of benchmark contention, and a two-turn cache test cannot certify a long-context retention policy.

## 6. Evidence and verdict rules

For each probe preserve: lane alias, UTC timestamp, exact `main` commit, probe ID, input **shape** (redacted), endpoint/stack/model revision, HTTP status, response field names, finish reason, token usage, rendered-marker checks, duration and the Doctor's assertion-level verdict.

Use **PROBLEM** only for the specific mechanism or contradiction actually observed; **OK/CLEAN** only for a matched control that rules out that mechanism; **INCONCLUSIVE** when several explanations remain; **UNKNOWN** when the endpoint, model family or required evidence was unavailable. Never turn a missing field or unrun test into a pass.

Retain raw internal evidence privately. Promote to the public registry only a deliberately scrubbed summary with reproducible conditions and credit; do not upload internal server logs unreviewed.

## Suggested lane order

Start with one **5090 single-GPU** text or multimodal endpoint for template/processor probes, then a **single DGX Spark** serving endpoint, then one **TP=2 Spark pair**, and only later wider TP or concurrency/soak tests. This is an order of isolation, **not** an assertion about what is currently running. Capture real endpoints and exact served model IDs at test time.

Record the pre-test and post-test `main` SHA and any unresolved issues. Do not run destructive stress, model conversion, GPU resets or distributed launch changes under the Doctor workflow.

## Completion receipt

Before expanding a lane, compare `selected_probes`, `probe_runs` and
`not_run_probes` in the returned `live_doctor` block. Sum the per-probe
`requests_made`, check `budget_exceeded`/`error`, and retain the original findings.
A completed invocation that only returns `UNKNOWN` is unavailable, not verified.
A timed-out validation request is not a clean validation result. These software
contracts are tested with synthetic local fixtures; hardware qualification is
still a separate operator-run phase.
