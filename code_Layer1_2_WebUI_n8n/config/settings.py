"""Environment-backed settings for local development."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    n8n_webhook_url: str
    ollama_base_url: str
    ollama_model: str
    request_timeout_seconds: int


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer. Received: {raw_value!r}") from exc


def get_settings() -> Settings:
    return Settings(
        n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL", "").strip(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3").strip(),
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 30),
    )
