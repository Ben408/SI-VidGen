"""YAML frontmatter helpers and path utilities for OKF bundles."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def slugify(value: str, *, max_length: int = 80) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return (text or "untitled")[:max_length]


def topic_relpath_from_url(page_url: str) -> str:
    """Map a Help page URL to topics/<module>/.../<stem>.md under the bundle."""
    path = urlparse(page_url).path
    marker = "/help_action/"
    if marker not in path:
        return f"topics/{slugify(path)}.md"
    relative = path.split(marker, 1)[1]
    relative = relative.removesuffix(".htm").removesuffix(".html")
    parts = [slugify(part, max_length=60) for part in relative.split("/") if part]
    if not parts:
        parts = ["untitled"]
    return "topics/" + "/".join(parts) + ".md"


def module_from_page_url(page_url: str) -> str:
    path = urlparse(page_url).path
    marker = "/help_action/"
    if marker not in path:
        return "unknown"
    rest = path.split(marker, 1)[1]
    first = rest.split("/", 1)[0]
    return first or "unknown"


def dump_concept(
    *,
    frontmatter: dict[str, Any],
    body: str,
) -> str:
    yaml_text = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    body = body.strip()
    if body:
        return f"---\n{yaml_text}\n---\n\n{body}\n"
    return f"---\n{yaml_text}\n---\n"


def load_concept(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text.strip()
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, match.group(2).strip()


PROCEDURE_HEADING_RE = re.compile(
    r"^(to |how to |steps?( to)? |correct |create |import |reverse |"
    r"post |configure |set up |add |edit |delete |enter |upload )",
    re.IGNORECASE,
)
UI_HEADING_RE = re.compile(
    r"(screen|dialog|window|form|page|workspace|list|menu)",
    re.IGNORECASE,
)


def classify_section(
    heading: str,
    body_lines: list[str],
    asset_classes: list[str],
) -> str:
    """Return OKF type for a section: Procedure, UIScreen, or HelpSection."""
    step_lines = sum(1 for line in body_lines if line.startswith("- "))
    if PROCEDURE_HEADING_RE.search(heading) or step_lines >= 2:
        return "Procedure"
    if UI_HEADING_RE.search(heading) or any(
        cls in {"screenshot", "example"} for cls in asset_classes
    ):
        return "UIScreen"
    if step_lines >= 1:
        return "Procedure"
    return "HelpSection"
