import json
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings
from src.rag.index_help import build_index
from src.rag.xhtml_ingest import XhtmlDocument
from tests.fakes import FakePipelineLLM


class FakeCrawler:
    def __init__(self, documents: list[XhtmlDocument], errors=None, skipped=None) -> None:
        self.documents = documents
        self.errors = errors or []
        self.skipped = skipped or []

    def crawl(self, max_pages=None) -> list[XhtmlDocument]:
        return self.documents if max_pages is None else self.documents[:max_pages]


@dataclass
class RecordingStore:
    replaced: list[str]
    deleted: list[str]

    def replace_source(self, source_url, chunks, embeddings) -> None:
        assert len(chunks) == len(embeddings)
        self.replaced.append(source_url)

    def delete_source(self, source_url) -> None:
        self.deleted.append(source_url)


def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        help_cache_dir=tmp_path / "help",
        help_locales="en_US",
        vector_store_dir=tmp_path / "vectors",
        runs_dir=tmp_path / "runs",
        output_dir=tmp_path / "output",
        scripts_dir=tmp_path / "output" / "scripts",
        payloads_dir=tmp_path / "output" / "payloads",
        videos_dir=tmp_path / "output" / "videos",
        published_dir=tmp_path / "output" / "published",
    )


def document(tmp_path: Path, content_hash: str = "hash-1") -> XhtmlDocument:
    page = tmp_path / "help" / "pages" / "topic.xhtml"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "<html><body><main><h1>Topic</h1><p>Useful official help.</p></main></body></html>",
        encoding="utf-8",
    )
    return XhtmlDocument(
        url="https://www.intacct.com/ia/docs/en_US/help_action/topic.htm",
        cache_path="pages/topic.xhtml",
        content_sha256=content_hash,
        fetched_at="now",
    )


def test_index_skips_unchanged_content_on_second_run(tmp_path) -> None:
    app_settings = settings(tmp_path)
    source = document(tmp_path)
    store = RecordingStore([], [])
    crawler = FakeCrawler([source])

    first = build_index(
        None,
        settings=app_settings,
        crawler=crawler,
        store=store,
        llm=FakePipelineLLM(),
    )
    second = build_index(
        None,
        settings=app_settings,
        crawler=crawler,
        store=store,
        llm=FakePipelineLLM(),
    )

    assert first.pages_indexed == 1
    assert first.complete is True
    assert second.pages_unchanged == 1
    assert store.replaced == [source.url]


def test_index_does_not_delete_stale_sources_when_crawl_has_errors(tmp_path) -> None:
    app_settings = settings(tmp_path)
    state = app_settings.vector_store_dir / "index_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text('{"https://example/stale.htm":"old"}', encoding="utf-8")
    store = RecordingStore([], [])

    summary = build_index(
        None,
        delete_stale=True,
        settings=app_settings,
        crawler=FakeCrawler([], errors=[{"url": "broken"}]),
        store=store,
        llm=FakePipelineLLM(),
    )

    assert summary.complete is False
    assert summary.crawl_errors == 1
    assert store.deleted == []


def test_index_from_cache_uses_manifest_pages(tmp_path) -> None:
    app_settings = settings(tmp_path)
    source = document(tmp_path)
    manifest = {
        "start_url": source.url,
        "allowed_prefix": "https://www.intacct.com/ia/docs/en_US/help_action/",
        "complete": False,
        "errors": [
            {
                "url": "https://www.intacct.com/ia/docs/en_US/help_action/missing.htm",
                "error_type": "HTTPStatusError",
                "status_code": 404,
            }
        ],
        "pages": [source.__dict__],
    }
    (app_settings.help_cache_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    store = RecordingStore([], [])

    summary = build_index(
        None,
        delete_stale=True,
        from_cache=True,
        settings=app_settings,
        store=store,
        llm=FakePipelineLLM(),
    )

    assert summary.complete is True
    assert summary.pages_indexed == 1
    assert store.replaced == [source.url]
    updated = json.loads(
        (app_settings.help_cache_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert updated["complete"] is True
    assert updated["errors"] == []
    assert updated["skipped"][0]["status_code"] == 404
