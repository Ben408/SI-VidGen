"""Higgsfield generation via MCP using the local CLI OAuth token."""

from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from src.models import HiggsfieldExplainerPackage, HiggsfieldPayload, Scene

MCP_URL = "https://mcp.higgsfield.ai/mcp"
DEFAULT_MODEL = "gemini_omni"
MAX_IMAGE_REFERENCES = 7
DEFAULT_DURATION_SECONDS = 8
# Per-scene clip length before model clamping (gemini_omni max is 10).
SCENE_CLIP_SECONDS = 8
MCP_TRIAL_HELP = (
    "Higgsfield blocked generation for this login "
    "(only_mcp_usage_on_trial_is_available). "
    "CLI/`higgsfield auth` tokens can upload and price jobs, but this account "
    "only allows real generation through Higgsfield's official MCP connector "
    "OAuth (for example Claude Connectors), or after API/CLI access is "
    "unlocked on the plan. See https://higgsfield.ai/mcp-credits"
)


class VideoGenerator(Protocol):
    @property
    def configured(self) -> bool: ...

    def generate(self, payload: HiggsfieldPayload) -> dict[str, object]: ...

    def wait_for_result(
        self,
        generation_id: str,
        *,
        timeout_seconds: int = 600,
        scene_job_ids: list[str] | None = None,
        aspect_ratio: str = "16:9",
    ) -> dict[str, object]: ...

    def download_video(self, source_url: str, destination: Path) -> Path: ...


@dataclass(frozen=True)
class SceneClipPlan:
    index: int
    total: int
    scene: Scene
    prompt: str
    images: list[Path]


class HiggsfieldClient:
    """Submit/wait/download through Higgsfield MCP using `higgsfield auth` token."""

    def __init__(
        self,
        *,
        api_key: str = "",
        workspace_id: str = "",
        job_type: str = DEFAULT_MODEL,
        cli_path: str | None = None,
        timeout_seconds: float = 120,
        mcp_url: str = MCP_URL,
    ) -> None:
        self._api_key = api_key
        self._workspace_id = workspace_id
        self._job_type = job_type or DEFAULT_MODEL
        self._cli_path = cli_path or shutil.which("higgsfield") or "higgsfield"
        self._timeout_seconds = timeout_seconds
        self._mcp_url = mcp_url
        self._configured_cache: bool | None = None

    @property
    def configured(self) -> bool:
        if self._configured_cache is not None:
            return self._configured_cache
        try:
            token = self._auth_token()
            self._configured_cache = bool(token)
        except (OSError, subprocess.CalledProcessError, RuntimeError):
            self._configured_cache = False
        return self._configured_cache

    def generate(self, payload: HiggsfieldPayload) -> dict[str, object]:
        package = self._load_package(payload)
        aspect = package.aspect_ratio if package else "16:9"
        role = _media_role_for_model(self._job_type)
        plans = plan_scene_clips(package, payload, model=self._job_type)
        client = self._session()

        if len(plans) >= 2:
            job_ids: list[str] = []
            uploaded: dict[str, str] = {}
            for plan in plans:
                if not plan.images:
                    raise RuntimeError(
                        f"Scene {plan.index}/{plan.total} has no Help screenshot to send"
                    )
                media_ids = [
                    _upload_cached(client, path, uploaded) for path in plan.images
                ]
                duration = _clip_duration(SCENE_CLIP_SECONDS, model=self._job_type)
                result = client.call_tool(
                    "generate_video",
                    {
                        "params": {
                            "model": self._job_type,
                            "prompt": plan.prompt,
                            "aspect_ratio": aspect,
                            "duration": duration,
                            "medias": [
                                {"value": media_id, "role": role}
                                for media_id in media_ids
                            ],
                        }
                    },
                )
                _raise_if_tool_error(result)
                generation_id = _extract_generation_id(result, exclude=set(media_ids))
                if not generation_id:
                    raise RuntimeError(
                        f"Higgsfield MCP create returned no job id for scene "
                        f"{plan.index}: {result}"
                    )
                job_ids.append(generation_id)
            return {
                "id": job_ids[0],
                "generation_id": job_ids[0],
                "generation_job_ids": job_ids,
                "job_type": self._job_type,
                "transport": "mcp",
                "mode": "scene_chunked",
                "aspect_ratio": aspect,
                "scene_count": len(job_ids),
            }

        # Single-clip path (one scene or medias-only fallback).
        prompt = (
            plans[0].prompt
            if plans
            else _build_prompt(package, payload)
        )
        images = plans[0].images if plans else _select_images(
            package, payload, model=self._job_type
        )
        if not images:
            raise RuntimeError("No local Help screenshots available to send to Higgsfield")
        duration = _clip_duration(
            SCENE_CLIP_SECONDS if plans else (
                package.duration if package else DEFAULT_DURATION_SECONDS
            ),
            model=self._job_type,
        )
        media_ids = [client.upload_image(path) for path in images]
        result = client.call_tool(
            "generate_video",
            {
                "params": {
                    "model": self._job_type,
                    "prompt": prompt,
                    "aspect_ratio": aspect,
                    "duration": duration,
                    "medias": [
                        {"value": media_id, "role": role} for media_id in media_ids
                    ],
                }
            },
        )
        _raise_if_tool_error(result)
        generation_id = _extract_generation_id(result, exclude=set(media_ids))
        if not generation_id:
            raise RuntimeError(f"Higgsfield MCP create returned no job id: {result}")
        return {
            "id": generation_id,
            "generation_id": generation_id,
            "generation_job_ids": [generation_id],
            "job_type": self._job_type,
            "transport": "mcp",
            "mode": "single",
            "aspect_ratio": aspect,
            "scene_count": 1,
            "raw": result,
        }

    def wait_for_result(
        self,
        generation_id: str,
        *,
        timeout_seconds: int = 600,
        scene_job_ids: list[str] | None = None,
        aspect_ratio: str = "16:9",
    ) -> dict[str, object]:
        job_ids = [item for item in (scene_job_ids or []) if item]
        if not job_ids:
            job_ids = [generation_id]
        client = self._session()
        clip_urls: list[str] = []
        for job_id in job_ids:
            waited = self._wait_one_job(
                client, job_id, timeout_seconds=timeout_seconds
            )
            url = waited.get("result_url")
            if isinstance(url, str):
                clip_urls.append(url)

        if len(job_ids) == 1:
            return {
                "id": job_ids[0],
                "result_url": clip_urls[0] if clip_urls else None,
                "scene_job_ids": job_ids,
                "mode": "single",
            }

        stitch = client.call_tool(
            "explainer_video",
            {
                "params": {
                    "width": 1280 if aspect_ratio == "16:9" else 720,
                    "height": 720 if aspect_ratio == "16:9" else 1280,
                    "items": [{"video": job_id} for job_id in job_ids],
                }
            },
        )
        _raise_if_tool_error(stitch)
        stitch_id = _extract_generation_id(stitch, exclude=set(job_ids))
        if not stitch_id:
            raise RuntimeError(f"explainer_video returned no assembly job id: {stitch}")
        assembled = self._wait_one_job(
            client, stitch_id, timeout_seconds=timeout_seconds
        )
        return {
            "id": stitch_id,
            "result_url": assembled.get("result_url"),
            "scene_job_ids": job_ids,
            "mode": "scene_chunked",
            "raw": assembled.get("raw"),
        }

    def download_video(self, source_url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", source_url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            with temporary.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
            temporary.replace(destination)
        return destination

    def _wait_one_job(
        self,
        client: _McpSession,
        generation_id: str,
        *,
        timeout_seconds: int,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        last: dict[str, object] = {}
        while time.monotonic() < deadline:
            last = client.call_tool(
                "job_status",
                {"jobId": generation_id, "sync": True},
            )
            _raise_if_tool_error(last)
            status = _extract_job_status(last)
            url = _extract_result_url(last)
            if url and status in {"completed", "complete", "succeeded", "success", "ready"}:
                return {"id": generation_id, "result_url": url, "raw": last}
            if status in {
                "failed",
                "error",
                "nsfw",
                "cancelled",
                "canceled",
                "ip_detected",
            }:
                raise RuntimeError(
                    f"Higgsfield job {generation_id} ended as {status}: "
                    f"{_tool_error_text(last)}"
                )
            if url and status is None:
                return {"id": generation_id, "result_url": url, "raw": last}
            time.sleep(5)
        raise TimeoutError(
            f"Timed out waiting for Higgsfield job {generation_id}. Last payload: {last}"
        )

    def _session(self) -> _McpSession:
        client = _McpSession(self._auth_token(), self._mcp_url, self._timeout_seconds)
        client.initialize()
        if self._workspace_id:
            select = client.call_tool(
                "select_workspace",
                {"workspace_id": self._workspace_id},
            )
            _raise_if_tool_error(select)
        return client

    def _auth_token(self) -> str:
        if self._api_key:
            return self._api_key
        completed = subprocess.run(
            [self._cli_path, "auth", "token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        token = (completed.stdout or "").strip()
        if not token:
            raise RuntimeError(
                "higgsfield auth token returned empty; run higgsfield auth login"
            )
        return token

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


class _McpSession:
    def __init__(self, token: str, url: str, timeout_seconds: float) -> None:
        self._token = token
        self._url = url
        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def initialize(self) -> None:
        self.rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "si-vidgen", "version": "0.1.0"},
            },
        )
        httpx.post(
            self._url,
            headers=self._headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=self._timeout,
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, object]:
        return self.rpc("tools/call", {"name": name, "arguments": arguments})

    def upload_image(self, path: Path) -> str:
        content_type = mimetypes.guess_type(path.name)[0] or "image/png"
        upload = self.call_tool(
            "media_upload",
            {
                "method": "upload_url",
                "filename": path.name,
                "content_type": content_type,
            },
        )
        _raise_if_tool_error(upload)
        media_id, upload_url = _extract_upload(upload)
        put = httpx.put(
            upload_url,
            content=path.read_bytes(),
            headers={"Content-Type": content_type},
            timeout=120,
        )
        put.raise_for_status()
        confirm = self.call_tool(
            "media_confirm", {"type": "image", "media_id": media_id}
        )
        _raise_if_tool_error(confirm)
        return media_id

    def rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, object]:
        response = httpx.post(
            self._url,
            headers=self._headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params or {},
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = _parse_mcp_response(response.text)
        if "error" in payload:
            raise RuntimeError(f"MCP {method} error: {payload['error']}")
        return payload


def plan_scene_clips(
    package: HiggsfieldExplainerPackage | None,
    payload: HiggsfieldPayload,
    *,
    model: str = DEFAULT_MODEL,
) -> list[SceneClipPlan]:
    """Build one clip plan per script scene when multiple scenes exist."""
    scenes = list(payload.scenes or [])
    if len(scenes) < 2:
        if len(scenes) == 1:
            scene = scenes[0]
            images = images_for_scene(package, payload, scene, index=0, model=model)
            if not images:
                images = _select_images(package, payload, model=model)
            return [
                SceneClipPlan(
                    index=1,
                    total=1,
                    scene=scene,
                    prompt=build_scene_prompt(package, payload, scene, 1, 1),
                    images=images,
                )
            ]
        return []

    total = len(scenes)
    plans: list[SceneClipPlan] = []
    for index, scene in enumerate(scenes):
        images = images_for_scene(package, payload, scene, index=index, model=model)
        if not images:
            # Keep generation moving: borrow shared package/payload medias.
            shared = _select_images(package, payload, model=model)
            if shared:
                images = [shared[min(index, len(shared) - 1)]]
        plans.append(
            SceneClipPlan(
                index=index + 1,
                total=total,
                scene=scene,
                prompt=build_scene_prompt(package, payload, scene, index + 1, total),
                images=images,
            )
        )
    return plans


def build_scene_prompt(
    package: HiggsfieldExplainerPackage | None,
    payload: HiggsfieldPayload,
    scene: Scene,
    index: int,
    total: int,
) -> str:
    instruction = (
        package.instruction
        if package
        else (
            "Use attached Sage Intacct Help screenshots as authoritative UI. "
            "Do not restyle."
        )
    )
    title = _package_title(package) or "Sage Intacct support video"
    asset = scene.help_asset or "use the attached Help screenshot"
    prompt = (
        f"{instruction}\n\n"
        f"Instructional clip {index} of {total} for: {title}\n\n"
        f"Action: {scene.action}\n"
        f"Visual: {scene.visual}\n"
        f"Voiceover (speak this clearly): {scene.voiceover}\n"
        f"Help asset: {asset}\n\n"
        "Keep product UI faithful to the attached screenshot. "
        "Do not invent alternate Intacct screens."
    )
    return prompt[:4_500]


def images_for_scene(
    package: HiggsfieldExplainerPackage | None,
    payload: HiggsfieldPayload,
    scene: Scene,
    *,
    index: int,
    model: str,
) -> list[Path]:
    role = _media_role_for_model(model)
    limit = 1 if role == "start_image" else min(2, MAX_IMAGE_REFERENCES)
    paths: list[Path] = []

    if scene.help_asset and package:
        for asset in package.assets:
            if not isinstance(asset, dict):
                continue
            if asset.get("source_url") != scene.help_asset:
                continue
            local = asset.get("local_path")
            if isinstance(local, str):
                path = Path(local)
                if path.is_file():
                    paths.append(path)
            break

    if not paths and scene.help_asset:
        # Payload medias are local paths; match by filename stem from Help URL.
        needle = Path(urlparse(scene.help_asset).path).stem.lower()
        for item in payload.medias:
            path = Path(item)
            if path.is_file() and needle and needle in path.stem.lower():
                paths.append(path)
                break

    if not paths:
        candidates = list(package.medias if package else payload.medias)
        if candidates:
            choice = candidates[min(index, len(candidates) - 1)]
            path = Path(choice)
            if path.is_file():
                paths.append(path)

    deduped: list[Path] = []
    for path in paths:
        if path not in deduped:
            deduped.append(path)
        if len(deduped) >= limit:
            break
    return deduped


def _upload_cached(
    client: _McpSession, path: Path, cache: dict[str, str]
) -> str:
    key = str(path.resolve())
    cached = cache.get(key)
    if cached:
        return cached
    media_id = client.upload_image(path)
    cache[key] = media_id
    return media_id


def _package_title(package: HiggsfieldExplainerPackage | None) -> str | None:
    if package is None or not package.prompt:
        return None
    first = package.prompt.strip().splitlines()[0].strip()
    return first or None


def _parse_mcp_response(text: str) -> dict[str, object]:
    # Prefer the last SSE data payload; earlier events can be progress-only.
    last: dict[str, object] | None = None
    if "data: " in text:
        for line in text.splitlines():
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if isinstance(payload, dict):
                    last = payload
        if last is not None:
            return last
    payload = json.loads(text)
    if isinstance(payload, dict):
        return payload
    raise RuntimeError(f"Unexpected MCP response type: {type(payload)}")


def _tool_is_error(payload: dict[str, object]) -> bool:
    result = payload.get("result")
    if not isinstance(result, dict):
        return False
    if result.get("isError"):
        return True
    structured = result.get("structuredContent")
    return bool(isinstance(structured, dict) and structured.get("error"))


def _tool_error_text(payload: dict[str, object]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return _humanize_error(first["text"])
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and isinstance(structured.get("error"), str):
            return _humanize_error(structured["error"])
    return _humanize_error(json.dumps(payload)[:800])


def _raise_if_tool_error(payload: dict[str, object]) -> None:
    if _tool_is_error(payload):
        raise RuntimeError(_tool_error_text(payload))


def _humanize_error(message: str) -> str:
    if "only_mcp_usage_on_trial_is_available" in message:
        return MCP_TRIAL_HELP
    return message.strip()


def _extract_upload(payload: dict[str, object]) -> tuple[str, str]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"media_upload missing result: {payload}")
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        uploads = structured.get("uploads")
        if isinstance(uploads, list) and uploads and isinstance(uploads[0], dict):
            item = uploads[0]
            upload_url = item.get("upload_url")
            media_id = item.get("media_id")
            if isinstance(upload_url, str):
                if not isinstance(media_id, str) or not media_id:
                    media_id = Path(urlparse(upload_url).path).stem
                return media_id, upload_url
    raise RuntimeError(f"Could not parse media_upload response: {payload}")


def _build_prompt(
    package: HiggsfieldExplainerPackage | None, payload: HiggsfieldPayload
) -> str:
    base = package.prompt if package else payload.script
    instruction = (
        package.instruction
        if package
        else "Use attached Sage Intacct Help screenshots as authoritative UI. Do not restyle."
    )
    prompt = f"{instruction}\n\n{base}".strip()
    return prompt[:4_500]


def _media_role_for_model(model: str) -> str:
    name = (model or "").lower()
    if name.startswith("kling") or name.startswith("cinematic"):
        return "start_image"
    if "seedance" in name or name in {"gemini_omni"}:
        return "image_references"
    return "image_references"


def _select_images(
    package: HiggsfieldExplainerPackage | None,
    payload: HiggsfieldPayload,
    *,
    model: str,
) -> list[Path]:
    role = _media_role_for_model(model)
    limit = 1 if role == "start_image" else MAX_IMAGE_REFERENCES
    candidates = list(package.medias if package else payload.medias)
    paths: list[Path] = []
    for item in candidates:
        path = Path(item)
        if path.is_file() and path not in paths:
            paths.append(path)
        if len(paths) >= limit:
            break
    return paths


def _clip_duration(seconds: int, *, model: str = DEFAULT_MODEL) -> int:
    value = int(seconds or DEFAULT_DURATION_SECONDS)
    name = (model or "").lower()
    if name.startswith("kling"):
        return max(3, min(8, value if value >= 3 else 5))
    if "seedance" in name:
        return max(4, min(8, value if value >= 4 else 5))
    # gemini_omni: 4-10 seconds per clip
    return max(4, min(10, value if value >= 4 else DEFAULT_DURATION_SECONDS))


def _extract_generation_id(
    payload: dict[str, object], *, exclude: set[str] | None = None
) -> str | None:
    exclude = exclude or set()
    preferred = _find_first_string(
        payload,
        keys=("jobId", "job_id", "generation_id"),
    )
    if preferred and preferred not in exclude and _looks_like_uuid(preferred):
        return preferred

    generation = _find_generation_object(payload)
    if generation:
        for key in ("id", "jobId", "job_id"):
            value = generation.get(key)
            if (
                isinstance(value, str)
                and value not in exclude
                and _looks_like_uuid(value)
            ):
                return value

    # Last resort: first UUID that is not a request_id / media id.
    for value in _walk_strings(payload):
        if value in exclude or not _looks_like_uuid(value):
            continue
        if _string_is_request_id_context(payload, value):
            continue
        return value
    return None


def _find_generation_object(payload: object) -> dict[str, object] | None:
    if isinstance(payload, dict):
        generation = payload.get("generation")
        if isinstance(generation, dict):
            return generation
        for value in payload.values():
            found = _find_generation_object(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_generation_object(item)
            if found:
                return found
    return None


def _string_is_request_id_context(payload: object, value: str) -> bool:
    """True when `value` only appears as a support request_id, not a job id."""
    if isinstance(payload, dict):
        for key, item in payload.items():
            if item == value and key in {"request_id", "requestId"}:
                return True
            if _string_is_request_id_context(item, value):
                return True
    elif isinstance(payload, list):
        for item in payload:
            if _string_is_request_id_context(item, value):
                return True
    return False


def _extract_job_status(payload: dict[str, object]) -> str | None:
    generation = _find_generation_object(payload)
    if generation:
        status = generation.get("status")
        if isinstance(status, str) and status.strip():
            return status.lower()
    for key in ("status", "state", "job_status"):
        value = _find_first_string(payload, keys=(key,))
        if value:
            return value.lower()
    return None


def _extract_result_url(payload: dict[str, object]) -> str | None:
    generation = _find_generation_object(payload)
    if generation:
        results = generation.get("results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    for key in ("url", "video_url", "download_url"):
                        value = item.get(key)
                        if isinstance(value, str) and value.startswith("http"):
                            return value
    for key in ("result_url", "url", "video_url", "output_url", "download_url"):
        value = _find_first_string(payload, keys=(key,))
        if value and value.startswith("http"):
            return value
    for value in _walk_strings(payload):
        if value.startswith("http") and _looks_like_media_url(value):
            return value
    return None


def _find_first_string(payload: object, *, keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = _find_first_string(value, keys=keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_string(item, keys=keys)
            if found:
                return found
    return None


def _walk_strings(payload: object):
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _walk_strings(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_strings(item)
    elif isinstance(payload, str):
        yield payload


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 5 and all(parts)


def _looks_like_media_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".m4v")) or (
        "video" in path
    )
