"""Read-only diagnostic tools for the Model Serving Minefield registry."""

__version__ = "0.1.0"

# Phase-0 reusable Doctor API (optional import; keeps lightweight CLI imports fast)
def __getattr__(name: str):
    if name in {
        "detect_target",
        "plan_checks",
        "run_checks",
        "summarize",
        "ProbePlan",
        "RunResult",
        "Summary",
        "TargetInfo",
        "result_to_doctor_json",
    }:
        from . import api as _api

        return getattr(_api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
