"""Sincronização do bruto (data/raw) com o dataset privado no Hugging Face.

    python -m pipeline.remote pull     # antes de coletar: traz partições e checkpoint
    python -m pipeline.remote push     # depois: envia só os arquivos alterados

Salvaguardas (docs/decisions/armazenamento-bruto.md):
  - recusa operar se o dataset não for privado;
  - `push` nunca espelha o diretório local apagando o que falta no remoto: um runner que começou
    vazio por falha apagaria tudo. Remoção só com a lista explícita `deleted` (partições que o
    RawStore esvaziou);
  - depois de qualquer remoção (`removed=True`), o histórico é comprimido num único commit
    (`super_squash_history`) e os arquivos LFS que o commit atual não referencia são apagados de
    vez. Só o squash não basta: medido em 05/11/2026, o arquivo removido continuava baixável pelo
    SHA do commit antigo, porque o HF guarda os LFS fora do histórico git;
  - só sobem partições e checkpoint: nada de .tmp nem arquivos soltos.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from huggingface_hub import HfApi

from pipeline.config import settings

log = logging.getLogger(__name__)

PATTERNS = ["source=*/day=*/items.parquet", "_checkpoint/*.json"]


class RemoteRaw:
    def __init__(self, repo: str | None = None, token: str | None = None, api: HfApi | None = None):
        self.repo = repo or settings.hf_raw_repo
        token = token or settings.hf_token
        if not self.repo or not token:
            raise RuntimeError("HF_RAW_REPO e HF_TOKEN são obrigatórios para sincronizar o bruto")
        self.api = api or HfApi(token=token)
        self._checked = False

    def _ensure_private(self) -> None:
        if self._checked:
            return
        if not self.api.repo_info(self.repo, repo_type="dataset").private:
            raise RuntimeError(f"{self.repo} não é privado: sincronização recusada")
        self._checked = True

    def pull(self, root: Path) -> None:
        self._ensure_private()
        root.mkdir(parents=True, exist_ok=True)
        self.api.snapshot_download(self.repo, repo_type="dataset", local_dir=root, allow_patterns=PATTERNS)

    def push(self, root: Path, message: str, deleted: list[str] | None = None, removed: bool = False) -> None:
        """Envia partições alteradas. `deleted`: caminhos relativos a apagar no remoto.
        `removed=True` quando algum item saiu (mesmo de partição que continua existindo)."""
        self._ensure_private()
        for rel in deleted or []:
            if not any(Path(rel).match(p) for p in PATTERNS):
                raise ValueError(f"caminho fora das partições: {rel}")
        self.api.upload_folder(repo_id=self.repo, repo_type="dataset", folder_path=root,
                               allow_patterns=PATTERNS, delete_patterns=list(deleted or []) or None,
                               commit_message=message)
        if removed or deleted:
            self.api.super_squash_history(self.repo, repo_type="dataset",
                                          commit_message="squash após remoção de itens")
            purged = self.purge_orphan_lfs()
            log.info("histórico comprimido; %d arquivos LFS órfãos apagados", purged)

    def purge_orphan_lfs(self) -> int:
        """Apaga de vez os arquivos LFS que nenhum arquivo do commit atual referencia."""
        info = self.api.repo_info(self.repo, repo_type="dataset", files_metadata=True)
        live = {s.lfs.sha256 for s in info.siblings if s.lfs}
        orphans = [f for f in self.api.list_lfs_files(self.repo, repo_type="dataset") if f.file_oid not in live]
        if orphans:
            self.api.permanently_delete_lfs_files(self.repo, orphans, repo_type="dataset")
        return len(orphans)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pull", "push"])
    ap.add_argument("--message", default="sync do bruto")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    remote = RemoteRaw()
    if args.cmd == "pull":
        remote.pull(settings.raw_dir)
    else:
        remote.push(settings.raw_dir, args.message)


if __name__ == "__main__":
    main()
