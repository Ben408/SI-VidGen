"""Unit tests for Help locale helpers and multi-locale crawl wiring."""

from pathlib import Path

import httpx

from src.rag.locales import (
    HELP_LOCALES,
    assets_dir_for_locale,
    detect_question_language,
    edge_voice_for_locale,
    locale_from_help_url,
    locale_spec,
    normalize_answer_language,
    parse_locales,
)
from src.rag.xhtml_ingest import XhtmlCrawler


def test_parse_locales_all_and_csv() -> None:
    assert parse_locales("all") == list(HELP_LOCALES)
    assert parse_locales("fr_FR,de_DE") == ["fr_FR", "de_DE"]
    assert parse_locales("") == ["en_US"]


def test_locale_specs_match_live_path_tags() -> None:
    for loc in HELP_LOCALES:
        spec = locale_spec(loc)
        assert f"/{loc}/help_action/" in spec.allowed_prefix
        assert spec.start_url.startswith(spec.allowed_prefix)


def test_locale_from_help_url() -> None:
    assert (
        locale_from_help_url(
            "https://www.intacct.com/ia/docs/de_DE/help_action/Intacct_basics/welcome.htm"
        )
        == "de_DE"
    )
    assert locale_from_help_url("https://example.com/x") is None


def test_assets_dir_for_locale(tmp_path: Path) -> None:
    root = tmp_path / "help_assets"
    (root / "files").mkdir(parents=True)
    (root / "catalog.json").write_text("{}", encoding="utf-8")
    assert assets_dir_for_locale(root, "en_US") == root
    assert assets_dir_for_locale(root, "fr_FR") == root / "fr_FR"


def test_detect_and_normalize_answer_language() -> None:
    assert detect_question_language("Comment créer une écriture de journal?") == "fr_FR"
    assert detect_question_language("Wie erstelle ich eine Buchung?") == "de_DE"
    assert detect_question_language("Cómo crear un asiento contable?") == "es_ES"
    source, answer = normalize_answer_language(
        question="How do I reverse a journal entry?",
        answer_language="fr_FR",
    )
    assert source == "en_US"
    assert answer == "fr_FR"
    source2, answer2 = normalize_answer_language(
        question="Comment créer un fournisseur?",
    )
    assert source2 == answer2 == "fr_FR"


def test_edge_voices() -> None:
    assert edge_voice_for_locale("fr_FR").startswith("fr-FR-")
    assert edge_voice_for_locale("de_DE").startswith("de-DE-")
    assert edge_voice_for_locale("es_ES").startswith("es-ES-")


def test_crawler_accepts_french_prefix(tmp_path: Path) -> None:
    allowed = "https://www.intacct.com/ia/docs/fr_FR/help_action/"
    start = f"{allowed}Intacct_basics/welcome.htm"
    pages = {start: "<html><body><h1>Bienvenue</h1></body></html>"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=pages[str(request.url)],
            headers={"content-type": "application/xhtml+xml", "etag": '"fr"'},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    crawler = XhtmlCrawler(start, allowed, tmp_path, delay_seconds=0, client=client)
    docs = crawler.crawl(max_pages=1)
    assert len(docs) == 1
    assert "fr_FR" in docs[0].url
