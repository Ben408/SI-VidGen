import json
from pathlib import Path

from src.models import HiggsfieldPayload, Script


def build_higgsfield_payload(script: Script) -> HiggsfieldPayload:
    return HiggsfieldPayload(
        script=script.narration,
        scenes=script.scenes,
    )


def write_payload(payload: HiggsfieldPayload, run_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def read_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
