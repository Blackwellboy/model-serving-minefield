# Library API (Phase 0)

Stable in-process surface for integrations that must not shell out to the CLI.

```python
from minefield.api import plan_checks, run_checks, summarize, result_to_doctor_json

plan = plan_checks(base_url="http://127.0.0.1:8000/v1", mode="lite", max_requests=5)
# plan makes zero chat completions when detect=False (default)

plan = plan_checks(base_url="http://127.0.0.1:8000/v1", mode="lite", max_requests=5, detect=True)
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

result = match_symptom("answer lands in reasoning_content when streaming", stack="vllm", limit=5)
result["diagnosis_level"]           # NOT_DOCUMENTED on a miss; never CONFIRMED from text alone
result["matches"]                   # ranked canonical candidates, each with trap_ids / title / confirmation_check
result["possible_unverified_leads"] # strictly weaker L-series tier
```

Integrations should call `match_symptom` instead of walking `load_registry()`
themselves. The compiled registry's internal layout (its entries live under
`entries`) is covered by `tests/test_integration_contract.py`, but a consumer
that guesses a key gets zero matches and no error, which is exactly how a
plugin matcher once went silently dark.

The CLI (`minefield quick` / `doctor/minefield_doctor.py`) remains the user-facing
entry and shares the same probe catalogue.
