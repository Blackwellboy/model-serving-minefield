import subprocess
import tempfile
import unittest
from pathlib import Path


def verify_git_checkout(root: Path, expected_revision: str) -> None:
    """Require a supplied source tree to be the clean immutable revision."""
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            [
                "git", "-C", str(root), "status", "--porcelain",
                "--untracked-files=no",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("source root must be a readable Git checkout") from exc
    if revision != expected_revision:
        raise ValueError(
            f"revision mismatch: expected {expected_revision}, got {revision}"
        )
    if status:
        raise ValueError("Git checkout has tracked local modifications")


class CapturePinnedEvidenceTests(unittest.TestCase):
    def test_checkout_revision_and_cleanliness_are_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                [
                    "git", "-C", str(root), "config",
                    "user.email", "test@example.invalid",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            source = root / "source.py"
            source.write_text("pinned\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "source.py"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-q", "-m", "fixture"],
                check=True,
            )
            revision = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            verify_git_checkout(root, revision)
            with self.assertRaisesRegex(ValueError, "revision mismatch"):
                verify_git_checkout(root, "0" * 40)

            source.write_text("modified\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "local modifications"):
                verify_git_checkout(root, revision)


if __name__ == "__main__":
    unittest.main()
