"""Configuração central lida do ambiente (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    bluesky_handle: str = os.getenv("BLUESKY_HANDLE", "")
    bluesky_app_password: str = os.getenv("BLUESKY_APP_PASSWORD", "")
    nominatim_user_agent: str = os.getenv("NOMINATIM_USER_AGENT", "")
    min_cell_size: int = int(os.getenv("MIN_CELL_SIZE", "3"))
    secret_key: str = os.getenv("POLARI_SECRET_KEY", "")

    raw_dir: Path = ROOT / "data" / "raw"
    processed_dir: Path = ROOT / "data" / "processed"
    out_dir: Path = ROOT / "web" / "public" / "data"
    prompt_path: Path = ROOT / "prompts" / "classifier.md"
    schema_path: Path = ROOT / "schemas" / "classification.schema.json"


settings = Settings()
