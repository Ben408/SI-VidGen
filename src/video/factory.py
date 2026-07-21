"""Select the video generation backend."""

from __future__ import annotations

from config.settings import Settings
from src.video.higgsfield_client import HiggsfieldClient, VideoGenerator
from src.video.local_compositor import LocalCompositorVideoGenerator


def create_video_generator(settings: Settings) -> VideoGenerator:
    backend = (settings.video_backend or "local_compositor").strip().lower()
    if backend in {"higgsfield", "hf", "gemini_omni"}:
        return HiggsfieldClient(
            api_key=settings.higgsfield_api_key,
            workspace_id=settings.higgsfield_workspace_id,
            job_type=settings.higgsfield_job_type,
        )
    return LocalCompositorVideoGenerator(
        jobs_dir=settings.data_dir / "compositor_jobs",
        enable_tts=settings.local_compositor_tts,
    )
