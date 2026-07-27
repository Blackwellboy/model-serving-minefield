# Trap 15: a server without echo plus logprobs silently breaks lm-eval multiple choice

**Found by @mrpmorris.**

**Status: reported by others** (@mrpmorris, handled explicitly in his public harness); not reproduced here.

**Symptom.** Multiple-choice benchmark tasks (MMLU-style) wedge forever or
read as a model scoring near zero, while generative tasks on the same
server work fine. The model gets the blame; the server's API surface is the
cause.

**Mechanism.** lm-eval scores multiple choice by loglikelihood: it sends
`echo=true` plus `logprobs` to `/v1/completions` and reads per-token
logprobs of each answer option. Some runtimes reject that combination
(sglang, per the harness comments); every request then times out and
retries forever, wedging the whole run. Worse, a server can return
**HTTP 200 with empty logprobs**, which wedges lm-eval exactly like a
rejection while looking healthy to any status-code check.

**Stacks and builds bitten.** Documented and worked around in
[mrpmorris/sparkrun-recipes](https://github.com/mrpmorris/sparkrun-recipes)'
`benchllm.py`, which (a) maintains an explicit list of loglikelihood-scored
tasks, (b) probes the server before running them, and (c) requires the
probe response to contain actual `token_logprobs`, not just a 200. His
comparison grid marks such servers UNSUPPORTED rather than letting them
score zero, alongside OOM, CRASH, HANG, and STARTUP as distinct
death-classes; the discipline of classifying **why** a number is missing is
itself the lesson.

**The check.** One cheap request before any multiple-choice eval:

```python
r = requests.post(f"{base}/completions", json={"model": m, "prompt": "hi",
    "max_tokens": 1, "echo": True, "logprobs": 1})
ok = r.status_code == 200 and bool(
    (r.json()["choices"][0].get("logprobs") or {}).get("token_logprobs"))
```

If `ok` is false, do not run loglikelihood tasks on this server, and do not
report their absence as a model score.

**The fix.** Probe first; mark unsupported combinations UNSUPPORTED in your
results rather than zero; keep generative and loglikelihood task lists
separate.

**Found.** Public in sparkrun-recipes as of 2026-07 (see the file history
there for exact dates).

**Attribution.** @mrpmorris (Peter Morris),
[sparkrun-recipes](https://github.com/mrpmorris/sparkrun-recipes).
