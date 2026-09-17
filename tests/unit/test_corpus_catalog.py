"""Unit tests for named Help corpus catalog parsing and URL overlay."""

from pathlib import Path

import pytest

from config.settings import Settings
from src.qa.ask_agent import is_allowed_help_url, scrub_non_help_urls
from src.rag.corpus_catalog import (
    help_settings_for_corpus,
    load_catalog,
    parse_catalog_text,
)


def _settings(tmp_path: Path, catalog: str | None = None) -> Settings:
    path = tmp_path / "corpus_catalog.txt"
    if catalog is not None:
        path.write_text(catalog, encoding="utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        help_cache_dir=tmp_path / "data" / "help_xhtml",
        help_assets_dir=tmp_path / "data" / "help_assets",
        okf_dir=tmp_path / "data" / "okf",
        vector_store_dir=tmp_path / "data" / "vector_store",
        corpus_catalog_path=path,
        help_start_url="https://termweb.atlassian.net/wiki/spaces/TWKB/overview",
        help_allowed_prefix="https://termweb.atlassian.net/wiki/spaces/TWKB",
    )


def test_settings_ignores_legacy_intacct_help_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "INTACCT_HELP_START_URL", "https://legacy.test/welcome.htm"
    )
    monkeypatch.setenv("INTACCT_HELP_ALLOWED_PREFIX", "https://legacy.test/")
    settings = Settings()
    assert settings.help_start_url == ""
    assert settings.help_allowed_prefix == ""
    text = """
# comment
start_url, allowed_prefix, corpus_id
https://help.acme.test/welcome.htm, https://help.acme.test/, acme-kb
"https://docs.other.test/space/home", "https://docs.other.test/space", other.docs
"""
    entries = parse_catalog_text(text)
    assert [item.corpus_id for item in entries] == ["acme-kb", "other.docs"]
    assert entries[0].start_url == "https://help.acme.test/welcome.htm"
    assert entries[1].allowed_prefix == "https://docs.other.test/space"


def test_parse_jsonl() -> None:
    text = (
        '{"url":"https://help.acme.test/a.htm","allowed_prefix":'
        '"https://help.acme.test/","corpus_id":"acme-kb"}\n'
    )
    entries = parse_catalog_text(text)
    assert len(entries) == 1
    assert entries[0].corpus_id == "acme-kb"


def test_rejects_start_outside_prefix() -> None:
    with pytest.raises(ValueError, match="outside allowed_prefix"):
        parse_catalog_text(
            "https://evil.test/page, https://help.acme.test/, acme-kb\n"
        )


def test_rejects_duplicate_corpus_id() -> None:
    with pytest.raises(ValueError, match="duplicate corpus_id"):
        parse_catalog_text(
            "https://help.acme.test/a.htm, https://help.acme.test/, acme-kb\n"
            "https://help.acme.test/b.htm, https://help.acme.test/, acme-kb\n"
        )


def test_missing_catalog_keeps_explicit_urls(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    overlay = help_settings_for_corpus(settings, "acme-kb")
    assert overlay.help_start_url == settings.help_start_url


def test_missing_catalog_named_id_raises_without_urls(tmp_path: Path) -> None:
    path = tmp_path / "corpus_catalog.txt"
    settings = Settings(
        data_dir=tmp_path / "data",
        help_cache_dir=tmp_path / "data" / "help_xhtml",
        help_assets_dir=tmp_path / "data" / "help_assets",
        okf_dir=tmp_path / "data" / "okf",
        vector_store_dir=tmp_path / "data" / "vector_store",
        corpus_catalog_path=path,
    )
    with pytest.raises(ValueError, match="not in catalog"):
        help_settings_for_corpus(settings, "acme-kb")


def test_help_settings_overlay_named_corpus(tmp_path: Path) -> None:
    catalog = (
        "https://help.acme.test/welcome.htm, https://help.acme.test/, acme-kb\n"
    )
    settings = _settings(tmp_path, catalog)
    defaulted = help_settings_for_corpus(settings, None)
    assert defaulted.help_allowed_prefix.endswith("TWKB")
    overlay = help_settings_for_corpus(settings, "acme-kb")
    assert overlay.help_start_url == "https://help.acme.test/welcome.htm"
    assert overlay.help_allowed_prefix == "https://help.acme.test/"
    loaded = load_catalog(settings.corpus_catalog_path)
    assert loaded[0].corpus_id == "acme-kb"


def test_default_corpus_uses_first_catalog_row(tmp_path: Path) -> None:
    catalog = (
        "https://help.acme.test/welcome.htm, https://help.acme.test/, acme-kb\n"
        "https://docs.other.test/home, https://docs.other.test/, other\n"
    )
    path = tmp_path / "corpus_catalog.txt"
    path.write_text(catalog, encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        help_cache_dir=tmp_path / "data" / "help_xhtml",
        help_assets_dir=tmp_path / "data" / "help_assets",
        okf_dir=tmp_path / "data" / "okf",
        vector_store_dir=tmp_path / "data" / "vector_store",
        corpus_catalog_path=path,
    )
    defaulted = help_settings_for_corpus(settings, None)
    assert defaulted.help_start_url == "https://help.acme.test/welcome.htm"
    assert defaulted.help_allowed_prefix == "https://help.acme.test/"


def test_ask_allowlist_uses_catalog_prefix(tmp_path: Path) -> None:
    catalog = (
        "https://help.acme.test/welcome.htm, https://help.acme.test/, acme-kb\n"
    )
    settings = _settings(tmp_path, catalog)
    overlay = help_settings_for_corpus(settings, "acme-kb")
    acme = "https://help.acme.test/topics/foo.htm"
    termweb = "https://termweb.atlassian.net/wiki/spaces/TWKB/pages/1"
    assert is_allowed_help_url(acme, settings=overlay)
    assert not is_allowed_help_url(termweb, settings=overlay)
    assert acme in scrub_non_help_urls(f"See {acme}", settings=overlay)
    assert "termweb" not in scrub_non_help_urls(f"See {termweb}", settings=overlay)
    assert is_allowed_help_url(termweb, settings=settings)
