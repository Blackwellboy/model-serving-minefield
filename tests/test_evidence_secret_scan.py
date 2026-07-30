import unittest

from integrity.check_evidence_json_secrets import findings


class EvidenceSecretScanTests(unittest.TestCase):
    def test_public_hashes_and_revisions_pass(self):
        self.assertEqual([], findings({"sha256": "a" * 64, "revision": "b" * 40}))

    def test_planted_credentials_fail(self):
        for value in (
            "github_pat_" + "A" * 30,
            "hf_" + "a" * 24,
            "sk-" + "a" * 24,
            "AKIA" + "A" * 16,
            "Authorization: Bearer secret-value",
            "api_key=secret-value",
            "-----BEGIN " + "PRIVATE KEY-----",
        ):
            with self.subTest(value=value):
                self.assertTrue(findings({"nested": [{"value": value}]}))


if __name__ == "__main__":
    unittest.main()
