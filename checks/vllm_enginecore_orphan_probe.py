#!/usr/bin/env python3
"""Offline adjudicator for trap 123 (no live process/GPU access).

Input is an observation object describing process/memory state around a
vllm serve API-server kill; classifies whether the EngineCore worker
survived the kill and is still holding GPU memory.
"""
import json, sys

OK, PROBLEM, NOTHING = 0, 1, 2


def classify(obs):
    if not isinstance(obs, dict) or not obs:
        return "INCONCLUSIVE", NOTHING
    if not obs.get("api_server_killed"):
        return "NOT_APPLICABLE", NOTHING
    engine_core_alive = obs.get("engine_core_pid_alive")
    gpu_mem_held_mb = obs.get("gpu_mem_held_mb")
    if engine_core_alive is None or gpu_mem_held_mb is None:
        return "INCONCLUSIVE", NOTHING
    if engine_core_alive or (isinstance(gpu_mem_held_mb, (int, float)) and gpu_mem_held_mb > 0):
        return "ENGINE_CORE_ORPHANED", PROBLEM
    return "CLEAN_TEARDOWN", OK


def evaluate(doc):
    state, code = classify(doc if isinstance(doc, dict) else {})
    if code == NOTHING:
        return NOTHING, {"status": "INCONCLUSIVE", "readiness_state": state}
    if code == PROBLEM:
        return PROBLEM, {
            "status": "PROBLEM",
            "readiness_state": state,
            "title": "EngineCore worker survived the API-server kill and still holds GPU memory",
        }
    return OK, {"status": "CLEAN", "readiness_state": state}


def _neg_orphan_alive():
    # engine_core_pid_alive True after a reported kill: must report PROBLEM
    return evaluate(
        {"api_server_killed": True, "engine_core_pid_alive": True, "gpu_mem_held_mb": 104277}
    )[0]


def _neg_orphan_memory_only():
    # process listing missed it, but memory is still held: must still report PROBLEM
    return evaluate(
        {"api_server_killed": True, "engine_core_pid_alive": False, "gpu_mem_held_mb": 512}
    )[0]


def _empty():
    return evaluate({})[0]


NEGATIVE_CONTROLS = [
    ("engine core still listed after kill", _neg_orphan_alive),
    ("engine core memory still held after kill", _neg_orphan_memory_only),
]
EMPTY_SET_CONTROL = ("empty", _empty)
REGRESSION_ASSERTS = [
    (
        "clean teardown (both zero/false) reports OK, not PROBLEM",
        lambda: evaluate(
            {"api_server_killed": True, "engine_core_pid_alive": False, "gpu_mem_held_mb": 0}
        )[0]
        == OK,
    ),
]

if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    doc = json.loads(raw) if raw else {}
    code, rep = evaluate(doc)
    print(json.dumps(rep, indent=2))
    sys.exit(code)
