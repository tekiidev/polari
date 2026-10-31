"""Saúde do pipeline: métricas por execução, para ver como as ferramentas se comportam no tempo.

Cada execução grava UMA linha em data/processed/runs.jsonl. O front lê um resumo
(web/public/data/health.json) e mostra a evolução: quantos itens entraram, quanto passou no
pré-filtro, quanto foi classificado e geolocalizado, erros e uso da cota do LLM.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class RunMetrics(BaseModel):
    run_at: datetime
    source: str
    window_start: date | None = None
    window_end: date | None = None
    collected: int = Field(ge=0)
    passed_prefilter: int = Field(ge=0)
    classified: int = Field(ge=0)
    classification_errors: int = Field(ge=0)
    political_violence: int = Field(ge=0)
    geolocated: int = Field(ge=0)
    llm_requests: int = Field(ge=0)
    duration_s: float = Field(ge=0)
    model_id: str
    prompt_version: str

    @property
    def prefilter_rate(self) -> float:
        return self.passed_prefilter / self.collected if self.collected else 0.0

    @property
    def error_rate(self) -> float:
        total = self.classified + self.classification_errors
        return self.classification_errors / total if total else 0.0

    @property
    def geolocated_rate(self) -> float:
        return self.geolocated / self.political_violence if self.political_violence else 0.0


def append_run_metrics(metrics: RunMetrics, path: Path) -> None:
    """Acrescenta uma linha JSON ao arquivo de execuções."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(metrics.model_dump_json() + "\n")
