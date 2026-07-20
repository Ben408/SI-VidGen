import json
from pathlib import Path

from src.models import Script


def write_script(
    script: Script,
    run_id: str,
    output_dir: Path,
    version: int | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-v{version}" if version is not None else ""
    path = output_dir / f"{run_id}{suffix}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(script.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def read_script(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_script_model(path: Path) -> Script:
    return Script.model_validate_json(path.read_text(encoding="utf-8"))
