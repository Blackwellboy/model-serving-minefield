import unittest

from minefield.leads import search_leads


class Qwen38LeadRoutingTests(unittest.TestCase):
    def _ids(self, query, **kwargs):
        return [item["lead_id"] for item in search_leads(query, limit=20, **kwargs)]

    def test_mtp_runtime_support_routes_to_qwen38_lead(self):
        self.assertIn(
            "L043",
            self._ids("Qwen3.8 NVFP4 MTP unsupported on one runtime but works on another"),
        )

    def test_arm64_exec_format_routes_to_architecture_lead(self):
        self.assertIn(
            "L044",
            self._ids("DGX Spark aarch64 benchmark image exec format error amd64"),
        )

    def test_container_model_subcommand_routes_to_entrypoint_lead(self):
        self.assertIn(
            "L046",
            self._ids("Usage serve No such command /model container"),
        )

    def test_thread_join_crash_routes_to_harness_lead(self):
        self.assertIn(
            "L047",
            self._ids("soak telemetry Thread _stop join crash"),
        )

    def test_single_decimal_failure_routes_to_repeat_before_corruption_lead(self):
        self.assertIn(
            "L048",
            self._ids("Qwen3.8 Q4 decimal canary 9.11 9.9 correctness corruption"),
        )


if __name__ == "__main__":
    unittest.main()
