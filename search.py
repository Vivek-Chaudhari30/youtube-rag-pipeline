"""
search.py
---------
Handles two things:
  1. Query expansion  - turns your one query into 3 related search phrases
                        so we fish a wider net on YouTube before semantic ranking.
  2. YouTube search   - calls YouTube Data API v3 and returns a list of
                        candidate videos (id, title, description, channelTitle).

Why expand queries?
  YouTube's search is keyword-based. If you type "sentiment analysis NLP",
  you might miss a great video titled "build a text classifier with Flask".
  By generating a few related phrases, we collect more candidates for the
  semantic stage to rank properly.
"""

import os
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def expand_query(user_query: str) -> list[str]:
    """
    Turn one user query into 3 related YouTube search phrases.

    This is a simple rule-based expander for the MVP.
    In Phase 2 you can replace this with an LLM call for smarter expansion.

    Example:
        Input : "NLP sentiment analysis project"
        Output: [
            "NLP sentiment analysis project tutorial",
            "sentiment analysis python deployment tutorial",
            "end to end NLP project flask"
        ]
    """
    base = user_query.strip()
    expansions = [
        f"{base} tutorial",
        f"{base} python step by step",
        f"end to end {base} project",
    ]
    return expansions


def search_youtube(query: str, max_results: int = 10) -> list[dict]:
    """
    Search YouTube for a single query string.
    Returns a list of video dicts: {video_id, title, description, channel}.

    max_results: how many videos per query phrase. With 3 expanded queries,
                 you get up to 3 × max_results candidates before dedup.
    """
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    request = youtube.search().list(
        part="snippet",
        q=query,
        type="video",               # only actual videos, not playlists/channels
        maxResults=max_results,
        relevanceLanguage="en",     # prefer English results
        videoDuration="medium",     # medium = 4–20 min, skips super short clips
    )
    response = request.execute()

    videos = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "channel": snippet.get("channelTitle", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return videos


def fetch_candidates(user_query: str, results_per_phrase: int = 10) -> list[dict]:
    """
    Full candidate-fetch pipeline:
      1. Expand the user query into multiple phrases.
      2. Search YouTube for each phrase.
      3. Deduplicate by video_id (same video might show up in multiple searches).

    Returns a deduplicated list of candidate video dicts.
    """
    phrases = expand_query(user_query)
    print(f"\n[search] Expanded to {len(phrases)} phrases:")
    for p in phrases:
        print(f"  → {p}")

    seen_ids = set()
    all_videos = []

    for phrase in phrases:
        results = search_youtube(phrase, max_results=results_per_phrase)
        for video in results:
            if video["video_id"] not in seen_ids:
                seen_ids.add(video["video_id"])
                all_videos.append(video)

    print(f"[search] Fetched {len(all_videos)} unique candidate videos.\n")
    return all_videos