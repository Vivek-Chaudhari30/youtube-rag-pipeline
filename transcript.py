"""
transcript.py
-------------
Downloads transcripts (captions) for YouTube videos and splits them into
overlapping chunks that are ready for embedding.

Fetches captions via youtube-transcript-api first, then yt-dlp as fallback.
Requests are throttled to reduce YouTube 429 rate-limit errors.
"""

from __future__ import annotations

import os
import re
import tempfile
import time

import yt_dlp
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

_ytt_api = YouTubeTranscriptApi()
_REQUEST_DELAY_SEC = 1.0
_last_request_at = 0.0
_captions_blocked = False

_YDL_SUB_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitleslangs": ["en", "en-US", "en-GB"],
    "subtitlesformat": "vtt/best",
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    "retries": 2,
}


def _rate_limit() -> None:
    global _last_request_at
    wait = _REQUEST_DELAY_SEC - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.time()


def _parse_vtt(vtt_text: str) -> str:
    lines: list[str] = []
    for raw in vtt_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)
    return " ".join(lines)


def _get_transcript_ytt_api(video_id: str) -> str | None:
    transcript_list = _ytt_api.list(video_id)
    try:
        transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"]).fetch()
    except Exception:
        transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"]).fetch()

    full_text = " ".join(
        snippet.text.replace("\n", " ").strip()
        for snippet in transcript
    )
    return full_text or None


def _get_transcript_ytdlp(video_id: str) -> str | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            **_YDL_SUB_OPTS,
            "outtmpl": os.path.join(tmpdir, "%(id)s"),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for name in os.listdir(tmpdir):
            if not name.endswith(".vtt"):
                continue
            path = os.path.join(tmpdir, name)
            text = _parse_vtt(open(path, encoding="utf-8", errors="ignore").read())
            if text.strip():
                return text
    return None


def _is_rate_limit_error(err: str) -> bool:
    lowered = err.lower()
    return any(token in lowered for token in ("429", "block", "too many requests", "ipblocked"))


def get_transcript(video_id: str) -> str | None:
    """
    Download transcript text for a video, trying multiple methods with retries.
    """
    global _captions_blocked
    if _captions_blocked:
        return None

    for attempt in range(2):
        _rate_limit()

        try:
            text = _get_transcript_ytt_api(video_id)
            if text:
                return text
        except (NoTranscriptFound, TranscriptsDisabled):
            break
        except Exception as e:
            err = str(e)
            if _is_rate_limit_error(err):
                _captions_blocked = True
                print("  [transcript] Caption downloads rate-limited — using metadata fallback")
                return None
            print(f"  [transcript] ytt-api {video_id}: {err[:120]}")

        if _captions_blocked:
            return None

        _rate_limit()
        try:
            text = _get_transcript_ytdlp(video_id)
            if text:
                return text
        except Exception as e:
            err = str(e)
            if _is_rate_limit_error(err):
                _captions_blocked = True
                print("  [transcript] Caption downloads rate-limited — using metadata fallback")
                return None
            print(f"  [transcript] yt-dlp {video_id}: {err[:120]}")

    return None


def chunk_text(text: str, chunk_size: int = 200, stride: int = 150) -> list[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += stride
        if start >= len(words):
            break
    return chunks


def metadata_chunks_for_video(video: dict) -> list[dict]:
    """Fallback when captions are unavailable: rank using title + description."""
    title = (video.get("title") or "").strip()
    description = (video.get("description") or "").strip()
    channel = (video.get("channel") or "").strip()
    text = ". ".join(part for part in (title, description, channel) if part)
    if not text:
        return []

    return [
        {
            "video_id": video["video_id"],
            "title": title,
            "url": video["url"],
            "channel": channel,
            "chunk_idx": 0,
            "text": text,
            "source": "metadata",
        }
    ]


def get_chunks_for_video(video: dict, allow_metadata_fallback: bool = True) -> list[dict] | None:
    video_id = video["video_id"]
    transcript = get_transcript(video_id)

    if transcript:
        result = []
        for idx, chunk_text_content in enumerate(chunk_text(transcript)):
            result.append(
                {
                    "video_id": video_id,
                    "title": video["title"],
                    "url": video["url"],
                    "channel": video["channel"],
                    "chunk_idx": idx,
                    "text": chunk_text_content,
                    "source": "transcript",
                }
            )
        print(f"  [transcript] {video['title'][:50]} → {len(result)} chunks")
        return result

    if allow_metadata_fallback:
        meta = metadata_chunks_for_video(video)
        if meta:
            print(f"  [transcript] {video['title'][:50]} → metadata fallback")
            return meta

    print(f"  [transcript] No transcript for: {video['title'][:60]}")
    return None


def process_all_videos(
    videos: list[dict],
    min_chunks: int = 1,
    allow_metadata_fallback: bool = True,
) -> tuple[list[dict], bool]:
    """
    Collect chunks from candidate videos.

    Returns (chunks, used_metadata_fallback).
    """
    global _captions_blocked
    _captions_blocked = False

    all_chunks: list[dict] = []
    used_metadata = False
    print(f"[transcript] Processing {len(videos)} videos...\n")

    for video in videos:
        chunks = get_chunks_for_video(video, allow_metadata_fallback=allow_metadata_fallback)
        if not chunks:
            continue

        if chunks[0].get("source") == "metadata":
            used_metadata = True

        all_chunks.extend(chunks)

        transcript_chunks = sum(1 for c in all_chunks if c.get("source") == "transcript")
        if transcript_chunks >= min_chunks and not used_metadata:
            break

    print(f"\n[transcript] Total chunks collected: {len(all_chunks)}")
    return all_chunks, used_metadata
