import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "mining"
    / "2026-07-30-inline-system-evidence"
    / "scripts"
    / "capture_pinned_evidence.py"
)
TRANSFORMERS = types.ModuleType("transformers")
TRANSFORMERS.AutoTokenizer = object
TRANSFORMERS_UTILS = types.ModuleType("transformers.utils")
CHAT_TEMPLATE_UTILS = types.ModuleType("transformers.utils.chat_template_utils")
CHAT_TEMPLATE_UTILS.render_jinja_template = object
sys.modules.setdefault("transformers", TRANSFORMERS)
sys.modules.setdefault("transformers.utils", TRANSFORMERS_UTILS)
sys.modules.setdefault(
    "transformers.utils.chat_template_utils", CHAT_TEMPLATE_UTILS
)
SPEC = importlib.util.spec_from_file_location("capture_pinned_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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

            MODULE.verify_git_checkout(root, revision)
            with self.assertRaisesRegex(ValueError, "revision mismatch"):
                MODULE.verify_git_checkout(root, "0" * 40)

            source.write_text("modified\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "local modifications"):
                MODULE.verify_git_checkout(root, revision)


if __name__ == "__main__":
    unittest.main()
