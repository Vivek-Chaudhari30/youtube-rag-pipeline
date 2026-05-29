# YouTube Semantic Search (RAG Pipeline)

Semantic search over YouTube video transcripts: fetch candidates, download transcripts, embed with sentence-transformers, and rank with FAISS.

## Prerequisites

- Python 3.12+
- A [YouTube Data API v3](https://console.cloud.google.com/) key

## Setup

```bash
# From the repository root (this folder)

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set YOUTUBE_API_KEY=your_key_here
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

Restart uvicorn after changing `.env`.

## Test the API

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "sentiment analysis flask deployment"}'
```

## Project layout

- `main.py` — FastAPI app and routes
- `search.py` — YouTube search and query expansion
- `transcript.py` — Transcript download and chunking
- `embeddings.py` — Sentence-transformer embeddings
- `ranker.py` — FAISS ranking
- `index.html` — Frontend (also served at `/`)
