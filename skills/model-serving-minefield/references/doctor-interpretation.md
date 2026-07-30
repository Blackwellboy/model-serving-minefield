# Doctor interpretation

Keep all four verdicts distinct:

- `PROBLEM`: the named failure signature was observed.
- `OK`: a load-bearing assertion rules out only the named trap.
- `INCONCLUSIVE`: the probe ran but multiple states explain the result.
- `UNKNOWN`: the probe or a prerequisite was unavailable.

Report the exact implemented/executed counts from the JSON. Never call an
endpoint or stack clean based on the absence of `PROBLEM`; the doctor covers
only a subset of the registry.
