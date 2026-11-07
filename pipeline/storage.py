"""Armazenamento do texto bruto: Parquet particionado por fonte e dia local.

    data/raw/source=<fonte>/day=<AAAA-MM-DD>/items.parquet

Por que assim: cada partição é um arquivo pequeno e independente, então sincronizar com um
bucket remoto é enviar só as partições alteradas, e remover um post apagado pelo autor é
reescrever um arquivo. O diretório inteiro fica fora do git (.gitignore: data/raw/).

Garantias:
  - idempotente: a chave é (source, item_id); gravar o mesmo item de novo não duplica, só
    acrescenta à coluna `queries` as consultas novas que o trouxeram;
  - `source_ref` só é gravado criptografado (coluna `source_ref_enc`);
  - escrita atômica: grava num arquivo temporário e renomeia, então uma queda não corrompe a partição.
"""
from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

from pipeline.config import settings
from pipeline.models import RawItem
from pipeline.privacy import decrypt_ref, encrypt_ref
from pipeline.study.windows import local_day

COLUMNS = "item_id VARCHAR, source VARCHAR, text VARCHAR, created_at TIMESTAMPTZ, lang VARCHAR, " \
          "source_ref_enc VARCHAR, collected_at TIMESTAMPTZ, queries VARCHAR[]"


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _from_us(us: int) -> datetime:
    return _EPOCH + timedelta(microseconds=us)  # exato; dividir por 1e6 em float pode errar 1 µs


class RawStore:
    def __init__(self, root: Path | None = None, secret: str | None = None):
        self.root = root or settings.raw_dir
        self.secret = secret

    def _path(self, source: str, day: date) -> Path:
        return self.root / f"source={source}" / f"day={day.isoformat()}" / "items.parquet"

    def _read(self, path: Path) -> list[tuple]:
        if not path.exists():
            return []
        # Datas saem como epoch em µs: devolver TIMESTAMPTZ direto exigiria o pacote pytz.
        query = ("SELECT item_id, source, text, epoch_us(created_at), lang, source_ref_enc, "
                 f"epoch_us(collected_at), queries FROM read_parquet('{path}')")
        with duckdb.connect() as con:
            rows = con.execute(query).fetchall()
        return [(*r[:3], _from_us(r[3]), r[4], r[5], _from_us(r[6]), r[7] or []) for r in rows]

    def _write(self, path: Path, rows: list[tuple]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".parquet.tmp")
        with duckdb.connect() as con:
            con.execute("SET TimeZone = 'UTC'")
            con.execute(f"CREATE TABLE t ({COLUMNS})")
            con.executemany("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
            con.execute(f"COPY (SELECT * FROM t ORDER BY created_at, item_id) TO '{tmp}' (FORMAT parquet)")
        os.replace(tmp, path)

    def put(self, items: Iterable[RawItem]) -> int:
        """Grava os itens; devolve quantos eram novos."""
        now = datetime.now(timezone.utc)
        parts: dict[tuple[str, date], dict[str, tuple]] = defaultdict(dict)
        for it in items:
            part = parts[(it.source, local_day(it.created_at))]
            if it.item_id in part:
                part[it.item_id][7].extend(q for q in it.queries if q not in part[it.item_id][7])
                continue
            ref = encrypt_ref(it.source_ref, self.secret) if it.source_ref else None
            part[it.item_id] = (it.item_id, it.source, it.text, it.created_at, it.lang, ref, now,
                                list(it.queries))
        added = 0
        for (source, day), new in parts.items():
            path = self._path(source, day)
            rows = {r[0]: r for r in self._read(path)}
            changed = False
            for k, row in new.items():
                if k not in rows:
                    rows[k] = row
                    added += 1
                    changed = True
                    continue
                extra = [q for q in row[7] if q not in rows[k][7]]
                if extra:
                    rows[k] = (*rows[k][:7], sorted(rows[k][7] + extra))
                    changed = True
            if changed:
                self._write(path, [(*r[:7], sorted(r[7])) for r in rows.values()])
        return added

    def iter_items(self, source: str, start: date, end: date) -> Iterator[RawItem]:
        """Itens de [start, end] (dias locais, inclusivos), com source_ref já decifrado."""
        for d in sorted((self.root / f"source={source}").glob("day=*")):
            day = date.fromisoformat(d.name.removeprefix("day="))
            if not start <= day <= end:
                continue
            for item_id, src, text, created_at, lang, ref, _, queries in self._read(d / "items.parquet"):
                yield RawItem(source=src, item_id=item_id, text=text, created_at=created_at, lang=lang,
                              queries=queries, source_ref=decrypt_ref(ref, self.secret) if ref else None)

    def delete(self, source: str, day: date, item_ids: set[str]) -> int:
        """Remove itens (ex.: posts apagados pelo autor). Devolve quantos saíram."""
        path = self._path(source, day)
        rows = self._read(path)
        keep = [r for r in rows if r[0] not in item_ids]
        if len(keep) == len(rows):
            return 0
        if keep:
            self._write(path, keep)
        else:
            path.unlink()
        return len(rows) - len(keep)
