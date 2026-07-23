---
name: youtube-gemini-openrouter
description: Analyze up to 10 public YouTube videos multimodally with a video-capable Gemini model through the OpenRouter API. Use for timestamped summaries, chapters, visual evidence, spoken-content analysis, comparisons, hooks, highlights, or editing notes when the user provides youtube.com or youtu.be URLs and wants an API-based workflow instead of the Gemini app.
---

# YouTube Gemini via OpenRouter

Analyze public YouTube videos through OpenRouter's normalized Chat Completions API. Send each
YouTube URL as a `video_url` content part and require evidence from both the audio and visible
content. Never describe a transcript-only result as multimodal.

## Priorities

1. Prefer genuine video-and-audio analysis.
2. Inspect metadata and duration before sending any video.
3. Require timestamps and concrete visual observations.
4. Label uncertainty instead of inventing details.
5. Treat transcript-only analysis as a last resort that requires the user's approval.

## Requirements

- Require `OPENROUTER_API_KEY` in the environment without printing its value.
- Accept 1–10 canonical, public YouTube URLs.
- Use a model whose OpenRouter metadata lists `video` as an input modality.
- Default to `google/gemini-3.6-flash`, but verify availability at runtime because model IDs change.
- Use `https://openrouter.ai/api/v1/chat/completions`.
- Use `yt-dlp` only for metadata inspection; do not download video media.

OpenRouter video URL support is provider-specific. Google AI Studio accepts public YouTube URLs;
Google Vertex AI does not. Report provider-routing errors instead of hiding them.

## Workflow

### 1. Validate URLs, model, key, and duration

Resolve bundled paths relative to this `SKILL.md`. From the skill directory, prefer the helper:

```bash
python scripts/analyze_youtube.py "https://www.youtube.com/watch?v=VIDEO_ID" --output analysis.md
```

The helper:

- canonicalizes supported YouTube URL forms;
- checks metadata with `yt-dlp --skip-download`;
- rejects private or known unlisted videos;
- refuses whole-video OpenRouter requests longer than 3 hours;
- warns when a video is longer than 1 hour;
- verifies the selected model currently accepts video input;
- sends the request and saves non-empty Markdown output.

For a dry validation that does not call the completions endpoint:

```bash
python scripts/analyze_youtube.py URL --dry-run
```

Dry-run verifies the URL, metadata, duration, live model listing, and payload shape. It deliberately
does not require the API key or test provider routing; those are confirmed only by a real request.

If a video exceeds 3 hours, or several long videos would make one request fragile, read
[references/long-videos.md](references/long-videos.md) and keep the workflow multimodal by
segmenting it.

### 2. Build an evidence-oriented prompt

Unless the user requests another format, ask for Brazilian Portuguese Markdown containing:

- a concise overview;
- a timestamped chapter outline;
- main arguments or events with supporting evidence;
- visual observations that cannot be inferred from speech alone;
- on-screen text, cuts, demonstrations, reactions, and scene changes;
- the opening hook, retention moments, and clip candidates;
- the final spoken hook and final visual hook separately;
- explicit uncertainties and approximate timestamps marked as such.

For editing or next-live planning, also ask for reusable clips and title or description ideas
grounded in what actually appears.

### 3. Send normalized multimodal content

Use this shape, repeating the `video_url` part for each URL:

```json
{
  "model": "google/gemini-3.6-flash",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Analise multimodalmente e inclua evidências visuais com timestamps."
        },
        {
          "type": "video_url",
          "video_url": {
            "url": "https://www.youtube.com/watch?v=VIDEO_ID"
          }
        }
      ]
    }
  ]
}
```

Do not substitute Gemini-native `file_data.file_uri` inside the OpenRouter request. For local or
private files, use a supported base64 video workflow rather than this public-URL path.

### 4. Verify the result

Accept the response only when:

- the HTTP request succeeded;
- assistant content is non-empty;
- timestamps are present;
- spoken content and visible content are both addressed;
- at least two concrete visual observations are tied to scenes or timestamps.

If visual evidence is missing, make one focused follow-up request for visible content only and
merge it with the first answer. Treat model-generated timestamps as approximate unless checked
against the source timeline.

### 5. Save and report

Save assistant content as UTF-8 Markdown when an output path is requested. Never save credentials
or authorization headers. Report:

- model used;
- source URLs;
- output path;
- whether timestamps and visual evidence were present;
- provider, duration, or context limitations.

## Error handling

- `401`: ask the user to configure `OPENROUTER_API_KEY`; never ask them to paste it into chat.
- `402`: report insufficient credits. Do not claim a fixed minimum balance unless the current
  OpenRouter response or documentation states one.
- `408`, `429`, or `5xx`: retry once, respecting `Retry-After` when present.
- Model rejects `video_url`: re-check model input modalities and provider compatibility.
- Vertex routing error: retry without forcing Vertex; AI Studio is the YouTube URL path.
- Private or unlisted video: stop and request a public upload or an authorized local-file workflow.
- Request too large: segment multimodally; do not silently fall back to a transcript.
- Empty response: preserve the safe status and error message, retry once if transient, then report
  the blocker.

## Batch strategy

For short videos, include up to 10 URLs in one request. For long videos, analyze them individually
and then synthesize the resulting Markdown reports with a text-only comparison request. This
MapReduce-style flow avoids long-running batch timeouts while preserving multimodal analysis of
each source.

## Official references

- OpenRouter video inputs: https://openrouter.ai/docs/guides/overview/multimodal/videos
- OpenRouter models API: https://openrouter.ai/docs/api/api-reference/models/get-models
- OpenRouter errors: https://openrouter.ai/docs/api/reference/errors-and-debugging
- Gemini video understanding: https://ai.google.dev/gemini-api/docs/video-understanding

## Provenance

Adapted from skill material attributed to Hermes Agent and marked MIT in the supplied metadata.
