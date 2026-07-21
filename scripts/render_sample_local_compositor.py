"""Render sample_query run with the local compositor backend."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from config.settings import Settings
from src.models import Script
from src.rag.image_library import HelpImageLibrary
from src.video.local_compositor import LocalCompositorVideoGenerator
from src.video.payload_builder import build_higgsfield_payload

RUN_ID = "run-1906fa1a-98e5-4fa2-b97b-b92821498769"


def main() -> None:
    script_path = Path(f"output/scripts/{RUN_ID}-v1.json")
    explainer_path = Path(f"output/payloads/{RUN_ID}-v1-explainer.json")
    script = Script.model_validate_json(script_path.read_text(encoding="utf-8"))

    settings = Settings()
    settings.ensure_runtime_directories()
    library = None
    catalog = settings.help_assets_dir / "catalog.json"
    if catalog.is_file():
        library = HelpImageLibrary(settings.help_assets_dir)

    payload = build_higgsfield_payload(script, library, visual_coverage="green")
    payload = payload.model_copy(
        update={"explainer_package_path": str(explainer_path.resolve())}
    )

    gen = LocalCompositorVideoGenerator(
        jobs_dir=settings.data_dir / "compositor_jobs",
        enable_tts=True,
    )
    print("configured", gen.configured)
    print("scenes", len(payload.scenes), "medias", len(payload.medias))
    submitted = gen.generate(payload)
    print(
        "submitted",
        {
            k: submitted[k]
            for k in ("id", "mode", "scene_count", "job_type")
            if k in submitted
        },
    )
    waited = gen.wait_for_result(str(submitted["generation_id"]))
    local = Path(str(waited["local_path"]))
    print("local", local, "size", local.stat().st_size)

    dest = settings.videos_dir / f"{RUN_ID}-local-compositor.mp4"
    demo = settings.videos_dir / "demo-sample-query-local-compositor.mp4"
    # Also standard run path used by UI download endpoint
    ui_path = settings.videos_dir / f"{RUN_ID}.mp4"
    for target in (dest, demo, ui_path):
        shutil.copy2(local, target)
        print("wrote", target)

    run_file = Path(f"data/runs/{RUN_ID}.json")
    data = json.loads(run_file.read_text(encoding="utf-8"))
    result = data["result"]
    result["review_status"] = "approved"
    result["generation_status"] = "ready"
    result["generation_id"] = submitted["generation_id"]
    result["generation_job_ids"] = submitted.get("generation_job_ids")
    result["video_path"] = str(ui_path.resolve())
    result["video_url"] = None
    result["error_code"] = None
    result["error_detail"] = None
    run_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("updated", run_file)


if __name__ == "__main__":
    main()
