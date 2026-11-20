# Example output format (illustrative only)

This is a hand-written *format illustration*, not the result of a real API call.

A successful call using `--format md` creates a local file similar to:

```markdown
# Video transcript note

- **Source:** https://example.com/public-video
- **Transcript language:** en
- **Retrieved:** 2026-11-20 08:00 UTC

## Transcript

> Welcome to our public demo.
> Today we will explain how transcripts become searchable notes.
```

The tool does not add AI-generated summaries or fabricate a title. The transcript
text comes directly from Supadata's response; the metadata wrapper is generated
locally by the example script.
