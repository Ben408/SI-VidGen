"""Lexical Help-corpus quality gate for Ask localization.

Compares candidate target-language strings to already-retrieved in-language
Help chunks. Prefer Help/TM wording when overlap is high — no extra Chroma
round-trip (keeps Slack latency low).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text or "") if len(t) > 2}


@dataclass(frozen=True)
class HelpGateResult:
    score: float
    prefer_candidate: bool
    matched_chunk_preview: str = ""


def help_overlap_score(candidate: str, help_texts: list[str]) -> HelpGateResult:
    """Return max Jaccard-like overlap of candidate tokens vs Help chunk tokens."""
    cand = _tokens(candidate)
    if not cand or not help_texts:
        return HelpGateResult(score=0.0, prefer_candidate=False)
    best = 0.0
    preview = ""
    for chunk in help_texts:
        ht = _tokens(chunk)
        if not ht:
            continue
        inter = len(cand & ht)
        union = len(cand | ht) or 1
        # Emphasize coverage of candidate by Help (how much of the MT is published)
        coverage = inter / len(cand)
        jaccard = inter / union
        score = 0.65 * coverage + 0.35 * jaccard
        if score > best:
            best = score
            preview = (chunk or "")[:160]
    # Prefer Help-aligned candidate when ≥ ~25% of its content words appear in Help
    return HelpGateResult(
        score=round(best, 4),
        prefer_candidate=best >= 0.25,
        matched_chunk_preview=preview,
    )


def pick_better_translation(
    *,
    mt_candidate: str,
    tm_or_help_candidate: str | None,
    help_texts: list[str],
) -> tuple[str, str]:
    """Choose between MT and TM/Help string using the Help gate.

    Returns (chosen_text, reason).
    """
    tm = (tm_or_help_candidate or "").strip()
    mt = (mt_candidate or "").strip()
    if tm and not mt:
        return tm, "tm_only"
    if mt and not tm:
        gate = help_overlap_score(mt, help_texts)
        return mt, f"mt_help_score={gate.score}"
    if not tm and not mt:
        return "", "empty"
    gate_tm = help_overlap_score(tm, help_texts)
    gate_mt = help_overlap_score(mt, help_texts)
    if gate_tm.score >= gate_mt.score and gate_tm.prefer_candidate:
        return tm, f"tm_preferred_help_score={gate_tm.score}"
    if gate_tm.score >= 0.25 and gate_tm.score + 0.05 >= gate_mt.score:
        return tm, f"tm_near_mt_help_score={gate_tm.score}"
    return mt, f"mt_preferred_help_score={gate_mt.score}"
