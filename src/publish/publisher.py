import shutil
from pathlib import Path


def publish_payload_locally(payload_path: Path, published_dir: Path) -> Path:
    published_dir.mkdir(parents=True, exist_ok=True)
    destination = published_dir / payload_path.name
    shutil.copy2(payload_path, destination)
    return destination
