"""Unit tests for Slack-compatible corpus_id path isolation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from config.settings import Settings
from src.models import IssueInput
from src.rag.corpus_paths import normalize_corpus_id, resolve_corpus_paths


def test_normalize_corpus_id_accepts_safe_ids() -> None:
    assert normalize_corpus_id(None) is None
    assert normalize_corpus_id("") is None
    assert normalize_corpus_id("  acme-kb  ") == "acme-kb"
    assert normalize_corpus_id("intacct.help_1") == "intacct.help_1"


def test_normalize_corpus_id_rejects_paths() -> None:
    with pytest.raises(ValueError):
        normalize_corpus_id("../secret")
    with pytest.raises(ValueError):
        normalize_corpus_id("a/b")
    with pytest.raises(ValueError):
        normalize_corpus_id("-leading-dash")


def test_resolve_default_paths_use_legacy_roots(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        help_cache_dir=tmp_path / "data" / "help_xhtml",
        help_assets_dir=tmp_path / "data" / "help_assets",
        okf_dir=tmp_path / "data" / "okf",
        vector_store_dir=tmp_path / "data" / "vector_store",
    )
    paths = resolve_corpus_paths(settings, None)
    assert paths.corpus_id is None
    assert paths.vector_store_dir == settings.vector_store_dir
    assert paths.help_cache_dir == settings.help_cache_dir


def test_resolve_named_corpus_is_isolated(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        help_cache_dir=tmp_path / "data" / "help_xhtml",
        help_assets_dir=tmp_path / "data" / "help_assets",
        okf_dir=tmp_path / "data" / "okf",
        vector_store_dir=tmp_path / "data" / "vector_store",
    )
    a = resolve_corpus_paths(settings, "acme-kb")
    b = resolve_corpus_paths(settings, "intacct-help")
    a.ensure()
    b.ensure()
    assert a.corpus_id == "acme-kb"
    assert a.vector_store_dir == tmp_path / "data" / "corpora" / "acme-kb" / "vector_store"
    assert b.vector_store_dir == tmp_path / "data" / "corpora" / "intacct-help" / "vector_store"
    assert a.vector_store_dir != b.vector_store_dir
    assert a.vector_store_dir.is_dir()
    assert (a.help_assets_dir / "files").is_dir()


def test_issue_input_accepts_corpus_id() -> None:
    issue = IssueInput(text="How do I reverse a journal entry?", corpus_id="acme-kb")
    assert issue.corpus_id == "acme-kb"


def test_issue_input_rejects_oversized_corpus_id() -> None:
    with pytest.raises(ValidationError):
        IssueInput(text="How do I reverse a journal entry?", corpus_id="x" * 65)
