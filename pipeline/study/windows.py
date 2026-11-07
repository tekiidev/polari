"""Janelas do estudo antes/depois das eleições de 2026.

Regras que o resto do pipeline deve respeitar:
  - Todo agrupamento por dia usa o DIA LOCAL (America/Sao_Paulo), nunca UTC.
    Um post de 01:30 UTC de 26/10 aconteceu às 22:30 de 25/10 no Brasil.
  - Os dias de votação (04/10 e 25/10) ficam no período que termina neles.
  - `PERIODS` e `EVENTS` são DADOS: ajuste aqui, sem espalhar datas pelo código.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

INICIO_CAMPANHA = date(2026, 8, 16)
PRIMEIRO_TURNO = date(2026, 10, 4)
SEGUNDO_TURNO = date(2026, 10, 25)

EVENTS: dict[str, date] = {
    "primeiro_turno": PRIMEIRO_TURNO,
    "segundo_turno": SEGUNDO_TURNO,
}


@dataclass(frozen=True)
class Period:
    name: str
    start: date  # inclusivo
    end: date | None  # inclusivo; None = em aberto (continua crescendo)


PERIODS: list[Period] = [
    # DECISÃO SUA: qual intervalo é a "linha de base calma"? Justifique em docs/METHODOLOGY.md.
    # Atenção: convenções partidárias (jul/ago) podem elevar o discurso político.
    Period("baseline", date(2026, 6, 1), date(2026, 8, 15)),
    Period("campanha_1t", INICIO_CAMPANHA, PRIMEIRO_TURNO),
    Period("entre_turnos", PRIMEIRO_TURNO + timedelta(days=1), SEGUNDO_TURNO),
    Period("pos_eleicao", SEGUNDO_TURNO + timedelta(days=1), None),
]


def local_day(dt: datetime) -> date:
    """Converte um datetime COM fuso para o dia local do Brasil."""
    if dt.tzinfo is None:
        raise ValueError("datetime sem fuso: converta para aware (UTC) antes de agrupar por dia")
    return dt.astimezone(TZ).date()


def day_bounds(d: date) -> tuple[datetime, datetime]:
    """[00:00, 24:00) do dia local, em UTC. Dias com troca de horário têm 23 ou 25 horas."""
    start = datetime.combine(d, time(0), TZ).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), time(0), TZ).astimezone(timezone.utc)
    return start, end


def period_of(d: date) -> str | None:
    """Nome do período que contém o dia, ou None se estiver fora de todos."""
    for p in PERIODS:
        if p.start <= d and (p.end is None or d <= p.end):
            return p.name
    return None


def event_window(event: date, before: int = 14, after: int = 14) -> tuple[date, date]:
    """Janela alinhada a um evento: (D-before, D+after), ambos inclusivos."""
    return event - timedelta(days=before), event + timedelta(days=after)


def day_offset(d: date, event: date) -> int:
    """Dias relativos ao evento (D0 = dia da votação; negativo = antes)."""
    return (d - event).days
