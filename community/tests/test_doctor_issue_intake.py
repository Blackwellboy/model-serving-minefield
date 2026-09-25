import unittest

from community.doctor_issue_intake import MARKER, normalize_issue


class DoctorIssueIntakeTests(unittest.TestCase):
    def test_normalizes_environment_coverage_and_traps(self):
        body = """### What broke

Streaming answer vanished.

### Doctor JSON

```json
{
  "stack": "sglang",
  "model": "example/model",
  "server_version": "0.5.2",
  "requests_made": 9,
  "coverage": {
    "implemented": ["01", "12", "141"],
    "executed_on_stack": ["12", "141"],
    "clean": ["141"],
    "problems": ["12"],
    "inconclusive": [],
    "not_implemented": ["53"]
  },
  "coverage_line": "implemented 20/143 | executed on this stack 2",
  "findings": [
    {"level": "PROBLEM", "traps": ["12"]},
    {"level": "OK", "traps": ["141"]}
  ]
}
```
"""
        out = normalize_issue(body)
        self.assertIn(MARKER, out)
        self.assertIn("**Stack:** sglang", out)
        self.assertIn("**Version/build:** 0.5.2", out)
        self.assertIn("**Model:** example/model", out)
        self.assertIn("PROBLEM trap IDs:** 12", out)
        self.assertIn("OK/CLEAN trap IDs:** 141", out)
        self.assertIn("implemented 3; executed 2; clean 1; problems 1", out)

    def test_rejects_missing_section(self):
        with self.assertRaises(ValueError):
            normalize_issue("### Something else\n\nhello")

    def test_one_string_trap_id_is_normalized(self):
        body = '### Doctor JSON\n\n{"findings":[{"level":"PROBLEM","traps":"7"}]}'
        out = normalize_issue(body)
        self.assertIn("PROBLEM trap IDs:** 07", out)


if __name__ == "__main__":
    unittest.main()
