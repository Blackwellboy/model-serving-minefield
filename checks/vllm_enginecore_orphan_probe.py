#!/usr/bin/env python3
"""Offline adjudicator for trap 123 (no live process/GPU access).

Input is an observation object describing process/memory state around an
API-server-only kill. The check deliberately binds residual GPU memory to the
EngineCore process; generic GPU memory held by some other process is not enough
to diagnose trap 123.
"""
import json
import sys

OK, PROBLEM, NOTHING = 0, 1, 2


def classify(obs):
    if not isinstance(obs, dict) or not obs:
        return "INCONCLUSIVE", NOTHING
    if not obs.get("api_server_killed"):
        return "NOT_APPLICABLE", NOTHING

    engine_core_alive = obs.get("engine_core_pid_alive")
    engine_core_gpu_mem_mb = obs.get("engine_core_gpu_mem_held_mb")
    if engine_core_alive is None or engine_core_gpu_mem_mb is None:
        return "INCONCLUSIVE", NOTHING
    if not isinstance(engine_core_alive, bool):
        return "INCONCLUSIVE", NOTHING
    if not isinstance(engine_core_gpu_mem_mb, (int, float)):
        return "INCONCLUSIVE", NOTHING
    if engine_core_gpu_mem_mb < 0:
        return "INCONCLUSIVE", NOTHING

    if engine_core_alive and engine_core_gpu_mem_mb > 0:
        return "ENGINE_CORE_ORPHANED_WITH_GPU_MEMORY", PROBLEM
    if not engine_core_alive and engine_core_gpu_mem_mb == 0:
        return "CLEAN_TEARDOWN", OK

    # Contradictory or partial observations do not prove this trap. For example,
    # a PID lookup can miss a renamed/reaped process while generic GPU memory is
    # still present, or EngineCore can survive briefly without owning GPU memory.
    return "INCONCLUSIVE_OWNERSHIP", NOTHING


def evaluate(doc):
    state, code = classify(doc if isinstance(doc, dict) else {})
    if code == NOTHING:
        return NOTHING, {"status": "INCONCLUSIVE", "readiness_state": state}
    if code == PROBLEM:
        return PROBLEM, {
            "status": "PROBLEM",
            "readiness_state": state,
            "title": "EngineCore survived the API-server kill and still owns GPU memory",
        }
    return OK, {"status": "CLEAN", "readiness_state": state}


def _neg_orphan_owned_memory():
    return evaluate(
        {
            "api_server_killed": True,
            "engine_core_pid_alive": True,
            "engine_core_gpu_mem_held_mb": 104277,
        }
    )[0]


def _empty():
    return evaluate({})[0]


NEGATIVE_CONTROLS = [
    ("engine core survives and owns contributor-measured memory", _neg_orphan_owned_memory),
]
EMPTY_SET_CONTROL = ("empty", _empty)
REGRESSION_ASSERTS = [
    (
        "clean teardown reports OK",
        lambda: evaluate(
            {
                "api_server_killed": True,
                "engine_core_pid_alive": False,
                "engine_core_gpu_mem_held_mb": 0,
            }
        )[0]
        == OK,
    ),
    (
        "memory without a live EngineCore ownership proof is inconclusive",
        lambda: evaluate(
            {
                "api_server_killed": True,
                "engine_core_pid_alive": False,
                "engine_core_gpu_mem_held_mb": 512,
            }
        )[0]
        == NOTHING,
    ),
    (
        "surviving EngineCore without GPU allocation is not this trap",
        lambda: evaluate(
            {
                "api_server_killed": True,
                "engine_core_pid_alive": True,
                "engine_core_gpu_mem_held_mb": 0,
            }
        )[0]
        == NOTHING,
    ),
]

if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    doc = json.loads(raw) if raw else {}
    code, rep = evaluate(doc)
    print(json.dumps(rep, indent=2))
    sys.exit(code)
