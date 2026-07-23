#!/usr/bin/env python3
"""Analyze public YouTube videos through OpenRouter without downloading media."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3.6-flash"
MAX_URLS = 10
WARN_DURATION_SECONDS = 60 * 60
MAX_WHOLE_VIDEO_SECONDS = 3 * 60 * 60

DEFAULT_PROMPT = """Analise os vídeos do YouTube de forma genuinamente multimodal, considerando
tanto o áudio e a fala quanto as imagens. Responda em português do Brasil e use Markdown.

Inclua:
1. Resumo executivo conciso.
2. Linha do tempo com capítulos e timestamps.
3. Principais argumentos, acontecimentos ou ensinamentos, com evidências.
4. Observações visuais que não poderiam ser deduzidas apenas da transcrição, incluindo cenas,
   gestos, objetos, interfaces, texto na tela, cortes e mudanças de contexto.
5. Gancho inicial, momentos de retenção e possíveis trechos de destaque, com timestamps.
6. Gancho final falado e gancho final visual, separadamente.
7. Incertezas ou limitações claramente marcadas.

Não invente detalhes. Trate timestamps como aproximados quando não puder confirmá-los.
"""


class SkillError(RuntimeError):
    """Expected, user-actionable failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze 1–10 public YouTube videos with Gemini through OpenRouter."
    )
    parser.add_argument("urls", nargs="+", help="Public YouTube URL(s), up to 10.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model ID.")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Custom analysis prompt.")
    prompt_group.add_argument("--prompt-file", type=Path, help="UTF-8 prompt file.")
    parser.add_argument("--output", type=Path, help="Write assistant Markdown to this path.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Completions request timeout in seconds (default: 900).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate metadata and model, then print a safe request preview.",
    )
    return parser.parse_args()


def canonicalize_youtube_url(raw_url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(raw_url)
    except ValueError as exc:
        raise SkillError(f"Invalid URL: {raw_url}") from exc

    host = (parsed.hostname or "").lower()
    video_id = ""

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"embed", "live", "shorts"}:
                video_id = parts[1]
    else:
        raise SkillError(f"Unsupported YouTube host: {host or '(missing)'}")

    if not video_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in video_id):
        raise SkillError(f"Could not find a valid YouTube video ID in: {raw_url}")

    return f"https://www.youtube.com/watch?v={video_id}"


def yt_dlp_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]

    probe = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "yt_dlp"]

    raise SkillError(
        "yt-dlp is required for metadata inspection. Install it with "
        "`python -m pip install yt-dlp`; the script uses --skip-download and does not download video media."
    )


def fetch_metadata(url: str) -> dict[str, Any]:
    command = yt_dlp_command() + [
        "--dump-single-json",
        "--no-playlist",
        "--skip-download",
        "--no-warnings",
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip().splitlines()
        safe_message = message[-1] if message else "unknown yt-dlp error"
        raise SkillError(f"Could not inspect YouTube metadata for {url}: {safe_message}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SkillError(f"yt-dlp returned malformed metadata for {url}") from exc


def validate_metadata(url: str, metadata: dict[str, Any]) -> None:
    availability = metadata.get("availability")
    if availability in {"private", "premium_only", "subscriber_only", "needs_auth", "unlisted"}:
        raise SkillError(f"Video is not a normal public upload ({availability}): {url}")

    duration = metadata.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise SkillError(f"Could not confirm a positive video duration for {url}")
    if duration > MAX_WHOLE_VIDEO_SECONDS:
        raise SkillError(
            f"Video is {format_duration(duration)}, longer than the 3-hour whole-video threshold. "
            "Use the multimodal segmentation workflow in references/long-videos.md."
        )
    if duration > WARN_DURATION_SECONDS:
        print(
            f"Warning: {url} is {format_duration(duration)}. "
            "A segmented request may be more reliable.",
            file=sys.stderr,
        )


def format_duration(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
    retry_transient: bool = False,
) -> dict[str, Any]:
    encoded = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "youtube-gemini-openrouter-skill/1.0",
        **(headers or {}),
    }
    if encoded is not None:
        request_headers["Content-Type"] = "application/json"

    attempts = 2 if retry_transient else 1
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            data=encoded,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            safe_body = exc.read().decode("utf-8", errors="replace")[:2000]
            transient = exc.code in {408, 429, 500, 502, 503, 504}
            if transient and attempt + 1 < attempts:
                retry_after = exc.headers.get("Retry-After")
                delay = min(int(retry_after), 30) if retry_after and retry_after.isdigit() else 2
                time.sleep(delay)
                continue
            raise SkillError(f"HTTP {exc.code} from OpenRouter: {safe_body}") from exc
        except urllib.error.URLError as exc:
            if attempt + 1 < attempts:
                time.sleep(2)
                continue
            raise SkillError(f"Could not reach OpenRouter: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SkillError("OpenRouter returned malformed JSON") from exc
    raise AssertionError("unreachable")


def verify_model(model_id: str) -> None:
    response = request_json(OPENROUTER_MODELS_URL)
    models = response.get("data")
    if not isinstance(models, list):
        raise SkillError("OpenRouter models response did not contain a data list")

    model = next((item for item in models if item.get("id") == model_id), None)
    if model is None:
        raise SkillError(f"Model is not currently listed by OpenRouter: {model_id}")

    architecture = model.get("architecture") or {}
    modalities = architecture.get("input_modalities") or []
    if "video" not in modalities:
        raise SkillError(f"Model does not currently advertise video input: {model_id}")


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillError(f"Could not read prompt file: {exc}") from exc
    else:
        prompt = args.prompt or DEFAULT_PROMPT
    if not prompt.strip():
        raise SkillError("Prompt must not be empty")
    return prompt.strip()


def build_payload(model: str, urls: list[str], prompt: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(
        {"type": "video_url", "video_url": {"url": url}}
        for url in urls
    )
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
    }


def extract_assistant_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SkillError("OpenRouter response did not contain choices[0].message.content") from exc

    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    else:
        text = ""

    if not text.strip():
        raise SkillError("OpenRouter returned empty assistant content")
    return text.strip()


def main() -> int:
    args = parse_args()
    if not 1 <= len(args.urls) <= MAX_URLS:
        raise SkillError(f"Supply between 1 and {MAX_URLS} YouTube URLs")
    if args.timeout <= 0:
        raise SkillError("--timeout must be positive")

    urls = [canonicalize_youtube_url(url) for url in args.urls]
    if len(set(urls)) != len(urls):
        raise SkillError("Duplicate YouTube URLs are not allowed")

    for url in urls:
        metadata = fetch_metadata(url)
        validate_metadata(url, metadata)
        title = metadata.get("title") or "(untitled)"
        print(f"Metadata: {format_duration(float(metadata['duration']))} — {title}")

    verify_model(args.model)
    print(f"Model verified for video input: {args.model}")
    prompt = load_prompt(args)
    payload = build_payload(args.model, urls, prompt)

    if args.dry_run:
        print(
            "Dry run only: API credentials and provider routing were not tested.",
            file=sys.stderr,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SkillError(
            "OPENROUTER_API_KEY is not set. Configure it in the environment; do not paste it into chat."
        )

    response = request_json(
        OPENROUTER_CHAT_URL,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
        timeout=args.timeout,
        retry_transient=True,
    )
    assistant_content = extract_assistant_content(response)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(assistant_content + "\n", encoding="utf-8")
        print(f"Saved analysis to {args.output.resolve()}")
    else:
        print(assistant_content)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
