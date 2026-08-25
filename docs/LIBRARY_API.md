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

The CLI (`minefield quick` / `doctor/minefield_doctor.py`) remains the user-facing
entry and shares the same probe catalogue.
