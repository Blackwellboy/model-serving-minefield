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

    def test_sensitive_key_context_fails(self):
        for key in ("password", "client_secret", "api_key", "access_token"):
            with self.subTest(key=key):
                self.assertTrue(findings({key: "actual-secret"}))

    def test_unlisted_high_entropy_token_fails(self):
        self.assertTrue(
            findings({"opaque": "Z9qX7vN3mK8pR2tY" + "6wL4cB1hF5sJ0dG"})
        )

    def test_token_evidence_and_public_digests_pass(self):
        self.assertEqual(
            [],
            findings({
                "token_strings": ["▁hello", "Ġworld"],
                "token_ids": [1, 2],
                "sha256": "a" * 64,
                "revision": "b" * 40,
            }),
        )


if __name__ == "__main__":
    unittest.main()
