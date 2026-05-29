# YouTube Semantic Search (RAG Pipeline)

Semantic search over YouTube video transcripts: fetch candidates, download transcripts, embed with sentence-transformers, and rank with FAISS.

**No YouTube API key required** — video search uses [yt-dlp](https://github.com/yt-dlp/yt-dlp); transcripts use [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api).

## Prerequisites

- Python 3.12+

## Setup

```bash
# From the repository root (this folder)

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Search UI |
| http://localhost:8000/health | API health check (JSON) |
| http://localhost:8000/docs | OpenAPI / Swagger UI |

## Test the API

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "sentiment analysis flask deployment"}'
```

## Project layout

- `main.py` — FastAPI app and routes
- `search.py` — YouTube search (yt-dlp) and query expansion
- `transcript.py` — Transcript download and chunking
- `embeddings.py` — Sentence-transformer embeddings
- `ranker.py` — FAISS ranking
- `index.html` — Frontend (also served at `/`)
