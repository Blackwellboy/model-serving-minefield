#!/usr/bin/env python3
"""Compare declared VLLM_* env names to a registered-name list (offline).

Fails when configured names are absent from the registered set (unknown/no-op).
"""
import json, sys
OK, UNREACHABLE, BLOCKING, NOTHING = 0, 1, 2, 3

def evaluate(doc):
  if not isinstance(doc, dict) or not doc:
    return NOTHING, {"status": "INCONCLUSIVE"}
  configured = [str(x) for x in (doc.get("configured_vllm_env") or [])]
  registered = set(str(x) for x in (doc.get("registered_vllm_env") or []))
  if not configured and not registered:
    return NOTHING, {"status": "INCONCLUSIVE", "detail": "empty"}
  if not registered:
    return UNREACHABLE, {"status": "UNKNOWN", "detail": "no registered table"}
  unknown = [c for c in configured if c not in registered]
  if unknown:
    return BLOCKING, {
      "status": "PROBLEM",
      "title": "configured VLLM env names not registered",
      "unknown": unknown,
      "surface": "STARTUP_CONFIGURATION_UNVALIDATED_CONTROL",
    }
  return OK, {"status": "CLEAN", "configured": configured}

def _neg():
  return evaluate({"configured_vllm_env":["VLLM_FLASHINFER_MOE_BACKEND","VLLM_USE_V1"],
                   "registered_vllm_env":["VLLM_USE_V1"]})[0]
def _empty():
  return evaluate({})[0]
NEGATIVE_CONTROLS = [("unknown env", _neg)]
EMPTY_SET_CONTROL = ("empty", _empty)
REGRESSION_ASSERTS = [("flashinfer moe unknown", lambda: _neg()==BLOCKING)]

if __name__ == "__main__":
  raw = sys.stdin.read().strip()
  doc = json.loads(raw) if raw else {}
  code, rep = evaluate(doc)
  print(json.dumps(rep, indent=2)); sys.exit(code)
