"""Locale asset binding rules for non-English videos."""

from src.models import RetrievedChunk
from src.rag.asset_binding import filter_assets_by_locale, filter_retrieved_to_library

EN = "https://www.intacct.com/ia/docs/en_US/help_action/a.png"
FR = "https://www.intacct.com/ia/docs/fr_FR/help_action/a.png"
DE = "https://www.intacct.com/ia/docs/de_DE/help_action/a.png"


def test_filter_assets_blocks_en_for_non_en_video() -> None:
    assert filter_assets_by_locale([EN, FR], video_locale="fr_FR") == [FR]
    assert filter_assets_by_locale([EN, FR], video_locale="en_US") == [EN, FR]
    assert filter_assets_by_locale([EN, DE], video_locale="de_DE") == [DE]


def test_filter_retrieved_applies_locale() -> None:
    chunk = RetrievedChunk(
        source_id="1",
        text="x",
        source_url="https://www.intacct.com/ia/docs/fr_FR/help_action/t.htm",
        title="t",
        heading_path="",
        score=0.9,
        asset_urls=[EN, FR],
    )
    out = filter_retrieved_to_library([chunk], None, video_locale="fr_FR")
    assert out[0].asset_urls == [FR]
