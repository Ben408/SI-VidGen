"""Local screenshot compositor — preserves Help PNG pixels (no generative restyle)."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import wave
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.models import HiggsfieldExplainerPackage, HiggsfieldPayload
from src.video.higgsfield_client import (
    plan_scene_clips,
)

FPS = 24
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
MIN_SCENE_SECONDS = 5.0
MAX_SCENE_SECONDS = 20.0
WORDS_PER_SECOND = 2.4
DEFAULT_NEURAL_VOICE = "en-US-JennyNeural"
DEFAULT_TTS_RATE = "-5%"

COMPOSITOR_VOICES: list[dict[str, str]] = [
    {"id": "en-US-JennyNeural", "label": "Jenny (US) — clear, professional"},
    {"id": "en-US-AriaNeural", "label": "Aria (US) — warm"},
    {"id": "en-US-AndrewNeural", "label": "Andrew (US) — conversational"},
    {"id": "en-US-GuyNeural", "label": "Guy (US) — steady"},
    {"id": "en-GB-SoniaNeural", "label": "Sonia (UK)"},
    {"id": "fr-FR-DeniseNeural", "label": "Denise (FR)"},
    {"id": "fr-FR-HenriNeural", "label": "Henri (FR)"},
    {"id": "de-DE-KatjaNeural", "label": "Katja (DE)"},
    {"id": "de-DE-ConradNeural", "label": "Conrad (DE)"},
    {"id": "es-ES-ElviraNeural", "label": "Elvira (ES)"},
    {"id": "es-ES-AlvaroNeural", "label": "Alvaro (ES)"},
]

COMPOSITOR_RATES: list[dict[str, str]] = [
    {"id": "-20%", "label": "Slower (−20%)"},
    {"id": "-10%", "label": "Slightly slow (−10%)"},
    {"id": "-5%", "label": "Default (−5%)"},
    {"id": "+0%", "label": "Natural (+0%)"},
    {"id": "+10%", "label": "Faster (+10%)"},
]


def compositor_capability_defaults(
    *,
    voice: str = DEFAULT_NEURAL_VOICE,
    rate: str = DEFAULT_TTS_RATE,
    captions: bool = True,
) -> dict[str, object]:
    return {
        "voices": COMPOSITOR_VOICES,
        "rates": COMPOSITOR_RATES,
        "defaults": {
            "voice": voice or DEFAULT_NEURAL_VOICE,
            "rate": rate or DEFAULT_TTS_RATE,
            "captions": captions,
        },
    }


class LocalCompositorVideoGenerator:
    """Ken Burns + optional TTS over real Help screenshots."""

    def __init__(
        self,
        *,
        jobs_dir: Path,
        work_dir: Path | None = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fps: int = FPS,
        enable_tts: bool = True,
        tts_voice: str = DEFAULT_NEURAL_VOICE,
        tts_rate: str = DEFAULT_TTS_RATE,
        enable_captions: bool = True,
    ) -> None:
        self._jobs_dir = Path(jobs_dir)
        self._work_dir = Path(work_dir) if work_dir else self._jobs_dir / "work"
        self._width = width
        self._height = height
        self._fps = fps
        self._enable_tts = enable_tts
        self._tts_voice = tts_voice or DEFAULT_NEURAL_VOICE
        self._tts_rate = tts_rate or DEFAULT_TTS_RATE
        self._enable_captions = enable_captions
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._configured_cache: bool | None = None

    @property
    def configured(self) -> bool:
        if self._configured_cache is not None:
            return self._configured_cache
        try:
            import imageio_ffmpeg  # noqa: F401
            from PIL import Image  # noqa: F401

            self._configured_cache = True
        except ImportError:
            self._configured_cache = False
        return self._configured_cache

    def generate(self, payload: HiggsfieldPayload) -> dict[str, object]:
        if not self.configured:
            raise RuntimeError(
                "Local compositor unavailable — install pillow, imageio, imageio-ffmpeg"
            )
        package = self._load_package(payload)
        plans = plan_scene_clips(package, payload, model="local_compositor")
        scenes_spec: list[dict[str, Any]] = []
        if plans:
            for plan in plans:
                if not plan.images:
                    raise RuntimeError(
                        f"Scene {plan.index}/{plan.total} has no Help screenshot"
                    )
                scenes_spec.append(
                    {
                        "index": plan.index,
                        "voiceover": plan.scene.voiceover,
                        "image": str(plan.images[0].resolve()),
                        "action": plan.scene.action,
                    }
                )
        else:
            medias = [
                str(Path(item).resolve())
                for item in (package.medias if package else payload.medias)
                if Path(item).is_file()
            ]
            if not medias:
                raise RuntimeError("No local Help screenshots available to compose")
            scenes_spec.append(
                {
                    "index": 1,
                    "voiceover": payload.script or "Sage Intacct support walkthrough.",
                    "image": medias[0],
                    "action": "Overview",
                }
            )

        job_id = str(uuid4())
        aspect = package.aspect_ratio if package else "16:9"
        job = {
            "job_id": job_id,
            "aspect_ratio": aspect,
            "width": self._width if aspect == "16:9" else self._height,
            "height": self._height if aspect == "16:9" else self._width,
            "scenes": scenes_spec,
            "title": _package_title(package) or "SI VidGen local compose",
            "tts_voice": payload.tts_voice or self._tts_voice,
            "tts_rate": payload.tts_rate or self._tts_rate,
            "captions": (
                payload.captions if payload.captions is not None else self._enable_captions
            ),
            "enable_tts": self._enable_tts,
        }
        path = self._jobs_dir / f"{job_id}.json"
        path.write_text(json.dumps(job, indent=2), encoding="utf-8")
        return {
            "id": job_id,
            "generation_id": job_id,
            "generation_job_ids": [job_id],
            "job_type": "local_compositor",
            "transport": "local",
            "mode": "scene_chunked" if len(scenes_spec) > 1 else "single",
            "aspect_ratio": aspect,
            "scene_count": len(scenes_spec),
        }

    def wait_for_result(
        self,
        generation_id: str,
        *,
        timeout_seconds: int = 600,
        scene_job_ids: list[str] | None = None,
        aspect_ratio: str = "16:9",
    ) -> dict[str, object]:
        del timeout_seconds, scene_job_ids, aspect_ratio  # plan is on disk
        job_path = self._jobs_dir / f"{generation_id}.json"
        if not job_path.is_file():
            raise FileNotFoundError(f"Compositor job not found: {generation_id}")
        job = json.loads(job_path.read_text(encoding="utf-8"))
        output = self._render_job(job)
        return {
            "id": generation_id,
            "result_url": output.resolve().as_uri(),
            "local_path": str(output.resolve()),
            "scene_job_ids": [generation_id],
            "mode": "local_compositor",
        }

    def download_video(self, source_url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = _resolve_local_source(source_url)
        if source is not None:
            if source.resolve() == destination.resolve():
                return destination
            shutil.copy2(source, destination)
            return destination
        raise RuntimeError(f"Local compositor expected a local file, got: {source_url}")

    def _render_job(self, job: dict[str, Any]) -> Path:
        from PIL import Image

        job_id = str(job["job_id"])
        width = int(job["width"])
        height = int(job["height"])
        enable_tts = bool(job.get("enable_tts", self._enable_tts))
        tts_voice = str(job.get("tts_voice") or self._tts_voice)
        tts_rate = str(job.get("tts_rate") or self._tts_rate)
        captions = bool(job.get("captions", self._enable_captions))
        work = self._work_dir / job_id
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)

        clip_paths: list[Path] = []
        for scene in job["scenes"]:
            image_path = Path(scene["image"])
            image = Image.open(image_path).convert("RGB")
            voiceover = str(scene.get("voiceover") or "")
            duration = _scene_duration_seconds(voiceover)
            audio_path: Path | None = None
            if enable_tts and voiceover.strip():
                audio_path = _synthesize_speech(
                    voiceover,
                    work / f"scene-{scene['index']:02d}",
                    voice=tts_voice,
                    rate=tts_rate,
                )
                if audio_path is not None:
                    duration = max(duration, _audio_duration_seconds(audio_path) + 0.35)

            frames_path = work / f"scene-{scene['index']:02d}.mp4"
            _write_ken_burns_clip(
                image=image,
                destination=frames_path,
                width=width,
                height=height,
                fps=self._fps,
                duration_seconds=duration,
                caption=voiceover if captions else None,
            )
            if audio_path is not None:
                muxed = work / f"scene-{scene['index']:02d}-muxed.mp4"
                _mux_audio(frames_path, audio_path, muxed)
                clip_paths.append(muxed)
            else:
                clip_paths.append(frames_path)

        output = work / "final.mp4"
        if len(clip_paths) == 1:
            shutil.copy2(clip_paths[0], output)
        else:
            _concat_clips(clip_paths, output)
        return output

    def _load_package(
        self, payload: HiggsfieldPayload
    ) -> HiggsfieldExplainerPackage | None:
        if not payload.explainer_package_path:
            return None
        path = Path(payload.explainer_package_path)
        if not path.is_file():
            return None
        return HiggsfieldExplainerPackage.model_validate_json(
            path.read_text(encoding="utf-8")
        )


def _package_title(package: HiggsfieldExplainerPackage | None) -> str | None:
    if package is None or not package.prompt:
        return None
    first = package.prompt.strip().splitlines()[0].strip()
    return first or None


def _scene_duration_seconds(voiceover: str) -> float:
    words = max(1, len(voiceover.split()))
    seconds = words / WORDS_PER_SECOND
    return max(MIN_SCENE_SECONDS, min(MAX_SCENE_SECONDS, seconds))


def _resolve_local_source(source_url: str) -> Path | None:
    if source_url.startswith("file:"):
        from urllib.parse import urlparse
        from urllib.request import url2pathname

        parsed = urlparse(source_url)
        path = Path(url2pathname(parsed.path))
        if path.is_file():
            return path
        return None
    path = Path(source_url)
    return path if path.is_file() else None


def _write_ken_burns_clip(
    *,
    image,
    destination: Path,
    width: int,
    height: int,
    fps: int,
    duration_seconds: float,
    caption: str | None = None,
) -> None:
    import imageio.v3 as iio
    import numpy as np
    from PIL import Image

    frame_count = max(fps, int(round(duration_seconds * fps)))
    src = _fit_cover(image, width, height)
    src_w, src_h = src.size
    # Zoom slowly into the upper-left-ish focal area (typical UI chrome).
    start_zoom = 1.0
    end_zoom = 1.12
    caption_overlay = None
    if caption and caption.strip():
        caption_overlay = _build_caption_overlay(width, height, caption.strip())
    frames = []
    for index in range(frame_count):
        t = index / max(1, frame_count - 1)
        zoom = start_zoom + (end_zoom - start_zoom) * t
        crop_w = src_w / zoom
        crop_h = src_h / zoom
        # Ease pan toward top-left content.
        max_x = src_w - crop_w
        max_y = src_h - crop_h
        x = max_x * (0.08 * t)
        y = max_y * (0.12 * t)
        box = (int(x), int(y), int(x + crop_w), int(y + crop_h))
        frame = src.crop(box).resize((width, height), Image.Resampling.LANCZOS)
        if caption_overlay is not None:
            frame = frame.copy()
            frame.paste(caption_overlay, (0, 0), caption_overlay)
        frames.append(np.asarray(frame))

    destination.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(
        destination,
        frames,
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
    )


def _build_caption_overlay(width: int, height: int, text: str):
    """Semi-transparent bottom bar with wrapped narration (RGBA)."""
    from PIL import Image, ImageDraw

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(22, min(34, width // 42))
    font = _load_caption_font(font_size)
    max_chars = max(28, width // max(10, font_size // 2))
    lines = textwrap.wrap(text, width=max_chars)[:4]
    if not lines:
        return overlay

    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])
    padding_x = 28
    padding_y = 16
    gap = max(4, font_size // 6)
    text_block_h = sum(line_heights) + gap * (len(lines) - 1)
    bar_h = text_block_h + padding_y * 2
    bar_top = height - bar_h - 24
    draw.rectangle(
        (0, bar_top, width, height),
        fill=(12, 18, 28, 168),
    )
    y = bar_top + padding_y
    for line, line_w, line_h in zip(lines, line_widths, line_heights, strict=True):
        x = max(padding_x, (width - line_w) // 2)
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 245))
        y += line_h + gap
    return overlay


def _load_caption_font(size: int):
    from PIL import ImageFont

    candidates = [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit_cover(image, width: int, height: int):
    """Scale image to cover target aspect, center-crop."""
    from PIL import Image

    src_w, src_h = image.size
    target_ratio = width / height
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_h = height
        new_w = int(round(height * src_ratio))
    else:
        new_w = width
        new_h = int(round(width / src_ratio))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - width) // 2)
    top = max(0, (new_h - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _synthesize_speech(
    text: str,
    destination_stem: Path,
    *,
    voice: str = DEFAULT_NEURAL_VOICE,
    rate: str = DEFAULT_TTS_RATE,
) -> Path | None:
    """Prefer Edge neural TTS (mp3); fall back to Windows SAPI/pyttsx3 (wav)."""
    destination_stem.parent.mkdir(parents=True, exist_ok=True)
    mp3_path = destination_stem.with_suffix(".mp3")
    if _synthesize_speech_edge(text, mp3_path, voice=voice, rate=rate):
        return mp3_path
    wav_path = destination_stem.with_suffix(".wav")
    if _synthesize_speech_pyttsx3(text, wav_path):
        return wav_path
    if _synthesize_speech_powershell(text, wav_path):
        return wav_path
    return None


def _synthesize_speech_edge(
    text: str,
    destination: Path,
    *,
    voice: str,
    rate: str,
) -> bool:
    try:
        import asyncio

        import edge_tts
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        return False

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicate.save(str(destination))

    try:
        asyncio.run(_run())
        return destination.is_file() and destination.stat().st_size > 500
    except Exception:
        return False


def _synthesize_speech_pyttsx3(text: str, destination: Path) -> bool:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.save_to_file(text, str(destination))
        engine.runAndWait()
        return destination.is_file() and destination.stat().st_size > 44
    except Exception:
        return False


def _synthesize_speech_powershell(text: str, destination: Path) -> bool:
    """Fallback Windows SAPI TTS via PowerShell."""
    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$speak.SetOutputToWaveFile('{destination}'); "
        f"$speak.Speak('{safe}'); "
        "$speak.Dispose();"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return completed.returncode == 0 and destination.is_file()
    except (OSError, subprocess.SubprocessError):
        return False


def _audio_duration_seconds(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        return _wav_duration_seconds(path)
    import re

    completed = subprocess.run(
        [_ffmpeg(), "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        completed.stderr or "",
    )
    if not match:
        return MIN_SCENE_SECONDS
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
        return frames / float(rate)


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _mux_audio(video_path: Path, audio_path: Path, destination: Path) -> None:
    cmd = [
        _ffmpeg(),
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(destination),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0 or not destination.is_file():
        raise RuntimeError(
            f"ffmpeg mux failed: {completed.stderr[-500:] or completed.stdout[-500:]}"
        )


def _concat_clips(clips: list[Path], destination: Path) -> None:
    list_file = destination.with_suffix(".concat.txt")
    lines = []
    for clip in clips:
        # ffmpeg concat demuxer needs escaped single quotes
        escaped = str(clip.resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        _ffmpeg(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(destination),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0 or not destination.is_file():
        # Re-encode fallback when codecs differ
        cmd = [
            _ffmpeg(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(destination),
        ]
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0 or not destination.is_file():
            raise RuntimeError(
                f"ffmpeg concat failed: {completed.stderr[-500:] or completed.stdout[-500:]}"
            )
