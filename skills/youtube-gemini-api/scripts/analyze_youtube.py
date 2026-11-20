#!/usr/bin/env python3
"""Analyze a public YouTube video with the Gemini API. Standard library only."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-flash-latest"
VIDEO_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")

DEFAULT_PROMPT = """Assista a este vídeo considerando áudio e imagem. Responda em Markdown, no
idioma predominante do vídeo, com:
1. Resumo curto.
2. Linha do tempo com timestamps (MM:SS).
3. Pontos principais, com evidências do que é dito e do que aparece na tela.
4. Incertezas: marque como aproximado o que não puder confirmar. Não invente detalhes."""


class SkillError(RuntimeError):
    pass


def canonical_url(raw: str) -> str:
    parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
                video_id = parts[1]
    if not video_id or not set(video_id) <= VIDEO_ID_CHARS:
        raise SkillError(f"Not a valid YouTube video URL: {raw}")
    return f"https://www.youtube.com/watch?v={video_id}"


def parse_time(value: str) -> int:
    """Accept seconds ("90"), MM:SS ("1:30") or HH:MM:SS ("1:02:03")."""
    try:
        parts = [int(p) for p in value.split(":")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid time: {value}") from exc
    if not 1 <= len(parts) <= 3 or any(p < 0 for p in parts):
        raise argparse.ArgumentTypeError(f"invalid time: {value}")
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def build_payload(url: str, prompt: str, start: int | None, end: int | None, low_res: bool) -> dict:
    video_part: dict = {"fileData": {"fileUri": url}}
    metadata = {}
    if start is not None:
        metadata["startOffset"] = f"{start}s"
    if end is not None:
        metadata["endOffset"] = f"{end}s"
    if metadata:
        video_part["videoMetadata"] = metadata
    payload: dict = {"contents": [{"parts": [video_part, {"text": prompt}]}]}
    if low_res:
        payload["generationConfig"] = {"mediaResolution": "MEDIA_RESOLUTION_LOW"}
    return payload


def call_gemini(model: str, payload: dict, api_key: str, timeout: int) -> dict:
    request = urllib.request.Request(
        API_URL.format(model=urllib.parse.quote(model, safe="")),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(body)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = body[:1000]
            if exc.code in {429, 500, 503} and attempt == 0:
                time.sleep(5)
                continue
            raise SkillError(f"Gemini API HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise SkillError(f"Could not reach the Gemini API: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SkillError(f"Gemini did not answer within {timeout}s; analyze a shorter window.") from exc
    raise AssertionError("unreachable")


def extract_text(response: dict) -> str:
    block = (response.get("promptFeedback") or {}).get("blockReason")
    if block:
        raise SkillError(f"Gemini blocked the request: {block}")
    candidates = response.get("candidates") or []
    if not candidates:
        raise SkillError("Gemini returned no candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "\n".join(p["text"] for p in parts if isinstance(p.get("text"), str)).strip()
    if not text:
        reason = candidates[0].get("finishReason", "unknown")
        raise SkillError(f"Gemini returned an empty answer (finishReason: {reason}).")
    return text


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description="Analyze a public YouTube video with Gemini.")
    parser.add_argument("url", help="Public YouTube URL (watch, youtu.be, shorts, live).")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="What to ask about the video.")
    prompt_group.add_argument("--prompt-file", type=Path, help="UTF-8 file with the prompt.")
    parser.add_argument("--start", type=parse_time, help="Window start: seconds, MM:SS or HH:MM:SS.")
    parser.add_argument("--end", type=parse_time, help="Window end: seconds, MM:SS or HH:MM:SS.")
    parser.add_argument("--low-res", action="store_true", help="Low media resolution (fits ~3x more video).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL}).")
    parser.add_argument("--output", type=Path, help="Save the answer to this Markdown file.")
    parser.add_argument("--timeout", type=int, default=600, help="Request timeout in seconds (default: 600).")
    parser.add_argument("--dry-run", action="store_true", help="Print the request body without calling the API.")
    args = parser.parse_args()

    if args.start is not None and args.end is not None and args.end <= args.start:
        raise SkillError("--end must be after --start.")

    url = canonical_url(args.url)
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else (args.prompt or DEFAULT_PROMPT)
    if not prompt.strip():
        raise SkillError("The prompt is empty.")
    payload = build_payload(url, prompt.strip(), args.start, args.end, args.low_res)

    if args.dry_run:
        print(json.dumps({"model": args.model, "body": payload}, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SkillError(
            "GEMINI_API_KEY is not set. Create a key at https://aistudio.google.com/apikey and set it "
            "as an environment variable. Never paste it into the chat."
        )

    text = extract_text(call_gemini(args.model, payload, api_key, args.timeout))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Saved to {args.output.resolve()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
