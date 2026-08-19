import unittest

from integrity.open_issue_queue import open_trap_issues, validate_queue


REPO = "Blackwellboy/model-serving-minefield"


def issue(number, title="[trap] candidate", state="open", pull_request=False):
    item = {"number": number, "title": title, "state": state}
    if pull_request:
        item["pull_request"] = {"url": "https://api.github.com/example"}
    return item


def q(number, issue_number, confirm=True, refute=True):
    lines = [
        f"### Q{number}. Candidate issue",
        "",
        f"- **Source.** [issue #{issue_number}](https://github.com/{REPO}/issues/{issue_number}).",
    ]
    if confirm:
        lines.append("- **CONFIRM.** Positive discriminator.")
    if refute:
        lines.append("- **REFUTE.** Negative discriminator.")
    return "\n".join(lines) + "\n"


class OpenIssueQueueTests(unittest.TestCase):
    def test_open_trap_issue_must_be_queued(self):
        payload = [issue(36), issue(38)]
        queue = q(16, 36) + "\n" + q(17, 38) + "\n---\n\n## CLOSED"
        self.assertEqual([], validate_queue(payload, queue, REPO))

    def test_missing_open_trap_issue_fails(self):
        findings = validate_queue([issue(36)], "## OPEN\n", REPO)
        self.assertEqual(1, len(findings))
        self.assertIn("#36", findings[0])

    def test_closed_and_non_trap_issues_are_not_candidates(self):
        payload = [
            issue(36, state="closed"),
            issue(42, title="[research-integrity] corroboration"),
        ]
        self.assertEqual([], open_trap_issues(payload))
        self.assertEqual([], validate_queue(payload, "## OPEN\n", REPO))

    def test_pull_requests_from_issues_endpoint_are_ignored(self):
        self.assertEqual([], open_trap_issues([issue(50, pull_request=True)]))

    def test_confirm_and_refute_are_load_bearing(self):
        payload = [issue(36)]
        findings = validate_queue(payload, q(16, 36, confirm=False), REPO)
        self.assertTrue(any("CONFIRM" in finding for finding in findings))
        findings = validate_queue(payload, q(16, 36, refute=False), REPO)
        self.assertTrue(any("REFUTE" in finding for finding in findings))

    def test_duplicate_queue_ownership_fails(self):
        payload = [issue(36)]
        queue = q(16, 36) + "\n" + q(17, 36)
        findings = validate_queue(payload, queue, REPO)
        self.assertTrue(any("multiple OPEN sections" in finding for finding in findings))


if __name__ == "__main__":
    unittest.main()
