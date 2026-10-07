# Library API (Phase 0)

Stable in-process surface for integrations that must not shell out to the CLI.

**Compatibility:** the supported integration contract, including `match_symptom()`,
is versioned from **model-serving-minefield 0.2.0**. Downstream plugins should
pin a compatible minor series (for example `>=0.2,<0.3`) rather than reading
compiled registry internals.

```python
from minefield.api import plan_checks, run_checks, summarize, result_to_doctor_json

plan = plan_checks(base_url="http://127.0.0.1:8000/v1", mode="lite", max_requests=5)
# plan makes zero chat completions when detect=False (default)

plan = plan_checks(
    base_url="http://127.0.0.1:8000/v1",
    mode="lite",
    max_requests=5,
    detect=True,
    preferred_trap_ids=("12", "23"),  # optional: matched traps are probed first
)
result = run_checks(plan)   # hard ceiling: requests_executed <= max_requests
summary = summarize(result) # structured counts + findings (not an intelligence score)
payload = result_to_doctor_json(result)  # classic doctor --json keys + plan metadata
```

Modes:

- `mode="lite"` — small high-value subset; default `max_requests=5`
- `mode="doctor"` — full executable catalogue (same order as historical Doctor)

Budget: when `max_requests` is set, chat completions cannot exceed it
(`RequestBudgetExceeded` if a probe would overrun).

## Symptom matching (offline)

```python
from minefield.api import match_symptom

result = match_symptom(
    "streamed reply is blank",
    stack="vllm",
    log_excerpt="answer lands in reasoning channel while content stays empty",
    limit=5,
)
result["diagnosis_level"]           # NOT_DOCUMENTED on a miss; never CONFIRMED from text alone
result["matches"]                   # ranked canonical candidates, each with trap_ids / title / confirmation_check
result["possible_unverified_leads"] # strictly weaker L-series tier
```

Ordinary textual candidates require at least two independently supplied meaningful
symptom/log concepts. Stack/model/version metadata can improve ranking and
applicability, but cannot turn a one-word resemblance into a canonical candidate.
Common phrasings such as "empty response", "garbage output" and "thinking leaked"
use bounded synonym concepts without making one word count twice.

Since 0.2.1 each match also carries `evidence_weight`: shared words weighted by
how specific they are to that entry (a word found in one entry weighs 1.0; one
found in most entries weighs little), with words that match the entry's title
counting 1.5x. Two further admission rules apply: the question must mention
something about model serving (a stack, hardware, tokens, templates, and so on,
or an identifier such as `max_tokens` or `gfx1151`), and the rarity-weighted
evidence must reach a minimum. Off-domain questions therefore return
`NOT_DOCUMENTED` with no leads. The CLI's strong / possible / weak labels are
`evidence_weight` thresholds calibrated in `benchmarks/`.

Integrations should call `match_symptom` instead of walking `load_registry()`
themselves. The compiled registry's internal layout (its entries live under
`entries`) is covered by `tests/test_integration_contract.py`, but a consumer
that guesses a key gets zero matches and no error, which is exactly how a
plugin matcher once went silently dark.

The CLI (`minefield quick` / `doctor/minefield_doctor.py`) remains the user-facing
entry and shares the same probe catalogue.


## Unified diagnosis

```python
from minefield import diagnose_environment
from minefield.registry import load_registry

report = diagnose_environment(
    load_registry(),
    "streaming replies go blank under tools",
    paths=["docker-compose.yml", "server.log"],
    base_url="http://127.0.0.1:8000/v1",
    max_requests=5,
)
```

The unified orchestrator keeps evidence classes separate while considering the
entire canonical registry for routing. Symptom similarity remains a lead,
offline file findings remain static/log leads, and live Doctor findings remain
bounded endpoint observations. When a small live request budget is used, probes
whose trap IDs already matched the symptom or supplied files are prioritised
before generic lite probes. No API key is copied into the result.
