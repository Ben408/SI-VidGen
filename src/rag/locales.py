"""Sage Intacct Help locale tags and crawl helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def help_base_url() -> str:
    return "https://www.intacct.com/ia/docs"


def locale_spec(locale: str) -> HelpLocaleSpec:
    if locale not in HELP_LOCALES:
        raise ValueError(f"Unsupported help locale: {locale}")
    prefix = f"{help_base_url()}/{locale}/help_action/"
    return HelpLocaleSpec(
        locale=locale,
        start_url=f"{prefix}Intacct_basics/welcome.htm",
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
    marker = "/ia/docs/"
    if marker not in url:
        return None
    rest = url.split(marker, 1)[1]
    tag = rest.split("/", 1)[0]
    return tag if tag in HELP_LOCALES else None


def cache_dir_for_locale(help_cache_dir: Path, locale: str) -> Path:
    """EN may live at legacy ``help_xhtml/``; other locales use ``help_xhtml/{locale}/``."""
    if locale == "en_US":
        legacy_pages = help_cache_dir / "pages"
        if legacy_pages.is_dir():
            return help_cache_dir
    return help_cache_dir / locale


def detect_question_language(text: str, default: str = "en_US") -> str:
    """Lightweight locale guess from character/word hints."""
    lowered = f" {(text or '').lower()} "
    scores = {loc: sum(1 for h in hints if h in lowered) for loc, hints in _LANG_HINTS.items()}
    if any(ch in text for ch in "äöüß"):
        scores["de_DE"] = scores.get("de_DE", 0) + 3
    if any(ch in text for ch in "àâçèêëîïôùûüÿœ"):
        scores["fr_FR"] = scores.get("fr_FR", 0) + 2
    if any(ch in text for ch in "¿¡ñ"):
        scores["es_ES"] = scores.get("es_ES", 0) + 3
    # Shared accent é/á/í/ó/ú — small boost to both FR and ES; word hints decide.
    if any(ch in text for ch in "áéíóú"):
        scores["fr_FR"] = scores.get("fr_FR", 0) + 1
        scores["es_ES"] = scores.get("es_ES", 0) + 1
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
    source = source_language if source_language in HELP_LOCALES else detect_question_language(question)
    if answer_language in HELP_LOCALES:
        answer = answer_language
    else:
        answer = source
    return source, answer


def edge_voice_for_locale(locale: str, fallback: str = "en-US-JennyNeural") -> str:
    return LOCALE_TO_EDGE_VOICE.get(locale, fallback)
