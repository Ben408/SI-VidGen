"""Ask Intacct answer sanitization: Help URLs only; no chunk ids / file names."""

from config.settings import Settings
from src.qa.ask_agent import is_allowed_help_url, scrub_ask_free_text, scrub_non_help_urls

_HELP_SETTINGS = Settings(
    help_start_url="https://termweb.atlassian.net/wiki/spaces/TWKB/overview",
    help_allowed_prefix="https://termweb.atlassian.net/wiki/spaces",
)


def test_allows_configured_help_url() -> None:
    url = "https://termweb.atlassian.net/wiki/spaces/TWKB/pages/123/email-domain"
    assert is_allowed_help_url(url, settings=_HELP_SETTINGS)
    assert scrub_non_help_urls(f"See {url}", settings=_HELP_SETTINGS) == f"See {url}"


def test_strips_third_party_url() -> None:
    text = (
        "Use an external tool (like https://mxtoolbox.com/SuperTool.aspx/) "
        "to validate DNS entries."
    )
    cleaned = scrub_non_help_urls(text, settings=_HELP_SETTINGS)
    assert "mxtoolbox" not in cleaned.lower()
    assert "https://" not in cleaned
    assert "validate DNS" in cleaned


def test_strips_markdown_non_help_keeps_label() -> None:
    cleaned = scrub_non_help_urls(
        "Check [MX Toolbox](https://mxtoolbox.com/foo) next.",
        settings=_HELP_SETTINGS,
    )
    assert "mxtoolbox" not in cleaned.lower()
    assert "MX Toolbox" in cleaned


def test_keeps_markdown_help_link() -> None:
    url = "https://termweb.atlassian.net/wiki/spaces/TWKB/pages/1/x"
    cleaned = scrub_non_help_urls(
        f"Open [Email domains]({url}).",
        settings=_HELP_SETTINGS,
    )
    assert url in cleaned
    assert "Email domains" in cleaned


def test_strips_source_id_hashes_from_notes() -> None:
    note = (
        "To use purchasing approvals, your company must be subscribed to Purchasing. "
        "[8a028f10f549fa7ae07dfa0379beb322bd61427530556fc8dab86223364275f1]"
    )
    cleaned = scrub_ask_free_text(note, settings=_HELP_SETTINGS)
    assert "8a028f10" not in cleaned
    assert "[" not in cleaned
    assert "subscribed to Purchasing" in cleaned


def test_strips_xhtml_filenames() -> None:
    cleaned = scrub_ask_free_text(
        "See purchasing-workflow-approvals.xhtml for details.",
        settings=_HELP_SETTINGS,
    )
    assert ".xhtml" not in cleaned.lower()
    assert "for details" in cleaned
