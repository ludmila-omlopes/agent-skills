# Long-video multimodal workflow

Read this reference when a YouTube video is longer than 1 hour, exceeds 3 hours, or when several
long videos would make one OpenRouter request unreliable.

## Why segment

Gemini's current video documentation says that models with a 1M-token context can process roughly
1 hour of video at default media resolution or up to 3 hours at low media resolution. Limits vary
by model and can change. OpenRouter also recommends trimming or splitting long videos.

Do not assume that a Google-specific clipping field will survive OpenRouter's normalized
`video_url` request. For timestamp offsets, use the native Gemini API or create smaller authorized
video files. Keep the analysis multimodal.

Official references:

- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/generate-content/video-understanding
- https://openrouter.ai/docs/guides/overview/multimodal/videos

## Segmentation plan

1. Inspect the exact duration without downloading media.
2. Divide the timeline into segments no longer than 90 minutes (5,400 seconds).
3. Add 30–60 seconds of overlap between neighboring segments when continuity matters.
4. Analyze every segment for speech, visible scenes, on-screen text, reactions, and timestamps.
5. Save one Markdown report per segment.
6. Run a text-only synthesis over the segment reports.
7. Preserve global timestamps by adding each segment's start offset to local timestamps.
8. Note gaps, overlaps, and approximate timestamps.

For multiple long videos, finish all segments of one video before starting the next. Synthesize
each video's reports first, then compare the per-video syntheses.

## Native Gemini clipping example

Install the current Google Gen AI SDK and set `GEMINI_API_KEY` in the environment. Use a current
video-capable model; the model below is an example and should be checked against the live model
list.

```python
from google import genai
from google.genai import types

client = genai.Client()

start_seconds = 0
end_seconds = 5400
youtube_url = "https://www.youtube.com/watch?v=VIDEO_ID"

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=types.Content(
        parts=[
            types.Part(
                file_data=types.FileData(file_uri=youtube_url),
                video_metadata=types.VideoMetadata(
                    start_offset=f"{start_seconds}s",
                    end_offset=f"{end_seconds}s",
                ),
            ),
            types.Part(
                text=(
                    "Analise este segmento multimodalmente. Inclua fala, cenas, texto na tela, "
                    "reações e timestamps. Não invente detalhes."
                )
            ),
        ]
    ),
)

print(response.text)
```

Google currently documents `videoMetadata` clipping in the Generate Content API. Check the
official reference before use because the recommended API surface and model IDs can change.

## Final synthesis checklist

- Every segment has spoken-content coverage.
- Every segment has concrete visual evidence.
- Local timestamps were converted to the full-video timeline.
- Overlap did not create duplicate events.
- Contradictions were marked and, where possible, rechecked.
- Transcript-only fallback was not used without the user's explicit approval.
