#!/usr/bin/env python3
"""Offline readiness hierarchy adjudicator (no live network).

Input is an observation object of surface results; classifies readiness state.
"""
import json, sys
OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3

def classify(obs):
  if not isinstance(obs, dict) or not obs:
    return "INCONCLUSIVE", NOTHING
  if obs.get("no_response"):
    return "NO_RESPONSE", BLOCKING
  # 401 is not down
  if obs.get("http_status") == 401 and obs.get("path") in ("/v1/models", "models"):
    if obs.get("treated_as_down"):
      return "AUTH_REQUIRED", BLOCKING  # PROBLEM: misclassified as down
    return "AUTH_REQUIRED", OK
  if obs.get("container_up") and obs.get("engine_dead"):
    return "WRAPPER_HEALTH_ONLY", BLOCKING
  if obs.get("health_200") and obs.get("generation_failed"):
    return "GENERATION_FAILED", BLOCKING
  if obs.get("generation_ok"):
    return "GENERATION_OK", OK
  if obs.get("health_200"):
    return "WRAPPER_HEALTH_ONLY", NOTHING
  return "INCONCLUSIVE", NOTHING

def evaluate(doc):
  state, code = classify(doc if isinstance(doc, dict) else {})
  if code == NOTHING and state == "INCONCLUSIVE":
    return NOTHING, {"status": "INCONCLUSIVE", "readiness_state": state}
  if code == BLOCKING:
    return BLOCKING, {"status": "PROBLEM", "readiness_state": state,
                      "title": "readiness surface misclassification or incomplete readiness"}
  return OK, {"status": "CLEAN", "readiness_state": state}

def _neg_fp():
  return evaluate({"container_up": True, "engine_dead": True, "health_200": True})[0]
def _neg_fn():
  return evaluate({"http_status": 401, "path": "/v1/models", "treated_as_down": True})[0]
def _empty():
  return evaluate({})[0]
NEGATIVE_CONTROLS = [("false positive wrapper", _neg_fp), ("false negative 401", _neg_fn)]
EMPTY_SET_CONTROL = ("empty", _empty)
REGRESSION_ASSERTS = [("401 not down when not treated_as_down",
  lambda: evaluate({"http_status":401,"path":"/v1/models","treated_as_down":False})[0]==OK)]

if __name__ == "__main__":
  raw = sys.stdin.read().strip()
  doc = json.loads(raw) if raw else {}
  code, rep = evaluate(doc)
  print(json.dumps(rep, indent=2)); sys.exit(code)
