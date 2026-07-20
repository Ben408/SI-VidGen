from pathlib import Path

import httpx

from src.rag.xhtml_ingest import XhtmlCrawler, extract_scoped_links, is_allowed_help_url

ALLOWED = "https://www.intacct.com/ia/docs/en_US/help_action/"


def test_allows_scoped_help_url() -> None:
    assert is_allowed_help_url(
        "https://www.intacct.com/ia/docs/en_US/help_action/General_Ledger/topic.htm",
        ALLOWED,
    )


def test_rejects_other_host_or_path() -> None:
    assert not is_allowed_help_url("https://example.com/ia/docs/en_US/help_action/a.htm", ALLOWED)
    assert not is_allowed_help_url("https://www.intacct.com/other/a.htm", ALLOWED)


def test_extracts_only_scoped_html_links() -> None:
    xhtml = """
    <html><body>
      <a href="../General_Ledger/topic.htm#section">GL</a>
      <a href="/other/topic.htm">Other path</a>
      <a href="https://example.com/topic.htm">Other host</a>
      <a href="manual.pdf">PDF</a>
    </body></html>
    """
    links = extract_scoped_links(
        xhtml,
        f"{ALLOWED}Intacct_basics/welcome.htm",
        ALLOWED,
    )
    assert links == [f"{ALLOWED}General_Ledger/topic.htm"]


def test_crawler_caches_pages_and_writes_manifest(tmp_path: Path) -> None:
    start = f"{ALLOWED}Intacct_basics/welcome.htm"
    child = f"{ALLOWED}General_Ledger/topic.htm"
    dead = f"{ALLOWED}General_Ledger/missing.htm"
    pages = {
        start: (
            "<html><body><h1>Welcome</h1>"
            '<a href="../General_Ledger/topic.htm">GL</a>'
            '<a href="../General_Ledger/missing.htm">Missing</a>'
            "</body></html>"
        ),
        child: "<html><body><h1>General Ledger</h1></body></html>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == dead:
            return httpx.Response(404, request=request)
        return httpx.Response(
            200,
            text=pages[url],
            headers={"content-type": "application/xhtml+xml", "etag": '"fixture"'},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    crawler = XhtmlCrawler(start, ALLOWED, tmp_path, delay_seconds=0, client=client)
    documents = crawler.crawl()

    assert [document.url for document in documents] == [start, child]
    assert crawler.errors == []
    assert crawler.skipped == [
        {"url": dead, "error_type": "HTTPStatusError", "status_code": 404}
    ]
    assert (tmp_path / "manifest.json").is_file()
    manifest = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert '"complete": true' in manifest
    assert all((tmp_path / document.cache_path).is_file() for document in documents)
