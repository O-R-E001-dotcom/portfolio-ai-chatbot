from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.cv_loader import load_cv_text, load_knowledge_text
from app.rag import CVRag

load_dotenv()

CACHE_PATH = Path(__file__).resolve().parents[1] / ".cache" / "cv_index.json"

SUGGESTIONS = [
    "What are Abolore's core technical skills?",
    "Tell me about the AI projects.",
    "What kind of backend experience does Abolore have?",
    "Is Abolore available for remote work?",
    "How can I contact Abolore?",
]


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(default="", max_length=2_000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    history: Optional[list[HistoryMessage]] = None


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str
    model: str
    chunks: int


def _cors_origins() -> list[str]:
    origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://portfolio-eta-flax-91.vercel.app",
    )
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_rag() -> CVRag:
    cv_text = load_cv_text()
    extra_text = load_knowledge_text()
    return CVRag(cv_text, extra_text=extra_text, cache_path=CACHE_PATH)


app = FastAPI(
    title="Portfolio AI Chatbot",
    description="CV-grounded RAG assistant for Abolore Sanni's portfolio.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Portfolio AI chatbot is running"}


@app.get("/health", response_model=HealthResponse)
def health():
    try:
        rag = get_rag()
        return HealthResponse(
            status="ok",
            model=rag.chat_model,
            chunks=len(rag.chunks),
        )
    except Exception:
        return HealthResponse(status="degraded", model="", chunks=0)


@app.get("/suggestions")
def suggestions():
    return {"suggestions": SUGGESTIONS}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        rag = get_rag()
        history = [turn.model_dump() for turn in (payload.history or [])]
        answer = rag.answer(payload.question, history=history)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail="Unable to answer right now."
        ) from exc

    return ChatResponse(answer=answer)


@app.post("/chat/stream")
def chat_stream(payload: ChatRequest):
    """Stream the answer as plain text chunks (used by the portfolio widget)."""
    try:
        rag = get_rag()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail="Unable to answer right now."
        ) from exc

    history = [turn.model_dump() for turn in (payload.history or [])]

    def event_stream():
        try:
            for token in rag.stream_answer(payload.question, history=history):
                yield token
        except Exception:  # noqa: BLE001
            yield (
                "\n\nSorry, the response was interrupted. "
                "Please try again in a moment."
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/reload")
def reload_cv(
    x_reload_token: Optional[str] = Header(default=None, alias="X-Reload-Token"),
):
    expected = os.getenv("RELOAD_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Reload is disabled. Set RELOAD_TOKEN to enable it.",
        )
    if not x_reload_token or not secrets.compare_digest(x_reload_token, expected):
        raise HTTPException(status_code=401, detail="Invalid reload token.")

    get_rag.cache_clear()
    try:
        rag = get_rag()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": "CV knowledge base reloaded",
        "chunks": len(rag.chunks),
    }
