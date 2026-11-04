# Portfolio AI Chatbot

A standalone, CV-grounded RAG assistant for Abolore Sanni's portfolio.

It loads the CV (and optional extra knowledge), splits it into overlapping
chunks, embeds the chunks with OpenAI embeddings, retrieves the most relevant
context for each question, and answers **only** from that context. The system
prompt forbids inventing employers, dates, degrees, metrics, or links.

## How it works

- `app/cv_loader.py` — loads the CV from `CV_PATH` or `CV_URL`, plus optional
  extra knowledge from `KNOWLEDGE_FILE` or `KNOWLEDGE_DIR`.
- `app/rag.py` — chunking, embedding, disk-cached index, cosine retrieval with
  keyword boosting, and answer generation.
- `app/main.py` — FastAPI API: `/chat`, `/suggestions`, `/health`, `/reload`.
- `.cache/` — the embedding cache (`cv_index.json`) is rebuilt only when the CV
  or embedding model changes.

## Setup

```powershell
cd AI_Chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-your-key-here
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Use ONE of these:
CV_PATH="./Abolore_Sanni_CV.pdf"
# CV_URL=http://localhost:8000/profile/cv/view

PORT=8010
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## Run

```powershell
uvicorn app.main:app --reload --port 8010
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8010/health
```

Ask a question:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8010/chat `
  -ContentType application/json `
  -Body '{"question":"What skills does Abolore have?"}'
```

The request body also accepts a short conversation history:

```json
{
  "question": "And which of those has he used in production?",
  "history": [
    { "role": "user", "content": "What are his core skills?" },
    { "role": "assistant", "content": "LangGraph, LangChain, FastAPI..." }
  ]
}
```

## Frontend

The widget already lives at
`frontend/src/components/PortfolioChatbot.jsx` and is rendered from
`frontend/src/App.jsx`. Point it at this service with:

```env
VITE_CHATBOT_API_URL=http://localhost:8010
```

## Extra knowledge (optional)

Create `knowledge/*.md` files (project write-ups, availability, FAQs) and set:

```env
KNOWLEDGE_DIR="./knowledge"
```

These are embedded alongside the CV, tagged with a `knowledge` source.

## Production deployment

### Render / Heroku (Procfile)

A `Procfile` is included for `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

1. Create a new web service pointing at `AI_Chatbot/`.
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add env vars: `OPENAI_API_KEY`, `CHAT_MODEL`, `EMBEDDING_MODEL`, `CV_URL` (or `CV_PATH`), `CORS_ORIGINS` (include production frontend URL), optional `RELOAD_TOKEN`.

### Docker

```bash
docker build -t portfolio-chatbot AI_Chatbot
docker run -p 8010:8010 --env-file AI_Chatbot/.env portfolio-chatbot
```

The image uses the included `Dockerfile` with `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]`.

### After deployment

Update `frontend/.env` (and Vercel env vars) with the new chatbot URL:

```env
VITE_CHATBOT_API_URL=https://your-chatbot-host.com
```

Rebuild and redeploy the frontend so the production bundle embeds the correct URL.

## Notes

- Never commit `.env`.
- After changing the CV, call `POST /reload` with `X-Reload-Token` equal to
  `RELOAD_TOKEN` (or restart the service). The cache fingerprint detects changes
  automatically on the next launch. `/reload` is disabled when `RELOAD_TOKEN`
  is unset.
- If `OPENAI_API_KEY` is missing, `/health` reports `degraded` and `/chat`
  returns HTTP 503 with a clear message.
- Answers are requested as plain text so the portfolio widget never renders
  raw Markdown.
