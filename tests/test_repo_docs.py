"""Offline documentation consistency: all linked local files actually exist."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_readme_targets_exist(self):
        for relative in [
            "video_to_notes.py",
            "tests/test_video_to_notes.py",
            "tests/test_repo_docs.py",
            "examples/quickstart_async.py",
            "examples/EXAMPLE.md",
            ".github/workflows/tests.yml",
            ".gitignore",
            "LICENSE",
        ]:
            with self.subTest(file=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_readme_contains_copyable_async_loop(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('get_json("/transcript/" + quote(job_id, safe=""))', text)
        self.assertIn('Path("quickstart-note.md").write_text', text)
        self.assertIn('https://supadata.ai/r/9YW9BZ05', text)


if __name__ == "__main__":
    unittest.main()
