#!/usr/bin/env python3
"""Regression for nullable llama.cpp generation params reported by /props."""
import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_doctor():
    path = REPO_ROOT / "doctor" / "minefield_doctor.py"
    spec = importlib.util.spec_from_file_location("minefield_doctor_null_params", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NullGenerationParamsTest(unittest.TestCase):
    def test_null_default_generation_params_do_not_crash(self):
        md = _load_doctor()
        doc = md.Doc()
        doc.evidence["props"] = {
            "default_generation_settings": {"params": None}
        }
        md.check_configs(doc, None)
        self.assertNotIn("server_defaults", doc.evidence)


if __name__ == "__main__":
    unittest.main()
