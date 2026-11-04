from __future__ import annotations

import io
import os
from pathlib import Path

import requests
from pypdf import PdfReader


def _read_pdf_bytes(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[1] / path


def load_cv_text() -> str:
    cv_url = os.getenv("CV_URL", "").strip()
    cv_path = os.getenv("CV_PATH", "./Abolore_Sanni_CV.pdf").strip()

    if cv_url:
        response = requests.get(cv_url, timeout=30)
        response.raise_for_status()
        return _read_pdf_bytes(response.content)

    path = _resolve_path(cv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"CV file not found at {path}. Set CV_PATH or CV_URL in AI_Chatbot/.env."
        )

    return _read_pdf_bytes(path.read_bytes())


def load_knowledge_text() -> str:
    """Optionally load extra portfolio knowledge beyond the CV.

    Supports either a single file (KNOWLEDGE_FILE) or a directory of
    .md/.txt files (KNOWLEDGE_DIR). Useful for project write-ups,
    FAQs, availability, and services.
    """
    chunks: list[str] = []

    knowledge_file = os.getenv("KNOWLEDGE_FILE", "").strip()
    if knowledge_file:
        path = _resolve_path(knowledge_file)
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))

    knowledge_dir = os.getenv("KNOWLEDGE_DIR", "").strip()
    if knowledge_dir:
        directory = _resolve_path(knowledge_dir)
        if directory.is_dir():
            for path in sorted(directory.glob("*")):
                if path.suffix.lower() in {".md", ".txt"}:
                    chunks.append(
                        f"# {path.stem}\n\n"
                        + path.read_text(encoding="utf-8", errors="ignore")
                    )

    return "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip())
