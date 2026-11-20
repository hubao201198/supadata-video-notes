# Turn YouTube and Social Videos into a Markdown Knowledge Base with Python + Supadata

**A practical, working tutorial for building a local library of video transcripts — without browser automation, fragile subtitle scraping, or third-party Python dependencies.**

Imagine following five technical talks, three product demos, and a couple of short social videos every week. Some of them contain useful explanations, but the information is difficult to search after the video disappears into your watch history. Copying subtitles manually does not scale. Screenshots are even harder to index. What if every public video URL could become a readable Markdown note that you can search with your favorite editor or feed into a retrieval-augmented generation (RAG) pipeline?

This project demonstrates one way to build exactly that workflow. We will call the **Supadata Transcript API**, handle both immediate results and asynchronous processing, and save the result as Markdown, plain text, or JSON. The example is a real Python command-line tool, not pseudocode. Its standard-library-only implementation makes it straightforward to inspect, test, and adapt.

**Get started with Supadata:** [Supadata — video and web data API](https://supadata.ai/r/9YW9BZ05)

> **Disclosure:** The link above is my personal promotional/referral link. I may receive Supadata credits if this tutorial meets the company's promotional requirements. This does not affect the technical examples or limitations described below.

## 1. What we are building

Our workflow has four simple stages:

```text
Public video URL(s)
        |
        v
Supadata GET /v1/transcript
        |
        +-- HTTP 200: transcript ready -----------------+
        |                                               |
        +-- HTTP 202: jobId --> poll /transcript/{id} --+
                                                        |
                                                        v
                                        Plain text + source metadata
                                                        |
                                         +--------------+-------------+
                                         |              |             |
                                         v              v             v
                                      Markdown        .txt          .json
```

The script accepts more than one URL at a time, which is useful for a research reading list. It keeps a source link and the returned transcript language, so each note has basic provenance. It also generates a deterministic filename from the video's URL and a short hash. Two links that happen to have the same last path component will not overwrite each other accidentally.

The example uses one API endpoint across supported public YouTube, TikTok, Instagram, X/Twitter, Facebook, and direct media URLs. Different services have different accessibility rules; the script does not bypass login walls, geographical restrictions, or platform permissions. Always obtain the appropriate permissions before collecting or redistributing media content.

## 2. Prerequisites: Python and an API key

You need **Python 3.10 or newer**, a terminal, and a Supadata API key. You can create an account and obtain a key via [Supadata](https://supadata.ai/r/9YW9BZ05). You do not need to install `requests`, `yt-dlp`, a browser driver, or a video downloader for this example. Python's `urllib`, `json`, and `pathlib` modules are sufficient.

Clone this repository (or download the source files), open a terminal inside its root directory, and verify your Python version:

```bash
python3 --version
```

Set your API key as an environment variable. On macOS or Linux:

```bash
export SUPADATA_API_KEY="YOUR_OWN_API_KEY"
```

On Windows PowerShell:

```powershell
$env:SUPADATA_API_KEY = "YOUR_OWN_API_KEY"
```

Do not paste a real API key into a public GitHub repository, example command, screenshot, or issue. The script reads it from your environment and sends it only in the API's `x-api-key` request header. The `.gitignore` also excludes local `.env` files, although this tutorial does not require one.

## Repository contents — every linked file is committed

This is not a README-only demo. You can inspect and execute all the referenced files in this public repository:

~~~text
supadata-video-notes/
├── README.md
├── video_to_notes.py
├── tests/
│   ├── test_video_to_notes.py
│   └── test_repo_docs.py
├── examples/
│   ├── quickstart_async.py
│   └── EXAMPLE.md
├── .github/workflows/tests.yml
├── .gitignore
└── LICENSE
~~~

The **batch CLI** is [video_to_notes.py](video_to_notes.py). The [async quickstart](examples/quickstart_async.py) is a smaller script that you can read in one sitting. [Offline tests](tests/test_video_to_notes.py) verify the request encoding, immediate results, queued jobs, failed jobs, filenames, and actual local file creation, without an API key or credit consumption.

## 3. Make your first transcript note

Run the following example from the repository directory:

```bash
python3 video_to_notes.py \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  --mode native \
  --format md
```

The command asks Supadata for **existing captions only**, then creates a Markdown file under `notes/` if a transcript is available. You will see a message with the generated output path. A note contains a source URL, the language returned by the API, the retrieval time, and a quoted transcript. We intentionally do **not** invent summaries, timestamps, or speaker labels that the plain-text response has not provided.

Why start with `--mode native` rather than jumping directly to AI transcription? It makes the first experiment predictable. If existing subtitles are missing, you can decide explicitly whether the video is important enough to generate a transcript. This is especially useful when processing long research lists, where generation costs may otherwise be surprising.

If you want Supadata to try existing captions first and generate them when necessary, switch to auto mode:

```bash
python3 video_to_notes.py \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  --mode auto \
  --format md
```

You can force generated transcription using `--mode generate`, but it may consume more credits. According to the [official transcript documentation](https://docs.supadata.ai/get-transcript), `native` retrieves existing captions, `auto` attempts captions before generation, and `generate` always uses AI. The official documentation currently describes native and generated transcription using different credit rates; check the latest pricing before scaling the workflow.

## 4. Process a small research playlist

The program accepts multiple positional URLs and continues to the next URL even when one fails. For example:

```bash
python3 video_to_notes.py \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  "https://youtu.be/dQw4w9WgXcQ" \
  --mode native \
  --format json \
  --output-dir research-notes
```

These two addresses point to the same example video, but they demonstrate that each URL is treated as an independent input. In your own project, use genuinely different public videos. Repeated requests can consume credits, even if the videos overlap. The JSON export is useful for later indexing because it contains `source_url`, `language`, `fetched_at`, and `transcript` fields.

To export plain text instead of Markdown, replace `--format json` with `--format txt`. To request a preferred transcript language, pass `--lang en` or another supported language code. Treat `--lang` as a **preference**, not a guarantee of translation: Supadata can return another available transcript language. In generated mode, the API documentation says the transcription language follows the video and the requested language is ignored.

## 5. Working code: synchronous results, 202 jobs, polling, and exporting

A useful technical subtlety is that the same Supadata endpoint can return two different outcomes. An HTTP 200 response with `text=true` contains a string `content` and `lang`. An HTTP 202 response instead supplies a `jobId`. Calling the transcript endpoint only once and assuming that the reply always has a `content` field will break when processing long videos.

For the asynchronous branch, make authenticated calls to **GET /v1/transcript/{jobId}** every second. Keep polling while `status` is `queued` or `active`; extract the content after `completed`; surface the error after `failed`. Always bound your waiting time. The official [transcript specification](https://docs.supadata.ai/get-transcript) documents these statuses, the REST response shape and the job expiration window.

The complete standalone program below is exactly the source of [examples/quickstart_async.py](examples/quickstart_async.py). It makes the initial request, polls when necessary, and writes a local Markdown file. It uses only the Python standard library:

~~~python
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
~~~

Run it from the repository root after setting your API key:

~~~bash
python3 examples/quickstart_async.py
~~~

It writes `quickstart-note.md`. This small script intentionally keeps error handling brief, so the control flow is obvious. For practical usage, [video_to_notes.py](video_to_notes.py) additionally supports **multiple URLs**, safe URL-derived filenames, JSON/TXT/Markdown formats, request retries for 429/selected 5xx responses, a timeout, and per-URL failure reporting. It is not merely pseudocode: you can execute the batch commands above against publicly accessible videos with your own API key.

### Example Markdown output (illustrative fixture)

To show what a generated note looks like *before* spending credits, here is a short example from the expected formatter. **The transcript sentences are synthetic demonstration text, not a claimed live Supadata response**, and the example does not redistribute a third-party video's spoken content. The [example file](examples/EXAMPLE.md) explains the same distinction.

~~~markdown
# Video transcript note

- **Source:** https://example.com/public-video
- **Transcript language:** en
- **Retrieved:** 2026-11-20 08:00 UTC

## Transcript

> Welcome to our public demo.
> Today we will explain how transcripts become searchable notes.
~~~

In a live run the source, retrieved time and language are set by the exporter, and the quoted body is the returned API text. The tool does not invent a title, summary, speaker identity or timestamps.

### Official Python SDK: a shorter alternative

If you prefer the [Supadata Python SDK](https://github.com/supadata-ai/py), install a release that supports `transcript.get_job_status` (the [official docs](https://docs.supadata.ai/get-transcript) specify version 1.7.0 or newer):

~~~bash
python3 -m pip install "supadata>=1.7.0"
~~~

Here is a comparable one-video flow with an explicit polling loop:

~~~python
import os
import time
from supadata import Supadata

client = Supadata(api_key=os.environ["SUPADATA_API_KEY"])
transcript = client.transcript(
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    text=True,
    mode="native",
)
if hasattr(transcript, "content"):
    print(transcript.content)
else:
    for attempt in range(300):
        job = client.transcript.get_job_status(transcript.job_id)
        if job.status == "completed":
            print(job.result.content)
            break
        if job.status == "failed":
            raise RuntimeError(str(job.error))
        time.sleep(1)
    else:
        raise TimeoutError("The job exceeded the polling window")
~~~

The SDK can make integration into an existing Python project more ergonomic. The standard-library CLI in this repository avoids installing dependencies, and already includes batching, retries, export choices, and tests. Both methods call Supadata's service and can consume credits.

### Cost, language and provenance are engineering concerns

As documented in Supadata's [pricing section](https://docs.supadata.ai/get-transcript#pricing) at the time of writing, **one native transcript costs 1 credit**, while **generated transcription costs 2 credits per minute**. A 206 "Transcript Unavailable" response may cost a credit as well. **Polling the asynchronous job-status endpoint does not incur additional credits.** For async generation, a charge estimate may be returned initially and the final amount reconciled on completion. Check current pricing before bulk ingestion.

Choose `mode=native` to request only existing captions and avoid accidentally switching to generation. Choose `mode=auto` to try native captions first and generate if missing. `mode=generate` always uses AI for transcription. For example, 20 successful native transcript requests would nominally consume 20 credits, but 10 generated videos lasting 15 minutes each would consume 300 credits at the documented generation rate.

The `lang` argument is a **language preference, not translation**. An available different-language track may be returned, so retain `lang` from the response; when generating, the API docs say the input `lang` preference is ignored and speech is transcribed in the video's language.

This tutorial requests `text=true`, which is plain text **without timestamps**. To retain timings, use `text=false` and process segment `offset` and `duration` values in milliseconds. Avoid implying temporal precision the response does not provide. If no speech is detected, a successful empty result can still be billable.

## 6. Test without consuming credits

The repository includes tests built with Python's standard `unittest` library. They mock the API request function and exercise immediate completion, asynchronous completion, a failed asynchronous job, invalid inputs, output rendering, safe filenames, and file creation.

```bash
python3 -m unittest discover -s tests -v
```

The tests do not send requests to Supadata and do not require an API key. They are also configured to run in GitHub Actions when you push the repository. This is useful when you modify the exporter for your own workflow: you can check the control flow without burning credits during development.

**Important distinction:** passing offline tests proves that the local code paths behave as expected against simulated API responses. It does not prove that a particular external video is accessible or that your personal API key is authorized. A live end-to-end smoke test still requires a valid key, an accessible video, and available credits.

## 7. Common errors and realistic limitations

**The API key is missing.** Confirm that `SUPADATA_API_KEY` is set in the same terminal where you run Python. Environment variables set in one terminal session are not automatically exported to another one.

**A transcript is unavailable.** Try another public video with captions. If you explicitly want generation, use `--mode auto` or `--mode generate`, keeping the credit impact in mind. Generation cannot guarantee success for every video.

**The video is private or restricted.** A publicly pasted URL does not imply public access. Login-only, private, paywalled, age-restricted, or geographically blocked media may fail. This script does not attempt to circumvent those restrictions.

**The API is temporarily busy.** HTTP 429 and selected 5xx errors are retried a limited number of times. If those attempts fail, the script reports the error and continues with other URLs. For a large production pipeline, add persistent job tracking, scheduling, usage monitoring, and a rate-limit-aware queue.

**The transcript has no speaker labels or timestamps.** That is expected in this example. We intentionally request plain text, not the timestamped segment representation. It is better to be explicit about missing detail than to present fabricated precision.

**A single URL fails during a batch.** Successful notes are still saved. The process exits with a nonzero status when at least one URL fails, which is convenient for automation and CI pipelines.

## 8. Next step: from notes to a searchable knowledge base

Markdown and JSON files are useful intermediate artifacts. You can import Markdown notes into Obsidian, open them in VS Code, or index JSON records using your preferred database and search engine. A minimal RAG application might split each transcript into chunks, store the chunk text alongside its source URL, create embeddings, and retrieve relevant chunks when answering a question.

The source URL is important: without provenance, an answer from a retrieval system can be difficult to audit. In more advanced pipelines, you should also preserve channel/title metadata, language information, timestamps where available, and a content hash for deduplication. This tutorial deliberately stops before embedding and summarization so that the core extraction path remains easy to understand and cheap to test.

There is also a privacy and copyright consideration. A transcript can contain personal or copyrighted speech. Collect only material you are allowed to process, avoid publishing full transcripts without the necessary rights, and handle downstream storage appropriately. Notes built for personal study are not automatically suitable for public redistribution or commercial datasets.

## 9. Conclusion

With a small amount of Python, you now have a practical pipeline from public video URLs to local searchable text. The key engineering choices are simple but consequential: authenticate using an environment variable, encode the source URL safely, distinguish immediate responses from background jobs, make transcription mode an explicit cost decision, keep source provenance, and test error handling without live API calls.

You can extend the project with a user interface, scheduled ingestion, timestamped subtitles, semantic search, and AI-assisted summaries. But even in its current form, it solves a useful problem: turning spoken explanations from a collection of videos into organized files you can actually find later.

**Try the API:** [Supadata via my personal link](https://supadata.ai/r/9YW9BZ05). *Disclosure: this is a promotional/referral link, and qualifying tutorials may earn me Supadata credits.*

### References

- [Official Supadata Transcript API documentation](https://docs.supadata.ai/get-transcript)
- [Supadata Python SDK (alternative to the standard-library approach)](https://github.com/supadata-ai/py)
- [Supadata API overview and examples](https://github.com/supadata-ai/skills)

### License

The example source code in this repository is released under the [MIT License](LICENSE).
