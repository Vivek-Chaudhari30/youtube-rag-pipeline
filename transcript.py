"""
transcript.py
-------------
Downloads transcripts (captions) for YouTube videos and splits them into
overlapping chunks that are ready for embedding.

Why chunk instead of embed the whole transcript?
  A sentence-transformer model has a token limit (usually 512 tokens, ~350 words).
  A 20-minute tutorial might have 3,000+ words. If you pass the whole thing,
  it gets silently truncated and you lose most of the content.

  By chunking into ~200-word pieces with a 50-word overlap between chunks,
  every part of the transcript gets a fair shot at matching the query.

  The overlap (stride < chunk_size) ensures a sentence that straddles a chunk
  boundary still gets represented fully in at least one chunk.

Chunk example (chunk_size=200, stride=150):
  chunk 0: words 0-199
  chunk 1: words 150-349   ← 50-word overlap with chunk 0
  chunk 2: words 300-499
  ...
"""

from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def get_transcript(video_id: str) -> str | None:
    """
    Download the transcript for a YouTube video and return it as plain text.

    Returns None if no transcript is available (some videos disable captions,
    or only have auto-generated ones in a language we can't use).

    video_id: the part after "watch?v=" in the URL.
              e.g. for https://www.youtube.com/watch?v=dQw4w9WgXcQ
              the video_id is "dQw4w9WgXcQ"
    """
    try:
        # Try to get English transcript first, then fall back to any available
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_transcript(["en"])
        except Exception:
            # Fall back to auto-translated English if manual English not available
            transcript = transcript_list.find_generated_transcript(["en"])

        entries = transcript.fetch()
        # Each entry is {"text": "...", "start": 12.5, "duration": 3.2}
        # We join all the text together, cleaning up line breaks from auto-captions
        full_text = " ".join(
            entry["text"].replace("\n", " ").strip()
            for entry in entries
        )
        return full_text

    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception as e:
        print(f"  [transcript] Error fetching {video_id}: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 200, stride: int = 150) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    chunk_size : number of words per chunk
    stride     : how many words to advance before starting the next chunk
                 stride < chunk_size means chunks overlap by (chunk_size - stride) words

    Returns a list of chunk strings.
    If the text is shorter than chunk_size, returns it as a single chunk.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start += stride
        if start >= len(words):
            break

    return chunks


def get_chunks_for_video(video: dict) -> list[dict] | None:
    """
    Given a video dict (from search.py), fetch its transcript and return
    a list of chunk dicts ready for embedding.

    Each chunk dict looks like:
    {
        "video_id"  : "dQw4w9WgXcQ",
        "title"     : "Rick Astley - Never Gonna Give You Up",
        "url"       : "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "channel"   : "RickAstleyVEVO",
        "chunk_idx" : 0,
        "text"      : "We're no strangers to love you know the rules ...",
    }

    Returns None if no transcript could be fetched.
    """
    video_id = video["video_id"]
    transcript = get_transcript(video_id)

    if not transcript:
        print(f"  [transcript] No transcript for: {video['title'][:60]}")
        return None

    chunks = chunk_text(transcript)
    result = []
    for idx, chunk_text_content in enumerate(chunks):
        result.append({
            "video_id" : video_id,
            "title"    : video["title"],
            "url"      : video["url"],
            "channel"  : video["channel"],
            "chunk_idx": idx,
            "text"     : chunk_text_content,
        })

    print(f"  [transcript] {video['title'][:50]} → {len(result)} chunks")
    return result


def process_all_videos(videos: list[dict]) -> list[dict]:
    """
    Loop over a list of candidate videos and collect all chunks from all videos
    that have transcripts.

    Returns a flat list of all chunks across all videos.
    """
    all_chunks = []
    print(f"[transcript] Processing {len(videos)} videos...\n")

    for video in videos:
        chunks = get_chunks_for_video(video)
        if chunks:
            all_chunks.extend(chunks)

    print(f"\n[transcript] Total chunks collected: {len(all_chunks)}")
    return all_chunks