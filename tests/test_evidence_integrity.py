#!/usr/bin/env python3
"""Tests for Evidence Packet, blind review, promotion receipt, upstream triage."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from minefield.blind_review import assert_no_leak, derive_blind_packet, sha256_obj
from minefield.evidence_packet import preflight, load_packet
from minefield.promotion_receipt import validate_receipt
from minefield.upstream_change_triage import triage_paths


EXAMPLES = ROOT / "docs" / "evidence-packet.examples"


class EvidencePacketTests(unittest.TestCase):
    def test_pass_example(self):
        doc = load_packet(EXAMPLES / "pass.example.json")
        report = preflight(doc)
        self.assertEqual(report["status"], "PASS", report)
        self.assertGreater(report["observed_count"], 0)

    def test_bad_example_fails(self):
        doc = load_packet(EXAMPLES / "bad.example.json")
        report = preflight(doc)
        self.assertEqual(report["status"], "FAIL", report)
        codes = {f["code"] for f in report["findings"]}
        self.assertIn("MOVING_REVISION_ONLY", codes)
        self.assertIn("INFRA_AS_TARGET_NEGATIVE", codes)
        self.assertIn("SUMMARY_ONLY_PROMOTION", codes)
        self.assertIn("SANITIZATION_CONTRADICTION", codes)

    def test_unknown_example_not_pass(self):
        doc = load_packet(EXAMPLES / "unknown.example.json")
        report = preflight(doc)
        self.assertIn(report["status"], ("UNKNOWN", "HOLD"))
        self.assertNotEqual(report["status"], "PASS")
        codes = {f["code"] for f in report["findings"]}
        self.assertIn("ARTIFACT_HASH_UNVERIFIED", codes)

    def test_empty_not_pass(self):
        report = preflight({})
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["observed_count"], 0)

    def test_malformed_sha(self):
        doc = load_packet(EXAMPLES / "pass.example.json")
        doc["artifacts"][0]["sha256"] = "not-a-hash"
        report = preflight(doc)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(f["code"] == "ARTIFACT_HASH_MALFORMED" for f in report["findings"]))

    def test_missing_claim_boundary(self):
        doc = load_packet(EXAMPLES / "pass.example.json")
        doc["claim"]["claim_boundary"] = ""
        report = preflight(doc)
        self.assertEqual(report["status"], "FAIL")

    def test_zero_observation_reproduced(self):
        doc = load_packet(EXAMPLES / "pass.example.json")
        doc["execution"]["observed_count"] = 0
        doc["claim"]["evidence_status"] = "reproduced here"
        report = preflight(doc)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(f["code"] == "ZERO_OBSERVATION_PASS" for f in report["findings"]))


class BlindReviewTests(unittest.TestCase):
    def test_strips_and_keeps(self):
        full = load_packet(EXAMPLES / "bad.example.json")
        full["recommended_trap_number"] = 99
        full["review"]["proposer_confidence"] = "high"
        full["review"]["proposer_verdict"] = "ship it"
        wrapper = derive_blind_packet(full)
        leaks = assert_no_leak(wrapper)
        self.assertEqual(leaks, [], leaks)
        packet = wrapper["packet"]
        self.assertIn("hypothesis", packet)
        self.assertIn("artifacts", packet)
        self.assertIn("execution", packet)
        self.assertIn("controls", packet)
        self.assertNotIn("disposition", packet.get("claim", {}))
        self.assertNotIn("proposer_confidence", packet.get("review", {}))
        self.assertNotIn("proposer_verdict", packet.get("review", {}))
        self.assertEqual(len(wrapper["full_packet_sha256"]), 64)
        self.assertEqual(len(wrapper["blind_packet_sha256"]), 64)

    def test_blind_hash_deterministic(self):
        full = load_packet(EXAMPLES / "pass.example.json")
        w1 = derive_blind_packet(full)
        w2 = derive_blind_packet(full)
        self.assertEqual(w1["blind_packet_sha256"], w2["blind_packet_sha256"])
        self.assertEqual(w1["full_packet_sha256"], sha256_obj(full))


class PromotionReceiptTests(unittest.TestCase):
    def test_example_pass(self):
        doc = json.loads(
            (ROOT / "docs/promotion-receipt.example.json").read_text(encoding="utf-8")
        )
        report = validate_receipt(doc)
        self.assertEqual(report["status"], "PASS", report)

    def test_malformed_hash(self):
        doc = json.loads(
            (ROOT / "docs/promotion-receipt.example.json").read_text(encoding="utf-8")
        )
        doc["evidence_packet_sha256"] = "abc"
        report = validate_receipt(doc)
        self.assertEqual(report["status"], "FAIL")

    def test_missing_adjudicator(self):
        doc = json.loads(
            (ROOT / "docs/promotion-receipt.example.json").read_text(encoding="utf-8")
        )
        doc["adjudicator"] = ""
        # empty string still "present" - validate treats missing; force delete
        del doc["adjudicator"]
        report = validate_receipt(doc)
        self.assertEqual(report["status"], "FAIL")


class UpstreamTriageTests(unittest.TestCase):
    def test_template_maps(self):
        r = triage_paths(["src/chat_template.jinja"])
        self.assertEqual(r["high_risk_surfaces"][0]["surface"], "CHAT_TEMPLATE_RENDERING")
        self.assertFalse(r["new_trap_found"])
        self.assertGreater(r["observed_count"], 0)

    def test_quant_maps(self):
        r = triage_paths(["vllm/model_executor/layers/quantization/fp8.py"])
        self.assertEqual(r["high_risk_surfaces"][0]["surface"], "QUANTIZATION")

    def test_unknown_not_fabricated(self):
        r = triage_paths(["zzz/nope.xyz"])
        self.assertEqual(r["path_results"][0]["surface"], "UNKNOWN")
        self.assertEqual(r["path_results"][0]["related_traps"], [])
        self.assertFalse(r["new_trap_found"])

    def test_empty_not_substantive_pass(self):
        r = triage_paths([])
        self.assertEqual(r["observed_count"], 0)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertFalse(r["new_trap_found"])


class AgentBundleReviewedKnowledgeTests(unittest.TestCase):
    """Unreviewed material must not silently become canonical agent knowledge."""

    def test_bundle_lists_only_numbered_trap_paths(self):
        reg = json.loads(
            (ROOT / "dist/MINEFIELD_REGISTRY.json").read_text(encoding="utf-8")
        )
        traps = reg.get("entries") or []
        self.assertEqual(reg.get("canonical_trap_count"), len(traps))
        self.assertTrue(traps, "registry should contain traps")
        for t in traps:
            tid = t.get("id") or t.get("trap_id") or t.get("number")
            self.assertIsNotNone(tid)
            sid = str(tid)
            self.assertFalse(sid.lower().startswith("draft"))
            self.assertNotIn("mining/", sid)
            # Numbered traps only in canonical registry
            self.assertTrue(
                str(tid).isdigit() or str(tid).lstrip("0").isdigit() or str(tid).isdigit(),
                f"non-numeric trap id in registry: {tid!r}",
            )

    def test_agent_bundle_mentions_evidence_status(self):
        text = (ROOT / "dist/MINEFIELD_AGENT_BUNDLE.md").read_text(encoding="utf-8")
        self.assertIn("evidence", text.lower())


if __name__ == "__main__":
    unittest.main()
