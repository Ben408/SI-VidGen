from src.models import Scene, Script
from src.video.payload_builder import build_higgsfield_payload, read_payload, write_payload


def test_builds_and_writes_payload(tmp_path) -> None:
    script = Script(
        title="Draft",
        narration="Narration",
        scenes=[Scene(action="Open", visual="Existing help asset", voiceover="Open it")],
    )

    payload = build_higgsfield_payload(script)
    path = write_payload(payload, "run-test", tmp_path)

    assert path.name == "run-test.json"
    assert read_payload(path)["script"] == "Narration"
    assert read_payload(path)["captions"] is True
