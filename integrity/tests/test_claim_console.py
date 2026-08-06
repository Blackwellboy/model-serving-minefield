import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claim_propagation import console_safe


class ClaimConsoleEncoding(unittest.TestCase):
    def test_unencodable_evidence_is_escaped_on_legacy_windows_console(self):
        rendered = console_safe("745 \u2192 282", encoding="cp1252")
        self.assertEqual(r"745 \u2192 282", rendered)

    def test_encodable_evidence_is_unchanged(self):
        self.assertEqual("plain evidence", console_safe("plain evidence", "cp1252"))


if __name__ == "__main__":
    unittest.main()
