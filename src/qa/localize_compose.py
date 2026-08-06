"""Bounded Ask answer localization compose (T1 free path).

Latency budget (from Hermes docs/benchmarks.md):
  Additive p50 target ≤ 3s; skip hops when budget exhausted.
Baseline (2026-08-06): translategemma ~0.8s, Phrase TM ~1.7s, Termweb ~7s.
Termweb is OFF by default on the Ask path (blows Slack budget).

Strategy: at most one Phrase TM lookup (summary) + one translategemma
batch for remaining English fields — not per-field round-trips.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field

from src.models import KnowledgeAnswer, KnowledgeStep
from src.qa.help_gate import help_overlap_score, pick_better_translation
from src.rag.locales import detect_question_language

DEFAULT_BUDGET_S = float(os.environ.get("ASK_LOCALIZE_BUDGET_S", "3.0"))
PHRASE_TM_TIMEOUT_S = float(os.environ.get("ASK_LOCALIZE_PHRASE_TIMEOUT_S", "2.5"))
TRANSLATE_TIMEOUT_S = float(os.environ.get("ASK_LOCALIZE_MT_TIMEOUT_S", "25.0"))
ENABLE_PHRASE_TM = os.environ.get("ASK_LOCALIZE_PHRASE_TM", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
# Termweb baseline ~7s — disabled on Ask compose unless explicitly enabled.
ENABLE_TERMWEB = os.environ.get("ASK_LOCALIZE_TERMWEB", "").strip().lower() in {
    "1",
    "true",
    "yes",
}


@dataclass
class ComposeReport:
    engines: list[str] = field(default_factory=list)
    budget_partial: bool = False
    notes: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0


def answer_looks_english(answer: KnowledgeAnswer, answer_language: str) -> bool:
    if answer_language == "en_US":
        return False
    sample = " ".join(
        [
            answer.summary or "",
            " ".join(s.instruction for s in answer.steps[:3]),
            " ".join(answer.notes[:2]),
        ]
    ).strip()
    if len(sample) < 12:
        return False
    return detect_question_language(sample, default="en_US") == "en_US"


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.perf_counter())


def _translate_gemma_batch(payload: dict, target: str, timeout: float) -> dict:
    """Translate a small JSON blob of fields in one Ollama call."""
    if timeout < 0.5:
        return {}
    lang_name = {"fr_FR": "French", "de_DE": "German", "es_ES": "Spanish"}.get(
        target, target
    )
    prompt = (
        f"Translate all string values in this JSON to {lang_name} ({target}). "
        "Keep product names (Sage Intacct) and JSON keys unchanged. "
        "Return only valid JSON with the same keys:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    env = os.environ.copy()
    env.setdefault("OLLAMA_MODELS", r"F:\OllamaModels")
    try:
        completed = subprocess.run(
            ["ollama", "run", "translategemma:12b", prompt],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        raw = (completed.stdout or "").strip() or (completed.stderr or "").strip()
    except Exception:  # noqa: BLE001
        return {}
    # Extract JSON object from model output
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _phrase_tm_hit(query: str, target: str, timeout: float) -> str | None:
    if timeout < 0.4 or len(query) < 4:
        return None
    try:
        import sys
        from pathlib import Path

        hermes = Path(os.environ.get("HERMES_LOCAL_ROOT", r"F:\Hermes-Local"))
        if hermes.is_dir() and str(hermes) not in sys.path:
            sys.path.insert(0, str(hermes))
        from packages.intacct.phrase_search import PhraseClient, search_tm_content

        token = (
            os.environ.get("PHRASE_TOKEN")
            or os.environ.get("PHRASE_TMS_TOKEN")
            or ""
        ).strip()
        if not token:
            env_path = hermes / ".env"
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
                token = (
                    os.environ.get("PHRASE_TOKEN")
                    or os.environ.get("PHRASE_TMS_TOKEN")
                    or ""
                ).strip()
        if not token:
            return None
        region = (os.environ.get("PHRASE_REGION") or "eu").strip().lower()
        client = PhraseClient(platform_token=token, region=region)
        hits = search_tm_content(
            client,
            query=query[:160],
            target_lang=target,
            source_lang="en_US",
            max_hits=2,
            tm_limit=2,
            timeout=min(timeout, PHRASE_TM_TIMEOUT_S),
        )
        for hit in hits:
            tgt = (hit.get("target") or "").strip()
            if tgt:
                return tgt
    except Exception:  # noqa: BLE001
        return None
    return None


def compose_localized_answer(
    answer: KnowledgeAnswer,
    *,
    answer_language: str,
    help_texts: list[str] | None = None,
    budget_s: float | None = None,
) -> tuple[KnowledgeAnswer, ComposeReport]:
    """Localize English-leaking Ask prose under a hard wall-clock budget."""
    report = ComposeReport()
    t0 = time.perf_counter()
    if answer_language == "en_US" or not answer_looks_english(answer, answer_language):
        report.notes.append("no_mismatch")
        report.elapsed_s = round(time.perf_counter() - t0, 3)
        return answer, report

    budget = budget_s if budget_s is not None else DEFAULT_BUDGET_S
    deadline = time.perf_counter() + budget
    help_texts = help_texts or []
    report.engines.append("help_gate")

    summary = answer.summary or ""
    # Optional single Phrase TM hop on summary (baseline ~1.7s)
    tm_summary: str | None = None
    if ENABLE_PHRASE_TM and _remaining(deadline) >= 0.6:
        tm_summary = _phrase_tm_hit(
            summary, answer_language, min(_remaining(deadline), PHRASE_TM_TIMEOUT_S)
        )
        if tm_summary:
            report.engines.append("phrase_tm")
    else:
        if ENABLE_PHRASE_TM:
            report.budget_partial = True
            report.notes.append("skipped_phrase_tm_budget")

    # Batch MT for fields still English
    payload: dict[str, str] = {}
    if detect_question_language(summary, default="en_US") == "en_US" and not tm_summary:
        payload["summary"] = summary
    for i, step in enumerate(answer.steps[:5]):
        if detect_question_language(step.instruction, default="en_US") == "en_US":
            payload[f"step_{i}_instruction"] = step.instruction
        if step.detail and detect_question_language(step.detail, default="en_US") == "en_US":
            payload[f"step_{i}_detail"] = step.detail
    for i, note in enumerate(answer.notes[:2]):
        if detect_question_language(note, default="en_US") == "en_US":
            payload[f"note_{i}"] = note

    mt_map: dict = {}
    rem = _remaining(deadline)
    if payload and rem >= 0.5:
        mt_map = _translate_gemma_batch(
            payload, answer_language, min(rem, TRANSLATE_TIMEOUT_S)
        )
        if mt_map:
            report.engines.append("translategemma")
        else:
            report.notes.append("mt_batch_empty")
    elif payload:
        report.budget_partial = True
        report.notes.append("skipped_mt_budget")

    def _field(key: str, original: str, tm_alt: str | None = None) -> str:
        mt = str(mt_map.get(key) or "").strip()
        chosen, reason = pick_better_translation(
            mt_candidate=mt,
            tm_or_help_candidate=tm_alt,
            help_texts=help_texts,
        )
        report.notes.append(f"{key}:{reason}")
        if chosen:
            # Keep MT/TM only if Help gate likes it or TM won; else MT if present
            gate = help_overlap_score(chosen, help_texts)
            if gate.prefer_candidate or tm_alt or mt:
                return chosen
        return original

    new_summary = _field("summary", summary, tm_summary)
    new_steps: list[KnowledgeStep] = []
    for i, step in enumerate(answer.steps):
        if i >= 5:
            new_steps.append(step)
            continue
        instr = _field(f"step_{i}_instruction", step.instruction)
        detail = step.detail
        if detail:
            detail = _field(f"step_{i}_detail", detail)
        new_steps.append(
            KnowledgeStep(
                instruction=instr or step.instruction,
                detail=detail,
                source_ids=step.source_ids,
            )
        )

    new_notes: list[str] = []
    for i, note in enumerate(answer.notes):
        if i < 2:
            new_notes.append(_field(f"note_{i}", note))
        else:
            new_notes.append(note)

    engines = sorted({e for e in report.engines})
    footer = f"Localized via {', '.join(engines)} (free path"
    if report.budget_partial:
        footer += ", budget_partial"
    footer += ")."
    if footer not in new_notes:
        new_notes.append(footer)

    if ENABLE_TERMWEB:
        report.notes.append("termweb_skipped_ask_path_latency")

    report.elapsed_s = round(time.perf_counter() - t0, 3)
    localized = KnowledgeAnswer(
        summary=new_summary or answer.summary,
        steps=new_steps or answer.steps,
        notes=new_notes,
        generation_model=answer.generation_model,
        sources=answer.sources,
    )
    return localized, report
