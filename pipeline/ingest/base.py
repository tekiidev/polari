"""Interface comum das fontes. Nova fonte (inclusive o X) = nova subclasse."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from pipeline.models import RawItem


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self, since: datetime, until: datetime | None = None, limit: int = 500) -> Iterable[RawItem]:
        """Devolve itens criados em [since, until), no máximo `limit`. until=None = até agora.

        `since` e `until` devem ser datetimes COM fuso (UTC).
        """
        raise NotImplementedError
