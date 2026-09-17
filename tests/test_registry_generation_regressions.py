import unittest

from minefield.diagnosis_contract import compare_conditions
from minefield.registry import ROOT, _clean, _related_trap_ids, compile_registry


class RegistryGenerationRegressionTests(unittest.TestCase):
    def test_inline_code_identifiers_preserve_underscores(self):
        cleaned = _clean("Use `NCCL_IB_GID_INDEX=3` with **verified** ports.")
        self.assertIn("NCCL_IB_GID_INDEX=3", cleaned)
        self.assertNotIn("NCCLIBGIDINDEX", cleaned)

    def test_related_traps_ignore_inline_array_indices(self):
        related = _related_trap_ids(
            "Trap 12 and [34] are related; `shape[0]` and `req[1]` are array indices.",
            {"01", "12", "34"},
            "99",
        )
        self.assertEqual(["12", "34"], related)

    def test_related_traps_ignore_fenced_code_and_noncanonical_ids(self):
        related = _related_trap_ids(
            "Trap 34 is prose.\n```python\nrow = shape[1]\nprint('Trap 12')\n```\n[999] is not canonical.",
            {"01", "12", "34"},
            "99",
        )
        self.assertEqual(["34"], related)

    def test_trap140_does_not_publish_bogus_trap00_relation(self):
        registry = compile_registry(ROOT)
        trap = next(entry for entry in registry["entries"] if entry["id"] == "140")
        self.assertNotIn("00", trap["related_traps"])

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
