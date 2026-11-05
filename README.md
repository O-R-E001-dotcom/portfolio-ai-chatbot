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
- `app/main.py` — FastAPI API: `/chat`, `/chat/stream`, `/suggestions`,
  `/health`, `/reload`.
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

Edit `.env`. You can use OpenAI directly or OpenRouter (OpenAI-compatible).

**Option A — OpenAI**

```env
OPENAI_API_KEY=sk-your-key-here
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

**Option B — OpenRouter**

```env
OPENROUTER_API_KEY=sk-or-your-key-here
CHAT_MODEL=openai/gpt-4o-mini
EMBEDDING_MODEL=openai/text-embedding-3-small
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

OpenRouter model IDs are namespaced (for example `openai/gpt-4o-mini`,
`anthropic/claude-3.5-sonnet`). Embedding models need the same prefix
(`openai/text-embedding-3-small`). When `OPENROUTER_API_KEY` is set the
service points at OpenRouter automatically.

Then:

```env
# Use ONE of these:
CV_PATH="./Abolore_Sanni_CV.pdf"
# CV_URL=https://portfolio-001-0ce74aa7e84e.herokuapp.com/profile/cv/view

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
  "question": "And which of those has she used in production?",
  "history": [
    { "role": "user", "content": "What are her core skills?" },
    { "role": "assistant", "content": "LangGraph, LangChain, FastAPI..." }
  ]
}
```

### Streaming

`POST /chat/stream` takes the same body and streams the answer as plain text
chunks, so the widget renders tokens as they arrive:

```powershell
curl.exe -N -X POST http://localhost:8010/chat/stream `
  -H "Content-Type: application/json" `
  -d '{\"question\":\"What skills does Abolore have?\"}'
```

The portfolio widget uses this endpoint by default. `/chat` is kept for
non-streaming clients.

Abolore is referred to with she/her pronouns everywhere in the generated
answers; the rule lives in `SYSTEM_PROMPT` in `app/rag.py`.

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
- If neither `OPENROUTER_API_KEY` nor `OPENAI_API_KEY` is set, `/health`
  reports `degraded` and `/chat` returns HTTP 503 with a clear message.
- Answers are requested as plain text so the portfolio widget never renders
  raw Markdown.
