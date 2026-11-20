#!/usr/bin/env python3
"""Complete standalone Supadata REST transcript -> Markdown demonstration.

Requires a real SUPADATA_API_KEY; may use Supadata credits. Python 3.10+.
"""
import json
import os
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://api.supadata.ai/v1"
VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
KEY = os.environ["SUPADATA_API_KEY"]


def get_json(path, params=None):
    url = API + path
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"x-api-key": KEY})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


result = get_json("/transcript", {
    "url": VIDEO_URL,
    "text": "true",  # Plain text rather than timestamped chunks
    "mode": "native",  # Avoid accidental AI-generation charges
})

if "jobId" in result:
    job_id = result["jobId"]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        time.sleep(1)
        job = get_json("/transcript/" + quote(job_id, safe=""))
        if job["status"] == "completed":
            result = job.get("result", job)  # REST: top-level; SDK: result object
            break
        if job["status"] == "failed":
            raise RuntimeError(f"Transcription failed: {job.get('error')}")
        if job["status"] not in ("queued", "active"):
            raise RuntimeError(f"Unexpected status: {job['status']}")
    else:
        raise TimeoutError("Transcript job did not finish in 5 minutes")

transcript = result["content"]
assert isinstance(transcript, str), "Expected text=true string content"
quoted_text = "\n".join("> " + line for line in transcript.splitlines())
note = ("# Video transcript note\n\n"
        + f"- **Source:** {VIDEO_URL}\n"
        + f"- **Language:** {result.get('lang', 'unknown')}\n\n"
        + "## Transcript\n\n" + quoted_text + "\n")
Path("quickstart-note.md").write_text(note, encoding="utf-8")
print("Saved: quickstart-note.md")
