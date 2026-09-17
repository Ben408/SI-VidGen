"""Help locale tags and crawl helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings

HELP_LOCALES: tuple[str, ...] = ("en_US", "fr_FR", "de_DE", "es_ES")

LOCALE_TO_EDGE_VOICE: dict[str, str] = {
    "en_US": "en-US-JennyNeural",
    "fr_FR": "fr-FR-DeniseNeural",
    "de_DE": "de-DE-KatjaNeural",
    "es_ES": "es-ES-ElviraNeural",
}

# Simple script/heuristics for question language detection (not ML).
_LANG_HINTS: dict[str, tuple[str, ...]] = {
    "fr_FR": (
        " le ",
        " la ",
        " les ",
        " des ",
        " une ",
        " pour ",
        " comment ",
        " créer ",
        " creer ",
        " comptabilit",
        " écriture",
        " ecriture",
        " fournisseur",
        " journal ",
        " qu'est-ce ",
        " qu’est-ce ",
        " est-ce ",
        " quel ",
        " quelle ",
        " leurs ",
        " leur ",
        " sur ",
        " utilisateurs",
        " utilisateur ",
        " normes ",
        " norme ",
        " impact ",
        " affectent ",
        " affecte ",
    ),
    "de_DE": (
        " der ",
        " die ",
        " das ",
        " und ",
        " wie ",
        " bitte ",
        " buchung",
        " kreditor",
        " erstellen",
        " für ",
        " fuer ",
    ),
    "es_ES": (
        " el ",
        " la ",
        " los ",
        " las ",
        " una ",
        " para ",
        " cómo ",
        " como ",
        " crear ",
        " asiento",
        " proveedor",
        " contabilidad",
        " qué ",
        " que ",
        " afectan ",
        " afecta ",
        " usuarios",
        " usuario ",
    ),
}


@dataclass(frozen=True)
class HelpLocaleSpec:
    locale: str
    start_url: str
    allowed_prefix: str

    @property
    def path_tag(self) -> str:
        return self.locale


def _settings(settings: Settings | None = None) -> Settings:
    if settings is not None:
        return settings
    from config.settings import get_settings

    return get_settings()


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def _base_and_env_locale(allowed_prefix: str) -> tuple[str, str | None]:
    """Derive crawl base URL and embedded locale (if any) from allowed prefix."""
    prefix = (allowed_prefix or "").rstrip("/")
    for loc in HELP_LOCALES:
        marker = f"/{loc}/help_action"
        if prefix.endswith(marker):
            return prefix[: -len(marker)], loc
    return prefix, None


def help_base_url(settings: Settings | None = None) -> str:
    """Return the Help crawl base from the catalog (or test) allowed prefix."""
    cfg = _settings(settings)
    base, _ = _base_and_env_locale(cfg.help_allowed_prefix)
    return base


def locale_spec(locale: str, settings: Settings | None = None) -> HelpLocaleSpec:
    """Build start/allowed URLs for a locale from catalog Help settings.

    When the configured prefix embeds a locale (``.../{locale}/help_action/``),
    other locales are derived by substituting the locale tag. When it does not
    (e.g. a Confluence space root), the configured start/prefix are used as-is.
    """
    if locale not in HELP_LOCALES:
        raise ValueError(f"Unsupported help locale: {locale}")
    cfg = _settings(settings)
    base, env_locale = _base_and_env_locale(cfg.help_allowed_prefix)
    start = cfg.help_start_url
    allowed = _ensure_trailing_slash(cfg.help_allowed_prefix)

    if env_locale is None or locale == env_locale:
        return HelpLocaleSpec(
            locale=locale,
            start_url=start,
            allowed_prefix=allowed,
        )

    prefix = f"{base}/{locale}/help_action/"
    if f"/{env_locale}/" in start:
        start_url = start.replace(f"/{env_locale}/", f"/{locale}/", 1)
    else:
        start_url = f"{prefix}Intacct_basics/welcome.htm"
    return HelpLocaleSpec(
        locale=locale,
        start_url=start_url,
        allowed_prefix=prefix,
    )


def parse_locales(raw: str) -> list[str]:
    """Parse HELP_LOCALES env: 'en_US' or 'en_US,fr_FR,de_DE,es_ES' or 'all'."""
    text = (raw or "").strip()
    if not text or text.lower() == "en":
        return ["en_US"]
    if text.lower() in {"all", "all-4", "all4"}:
        return list(HELP_LOCALES)
    out: list[str] = []
    for part in text.split(","):
        loc = part.strip()
        if not loc:
            continue
        if loc not in HELP_LOCALES:
            raise ValueError(f"Unknown help locale '{loc}'. Expected one of {HELP_LOCALES}")
        if loc not in out:
            out.append(loc)
    return out or ["en_US"]


def locale_from_help_url(url: str) -> str | None:
    """Return a Help locale path tag if present as a ``/{locale}/`` segment."""
    for loc in HELP_LOCALES:
        if f"/{loc}/" in url:
            return loc
    return None


def cache_dir_for_locale(help_cache_dir: Path, locale: str) -> Path:
    """EN may live at legacy ``help_xhtml/``; other locales use ``help_xhtml/{locale}/``."""
    if locale == "en_US":
        legacy_pages = help_cache_dir / "pages"
        if legacy_pages.is_dir():
            return help_cache_dir
    return help_cache_dir / locale


def assets_dir_for_locale(help_assets_dir: Path, locale: str) -> Path:
    """EN may live at legacy ``help_assets/``; other locales use ``help_assets/{locale}/``."""
    if locale == "en_US":
        legacy_catalog = help_assets_dir / "catalog.json"
        if legacy_catalog.is_file() or (help_assets_dir / "files").is_dir():
            return help_assets_dir
    return help_assets_dir / locale


def detect_question_language(text: str, default: str = "en_US") -> str:
    """Lightweight locale guess from character/word hints."""
    raw = text or ""
    lowered = f" {raw.lower()} "
    # Normalize curly apostrophes so qu'est-ce matches.
    lowered = lowered.replace("’", "'").replace("`", "'")
    scores = {loc: sum(1 for h in hints if h in lowered) for loc, hints in _LANG_HINTS.items()}
    if any(ch in raw for ch in "äöüß"):
        scores["de_DE"] = scores.get("de_DE", 0) + 3
    if any(ch in raw for ch in "àâçèêëîïôùûüÿœ"):
        scores["fr_FR"] = scores.get("fr_FR", 0) + 2
    if any(ch in raw for ch in "¿¡ñ"):
        scores["es_ES"] = scores.get("es_ES", 0) + 3
    # Shared accent é/á/í/ó/ú — small boost to both FR and ES; word hints decide.
    if any(ch in raw for ch in "áéíóú"):
        scores["fr_FR"] = scores.get("fr_FR", 0) + 1
        scores["es_ES"] = scores.get("es_ES", 0) + 1
    # High-precision French openers (GAAP-style questions often miss older hints).
    if re.search(r"(?i)\bqu'est-ce\b|\bquel(?:le)?s?\s+est\b|\bnormes?\b.*\bgaap\b", lowered):
        scores["fr_FR"] = scores.get("fr_FR", 0) + 4
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return default


def normalize_answer_language(
    *,
    question: str,
    answer_language: str | None = None,
    source_language: str | None = None,
) -> tuple[str, str]:
    """Return (source_language, answer_language) with defaults."""
    if source_language in HELP_LOCALES:
        source = source_language
    else:
        source = detect_question_language(question)
    answer = answer_language if answer_language in HELP_LOCALES else source
    return source, answer


def edge_voice_for_locale(locale: str, fallback: str = "en-US-JennyNeural") -> str:
    return LOCALE_TO_EDGE_VOICE.get(locale, fallback)
