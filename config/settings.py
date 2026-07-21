from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    web_origin: str = "http://localhost:5173"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "gemma3:12b"
    ollama_fallback_model: str = "llama3.2:latest"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 180
    rag_top_k: int = 6
    rag_min_score: float = 0.2

    intacct_help_start_url: str = (
        "https://www.intacct.com/ia/docs/en_US/help_action/Intacct_basics/welcome.htm"
    )
    intacct_help_allowed_prefix: str = (
        "https://www.intacct.com/ia/docs/en_US/help_action/"
    )
    crawl_delay_seconds: float = 0.25

    data_dir: Path = Path("data")
    help_cache_dir: Path = Path("data/help_xhtml")
    help_assets_dir: Path = Path("data/help_assets")
    vector_store_dir: Path = Path("data/vector_store")
    runs_dir: Path = Path("data/runs")
    output_dir: Path = Path("output")
    scripts_dir: Path = Path("output/scripts")
    payloads_dir: Path = Path("output/payloads")
    videos_dir: Path = Path("output/videos")
    published_dir: Path = Path("output/published")
    log_level: str = "INFO"
    video_backend: str = "local_compositor"
    local_compositor_tts: bool = True
    local_compositor_voice: str = "en-US-JennyNeural"
    local_compositor_tts_rate: str = "-5%"
    local_compositor_captions: bool = True
    higgsfield_api_key: str = ""
    higgsfield_workspace_id: str = ""
    higgsfield_job_type: str = "gemini_omni"
    higgsfield_wait_timeout_seconds: int = 600

    def ensure_runtime_directories(self) -> None:
        for path in (
            self.data_dir,
            self.help_cache_dir,
            self.help_assets_dir,
            self.help_assets_dir / "files",
            self.vector_store_dir,
            self.runs_dir,
            self.data_dir / "compositor_jobs",
            self.output_dir,
            self.scripts_dir,
            self.payloads_dir,
            self.videos_dir,
            self.published_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_directories()
    return settings
