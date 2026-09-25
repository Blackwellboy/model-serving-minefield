import unittest

from community.github_issue_comment import find_comment_id
from community.doctor_issue_intake import MARKER


class GithubIssueCommentTests(unittest.TestCase):
    def test_finds_existing_normalized_comment(self):
        comments = [
            {"id": 11, "body": "other comment"},
            {"id": 22, "body": f"{MARKER}\nnormalized"},
        ]
        self.assertEqual(find_comment_id(comments), 22)

    def test_missing_marker_returns_none(self):
        self.assertIsNone(find_comment_id([{"id": 11, "body": "other"}]))

    def test_malformed_comment_is_ignored(self):
        comments = [
            {"body": f"{MARKER}\nmissing id"},
            None,
            {"id": "33", "body": f"{MARKER}\nvalid"},
        ]
        self.assertEqual(find_comment_id(comments), 33)


if __name__ == "__main__":
    unittest.main()
