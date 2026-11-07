"""Sincronização com o HF (API simulada): privacidade, remoção explícita e squash."""
from types import SimpleNamespace

import pytest

from pipeline.remote import RemoteRaw


class FakeApi:
    def __init__(self, private=True):
        self.private = private
        self.calls: list[tuple[str, dict]] = []

    def upload_folder(self, **kw):
        self.calls.append(("upload", kw))

    def super_squash_history(self, repo, **kw):
        self.calls.append(("squash", kw))

    def repo_info(self, repo, repo_type, files_metadata=False):
        live = SimpleNamespace(rfilename="vivo.parquet", lfs=SimpleNamespace(sha256="vivo"))
        return SimpleNamespace(private=self.private, siblings=[live, SimpleNamespace(rfilename=".gitattributes", lfs=None)])

    def list_lfs_files(self, repo, repo_type):
        return [SimpleNamespace(file_oid="vivo"), SimpleNamespace(file_oid="orfao")]

    def permanently_delete_lfs_files(self, repo, files, **kw):
        self.calls.append(("purge", [f.file_oid for f in files]))


def test_refuses_public_repo(tmp_path):
    with pytest.raises(RuntimeError, match="não é privado"):
        RemoteRaw("u/r", "t", api=FakeApi(private=False)).push(tmp_path, "m")


def test_plain_push_never_deletes_or_squashes(tmp_path):
    api = FakeApi()
    RemoteRaw("u/r", "t", api=api).push(tmp_path, "m")
    ((name, kw),) = api.calls
    assert name == "upload" and kw["delete_patterns"] is None
    assert "source=*/day=*/items.parquet" in kw["allow_patterns"]


def test_removal_deletes_listed_paths_then_squashes(tmp_path):
    api = FakeApi()
    rel = "source=bluesky/day=2026-10-04/items.parquet"
    RemoteRaw("u/r", "t", api=api).push(tmp_path, "m", deleted=[rel])
    assert [c[0] for c in api.calls] == ["upload", "squash", "purge"]
    assert api.calls[0][1]["delete_patterns"] == [rel]
    assert api.calls[2][1] == ["orfao"]  # só o que o commit atual não usa


def test_rewritten_partition_also_squashes(tmp_path):
    api = FakeApi()
    RemoteRaw("u/r", "t", api=api).push(tmp_path, "m", removed=True)
    assert [c[0] for c in api.calls] == ["upload", "squash", "purge"]


def test_rejects_delete_outside_partitions(tmp_path):
    with pytest.raises(ValueError):
        RemoteRaw("u/r", "t", api=FakeApi()).push(tmp_path, "m", deleted=["*"])
