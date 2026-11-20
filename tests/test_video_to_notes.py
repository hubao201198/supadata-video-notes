"""Offline tests: no API key, network access, or paid request is needed."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_to_notes as app


class TranscriptTests(unittest.TestCase):
    def test_http_request_encodes_url_and_uses_api_key(self):
        source_url = "https://www.youtube.com/watch?v=abc&t=120"
        mock_response = io.BytesIO(b'{"content":"Hello","lang":"en"}')
        with patch.object(app, "urlopen", return_value=mock_response) as mocked:
            result = app.request_json(
                "/transcript", "test-secret", params={"url": source_url, "text": "true"}
            )
        actual_request = mocked.call_args.args[0]
        self.assertIn("url=https%3A%2F%2Fwww.youtube.com", actual_request.full_url)
        self.assertIn("%26t%3D120", actual_request.full_url)
        self.assertEqual(actual_request.get_header("X-api-key"), "test-secret")
        self.assertEqual(result["content"], "Hello")

    def test_immediate_response(self):
        with patch.object(app, "request_json", return_value={"content": "Hello!", "lang": "en"}) as mocked:
            result = app.fetch_transcript("https://youtu.be/abc123", "test-key")
        self.assertEqual(result["content"], "Hello!")
        self.assertEqual(mocked.call_args.kwargs["params"]["mode"], "native")
        self.assertEqual(mocked.call_args.kwargs["params"]["text"], "true")

    def test_async_job(self):
        responses = [
            {"jobId": "job-123"},
            {"status": "active"},
            {"status": "completed", "content": "Finished", "lang": "en"},
        ]
        with patch.object(app, "request_json", side_effect=responses) as mocked, patch.object(
            app.time, "sleep"
        ):
            result = app.fetch_transcript("https://youtu.be/abc123", "test-key")
        self.assertEqual(result["content"], "Finished")
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual(mocked.call_args.args[0], "/transcript/job-123")

    def test_async_failure(self):
        with patch.object(
            app, "request_json", side_effect=[{"jobId": "j"}, {"status": "failed", "error": "unavailable"}]
        ), patch.object(app.time, "sleep"):
            with self.assertRaisesRegex(app.SupadataAPIError, "unavailable"):
                app.fetch_transcript("https://youtu.be/abc123", "test-key")

    def test_bad_url(self):
        with self.assertRaises(ValueError):
            app.fetch_transcript("not-a-video-url", "test-key")

    def test_markdown_and_json(self):
        transcript = {"content": "Hello\nworld", "lang": "en"}
        note = app.render_note("https://youtu.be/abc", transcript, "md")
        self.assertIn("**Source:** https://youtu.be/abc", note)
        self.assertIn("> Hello\n> world", note)
        record = json.loads(app.render_note("https://youtu.be/abc", transcript, "json"))
        self.assertEqual(record["transcript"], "Hello\nworld")

    def test_name_is_safe_and_stable(self):
        a = app.output_stem("https://youtube.com/watch?v=abc123&t=1")
        b = app.output_stem("https://youtube.com/watch?v=abc123&t=2")
        self.assertNotEqual(a, b)
        self.assertNotIn("/", a)
        self.assertEqual(a, app.output_stem("https://youtube.com/watch?v=abc123&t=1"))

    def test_cli_saves_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            app.os.environ, {"SUPADATA_API_KEY": "fake-test-key"}
        ), patch.object(app, "fetch_transcript", return_value={"content": "hello", "lang": "en"}):
            status = app.main(["https://youtu.be/abc123", "--output-dir", directory])
            self.assertEqual(status, 0)
            generated = list(Path(directory).glob("*.md"))
            self.assertEqual(len(generated), 1)
            self.assertIn("hello", generated[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
