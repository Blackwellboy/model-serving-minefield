import unittest

from minefield.diagnosis_contract import compare_conditions
from minefield.registry import ROOT, _clean, compile_registry


class RegistryGenerationRegressionTests(unittest.TestCase):
    def test_inline_code_identifiers_preserve_underscores(self):
        cleaned = _clean("Use `NCCL_IB_GID_INDEX=3` with **verified** ports.")
        self.assertIn("NCCL_IB_GID_INDEX=3", cleaned)
        self.assertNotIn("NCCLIBGIDINDEX", cleaned)


    def test_related_trap_parser_ignores_array_index_notation(self):
        registry = compile_registry(ROOT)
        bad = [
            entry["id"]
            for entry in registry["entries"]
            if "00" in entry["related_traps"]
        ]
        self.assertEqual([], bad)

        trap33 = next(entry for entry in registry["entries"] if entry["id"] == "33")
        self.assertIn("35", trap33["related_traps"])

    def test_trap139_encodes_switchless_topology(self):
        registry = compile_registry(ROOT)
        trap = next(entry for entry in registry["entries"] if entry["id"] == "139")
        topology = trap["applicability"]["topology"]
        self.assertIn("switchless-direct-cable", topology)
        self.assertIn("multi-nic", topology)

        _, mismatched, _ = compare_conditions(
            trap["applicability"], {"topology": "switched-fabric"}
        )
        self.assertTrue(any(item.startswith("topology:") for item in mismatched))


if __name__ == "__main__":
    unittest.main()
