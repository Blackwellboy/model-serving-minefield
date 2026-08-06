#!/usr/bin/env python3
import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"endpoint_readiness_hierarchy_probe.py"
spec=importlib.util.spec_from_file_location("er",P); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_controls():
  for _,fn in m.NEGATIVE_CONTROLS: assert fn()==m.BLOCKING
  assert m.EMPTY_SET_CONTROL[1]()!=m.OK
  for _,fn in m.REGRESSION_ASSERTS: assert fn() is True
if __name__=="__main__":
  test_controls(); print("ALL PASS")
