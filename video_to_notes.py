#!/usr/bin/env python3
"""Turn public video URLs into local text, JSON, or Markdown notes with Supadata.

Only Python's standard library is required. Requires SUPADATA_API_KEY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

API_BASE = "https://api.supadata.ai/v1"
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


class SupadataAPIError(RuntimeError):
    """A request failed or the API returned an unexpected response."""


def request_json(
    path: str,
    api_key: str,
    *,
    params: dict[str, str] | None = None,
    timeout: float = 120.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Make an authenticated GET request with bounded retries."""
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urlencode(params)

    request = Request(
        url,
        headers={"x-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )

    for attempt in range(max_attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
                if not isinstance(payload, dict):
                    raise SupadataAPIError("Unexpected response: expected a JSON object")
                # Some API errors can arrive with a 2xx status (such as HTTP 206).
                if payload.get("error") and "content" not in payload and "jobId" not in payload:
                    raise SupadataAPIError(f"API returned an error: {payload}")
                return payload
        except HTTPError as exc:
            message = exc.read(2048).decode("utf-8", errors="replace")
            if exc.code in RETRYABLE_HTTP and attempt + 1 < max_attempts:
                time.sleep(min(2**attempt, 8))
                continue
            raise SupadataAPIError(f"HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            if attempt + 1 < max_attempts:
                time.sleep(min(2**attempt, 8))
                continue
            raise SupadataAPIError(f"Network error: {exc.reason}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SupadataAPIError("The API did not return valid JSON") from exc

    raise SupadataAPIError("Request failed after retry attempts")


def fetch_transcript(
    url: str,
    api_key: str,
    *,
    mode: str = "native",
    lang: str | None = None,
    poll_interval: float = 1.0,
    max_wait: float = 300.0,
    request_timeout: float = 120.0,
) -> dict[str, Any]:
    """Fetch the transcript, waiting for an async job when necessary."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("A public http(s) video URL is required")

    params = {"url": url, "text": "true", "mode": mode}
    if lang:
        params["lang"] = lang

    payload = request_json("/transcript", api_key, params=params, timeout=request_timeout)
    job_id = payload.get("jobId")
    if job_id:
        deadline = time.monotonic() + max_wait
        print(f"  Processing asynchronously (job {job_id})...", file=sys.stderr)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SupadataAPIError(f"Timed out waiting for job {job_id}")
            time.sleep(min(poll_interval, remaining))
            payload = request_json(
                f"/transcript/{job_id}", api_key, timeout=request_timeout
            )
            status = payload.get("status")
            if status == "failed":
                raise SupadataAPIError(f"Job {job_id} failed: {payload.get('error')}")
            if status == "completed":
                if isinstance(payload.get("result"), dict):
                    payload = payload["result"]
                break
            if status not in ("queued", "active"):
                raise SupadataAPIError(f"Unexpected job status: {status!r}")

    if not isinstance(payload.get("content"), str):
        raise SupadataAPIError("Expected a plain-text transcript; content is missing")
    return payload


def output_stem(url: str) -> str:
    """Derive a stable, filesystem-safe name; hash prevents URL collisions."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    video_id = parse_qs(parsed.query).get("v", [None])[0]
    identity = video_id or parsed.path.rstrip("/").split("/")[-1] or "video"
    candidate = f"{host}-{identity}"
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate).strip(".-_")[:72]
    suffix = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    return f"{safe or 'video'}-{suffix}"


def render_note(url: str, transcript: dict[str, Any], fmt: str) -> str:
    text = transcript["content"]
    lang = transcript.get("lang") or "unknown"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if fmt == "txt":
        return text + ("\n" if text and not text.endswith("\n") else "")
    if fmt == "json":
        return json.dumps(
            {"source_url": url, "language": lang, "fetched_at": timestamp, "transcript": text},
            indent=2,
            ensure_ascii=False,
        ) + "\n"
    display_text = text.strip() if text.strip() else "[No speech detected]"
    quoted = "\n".join("> " + line for line in display_text.splitlines())
    return (
        "# Video transcript note\n\n"
        f"- **Source:** {url}\n"
        f"- **Transcript language:** {lang}\n"
        f"- **Retrieved:** {timestamp}\n\n"
        "## Transcript\n\n"
        f"{quoted}\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Save Supadata transcripts as local Markdown, text, or JSON notes."
    )
    parser.add_argument("urls", nargs="+", help="One or more public video URLs")
    parser.add_argument("--mode", choices=("native", "auto", "generate"), default="native")
    parser.add_argument("--lang", help="Preferred transcript language, for example en or zh")
    parser.add_argument("--format", choices=("md", "txt", "json"), default="md")
    parser.add_argument("--output-dir", type=Path, default=Path("notes"))
    parser.add_argument("--max-wait", type=float, default=300.0, help="Maximum seconds to poll an async job")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Seconds between job checks")
    parser.add_argument("--request-timeout", type=float, default=120.0, help="HTTP timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api_key = os.environ.get("SUPADATA_API_KEY", "").strip()
    if not api_key:
        parser.error("SUPADATA_API_KEY is missing. Export your key in the shell first.")
    if args.max_wait <= 0 or args.poll_interval <= 0 or args.request_timeout <= 0:
        parser.error("Timeouts and polling interval must be positive numbers")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for video_url in args.urls:
        print(f"Fetching: {video_url}")
        try:
            transcript = fetch_transcript(
                video_url,
                api_key,
                mode=args.mode,
                lang=args.lang,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                request_timeout=args.request_timeout,
            )
            destination = args.output_dir / f"{output_stem(video_url)}.{args.format}"
            destination.write_text(render_note(video_url, transcript, args.format), encoding="utf-8")
            print(f"  Saved: {destination}")
        except (SupadataAPIError, ValueError, OSError) as exc:
            failures += 1
            print(f"  Error: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
