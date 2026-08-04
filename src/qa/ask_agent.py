"""Product Q&A over Chroma + OKF for internal Sage Intacct staff (no video)."""

from __future__ import annotations

import json
import re
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from config.settings import Settings
from src.classifier.classify_issue import classify_issue
from src.intake.intake_handler import normalize_issue
from src.llm.client import OllamaClient, StructuredLLM
from src.models import (
    AskResult,
    IssueInput,
    KnowledgeAnswer,
    KnowledgeStep,
    OkfConceptRef,
    SourceReference,
)
from src.rag.locales import normalize_answer_language
from src.rag.okf.enrich import enrich_retrieved_with_okf, related_concepts_for_sources
from src.rag.okf.store import OkfStore
from src.rag.rag_retriever import InsufficientEvidenceError, retrieve_help_content
from src.rag.vector_store import VectorStore
from src.runtime_gate import BusyError, WorkGate
from src.telemetry.logging import log_event, stage
from src.telemetry.progress import ProgressTracker
from src.telemetry.run_store import JsonRunStore

PLAN_SYSTEM = """You plan Help Center retrieval for a Sage Intacct product-usage question.
Given the user question and the first retrieval hits, return up to 2 additional
search queries in the requested help_language that cover missing modules, screens, or prerequisites.
Return an empty list when the first retrieval already covers the goal.
Do not invent product behavior. Structured data only."""

ANSWER_SYSTEM = """You are an internal Sage Intacct product expert answering staff how-to questions.
Use only the supplied official Help excerpts (and derived OKF procedure text in those excerpts).
Produce a structured answer: summary, ordered steps, and notes.
Write the entire answer in the requested answer_language.
Every step must cite one or more supplied source_ids (copy ids exactly from the sources).
Set coverage_sufficient=true whenever a supplied Help topic directly addresses the goal
(for example a topic titled like "Reverse journal entries" for reversing a GL journal).
Answer from those excerpts even if some edge cases are missing; put caveats in notes.
Set coverage_sufficient=false ONLY when the sources clearly do not cover the procedure at all.
Do not invent navigation or UI steps that are absent from the excerpts.
Do not include external websites, vendor tools, or any URL that is not an official
Sage Intacct Help link from the supplied sources (https://www.intacct.com/ia/docs/…).
Never recommend third-party DNS, email, or network utilities. Help topic titles and
source_ids are enough; the product UI lists Help references separately.
Never put source_id values, content hashes, or Help file names (.htm / .xhtml) in
summary, steps, or notes — cite only via the structured source_ids field on each step.
Structured data only."""

# Only official Intacct Help Center links may appear in Ask free text.
_ALLOWED_HELP_URL_PREFIXES = (
    "https://www.intacct.com/ia/docs/",
    "http://www.intacct.com/ia/docs/",
)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", re.IGNORECASE)
_BARE_URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+", re.IGNORECASE)
# Chroma / chunk source ids are sha-like hex; models often paste them into notes.
_SOURCE_ID_TOKEN_RE = re.compile(r"\[?\b[a-f0-9]{40,64}\b\]?", re.IGNORECASE)
_HELP_FILE_TOKEN_RE = re.compile(r"\b[\w.-]+\.(?:xhtml|htm|html)\b", re.IGNORECASE)


class FollowUpPlan(BaseModel):
    additional_queries: list[str] = Field(default_factory=list, max_length=2)


class AnswerStepDraft(BaseModel):
    instruction: str = Field(min_length=1, max_length=500)
    detail: str = Field(default="", max_length=1_000)
    source_ids: list[str] = Field(min_length=1, max_length=6)


class AnswerDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=1_200)
    steps: list[AnswerStepDraft] = Field(default_factory=list, max_length=12)
    notes: list[str] = Field(default_factory=list, max_length=8)
    coverage_sufficient: bool = True
    coverage_gap: str = Field(default="", max_length=800)


class AskService:
    def __init__(
        self,
        settings: Settings,
        run_store: JsonRunStore,
        tracker: ProgressTracker,
        gate: WorkGate,
        llm: OllamaClient | None = None,
        vector_store: VectorStore | None = None,
        okf_store: OkfStore | None = None,
    ) -> None:
        self.settings = settings
        self.run_store = run_store
        self.tracker = tracker
        self.gate = gate
        self.llm = llm or OllamaClient(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            fallback_model=settings.ollama_fallback_model,
            embed_model=settings.ollama_embed_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
        from src.rag.chroma_store import ChromaVectorStore

        self.vector_store = vector_store or ChromaVectorStore(settings.vector_store_dir)
        self.okf_store = okf_store
        if self.okf_store is None and settings.okf_dir.joinpath("catalog.json").is_file():
            self.okf_store = OkfStore(settings.okf_dir)
        self._pipeline_lock = Lock()

    def create_ask_id(self) -> str:
        return f"ask-{uuid4()}"

    def queue(self, ask_id: str) -> AskResult:
        result = AskResult(ask_id=ask_id, status="queued")
        self._write_result(result)
        return result

    def run(self, ask_id: str, question: IssueInput) -> AskResult:
        with self._pipeline_lock:
            return self._run_locked(ask_id, question)

    def get_result(self, ask_id: str) -> AskResult | None:
        record = self.run_store.read(ask_id)
        result = record.get("result")
        return AskResult.model_validate(result) if result else None

    def _run_locked(self, ask_id: str, question: IssueInput) -> AskResult:
        try:
            self.gate.acquire("ask")
        except BusyError as error:
            result = AskResult(
                ask_id=ask_id,
                status="failed",
                error_code="WORKSPACE_BUSY",
                error_detail=str(error),
            )
            self._write_result(result)
            return result

        self._write_status(ask_id, "processing")
        log_event("ask_started", run_id=ask_id)
        try:
            with stage(ask_id, "intake", self.tracker):
                issue = normalize_issue(question)
                source_language, answer_language = normalize_answer_language(
                    question=issue.raw_text,
                    answer_language=question.answer_language,
                    source_language=question.source_language,
                )
                # Retrieve from the Help corpus matching the answer language
                # (localized Help is the grounding source for that language).
                help_language = answer_language

            with stage(ask_id, "classify", self.tracker):
                classification = classify_issue(
                    issue, self.llm, help_language=help_language
                )

            with stage(ask_id, "retrieve", self.tracker):
                retrieved = retrieve_help_content(
                    classification.search_query,
                    self.vector_store,
                    self.llm,
                    top_k=self.settings.rag_top_k,
                    min_score=self.settings.rag_min_score,
                    language=help_language,
                )
                retrieved = enrich_retrieved_with_okf(retrieved, self.okf_store)

            with stage(ask_id, "retrieve_followup", self.tracker):
                follow_ups = _plan_followups(
                    self.llm,
                    question=issue.raw_text,
                    classification_query=classification.search_query,
                    retrieved=retrieved,
                    help_language=help_language,
                )
                for query in follow_ups:
                    try:
                        more = retrieve_help_content(
                            query,
                            self.vector_store,
                            self.llm,
                            top_k=self.settings.rag_top_k,
                            min_score=self.settings.rag_min_score,
                            language=help_language,
                        )
                        more = enrich_retrieved_with_okf(more, self.okf_store)
                        retrieved = _merge_chunks(retrieved, more)
                    except InsufficientEvidenceError:
                        continue

            if not retrieved:
                raise InsufficientEvidenceError(
                    "Not enough Help coverage to answer this product question"
                )

            with stage(ask_id, "answer", self.tracker):
                answer, refused_gap = _build_answer(
                    self.llm,
                    question=issue.raw_text,
                    retrieved=retrieved,
                    answer_language=answer_language,
                )

            if refused_gap is not None:
                result = AskResult(
                    ask_id=ask_id,
                    status="refused",
                    classification=classification,
                    sources=[_as_source(chunk) for chunk in retrieved[:8]],
                    okf_concepts=[
                        OkfConceptRef.model_validate(item)
                        for item in related_concepts_for_sources(
                            [_as_source(chunk) for chunk in retrieved[:5]],
                            self.okf_store,
                        )
                    ],
                    coverage_gap=refused_gap,
                    error_code="INSUFFICIENT_HELP_COVERAGE",
                    error_detail=refused_gap,
                    source_language=source_language,
                    answer_language=answer_language,
                )
                self._write_result(result)
                log_event("ask_refused", run_id=ask_id, error_code="INSUFFICIENT_HELP_COVERAGE")
                return result

            sources = answer.sources
            result = AskResult(
                ask_id=ask_id,
                status="completed",
                classification=classification,
                answer=answer,
                sources=sources,
                okf_concepts=[
                    OkfConceptRef.model_validate(item)
                    for item in related_concepts_for_sources(sources, self.okf_store)
                ],
                followup_queries=follow_ups,
                source_language=source_language,
                answer_language=answer_language,
            )
            self._write_result(result)
            log_event("ask_completed", run_id=ask_id)
            return result
        except InsufficientEvidenceError as exc:
            result = AskResult(
                ask_id=ask_id,
                status="refused",
                coverage_gap=str(exc),
                error_code="INSUFFICIENT_HELP_COVERAGE",
                error_detail=str(exc),
            )
            self._write_result(result)
            log_event("ask_refused", run_id=ask_id, error_code="INSUFFICIENT_HELP_COVERAGE")
            return result
        except Exception as exc:
            error_code = f"ASK_{type(exc).__name__.upper()}"
            result = AskResult(
                ask_id=ask_id,
                status="failed",
                error_code=error_code,
                error_detail=str(exc)[:500],
            )
            self._write_result(result)
            log_event("ask_failed", run_id=ask_id, error_code=error_code)
            return result
        finally:
            self.gate.release("ask")

    def _write_status(self, ask_id: str, status: str) -> None:
        self._write_result(
            AskResult(ask_id=ask_id, status=status)  # type: ignore[arg-type]
        )

    def _write_result(self, result: AskResult) -> None:
        record = self.run_store.read(result.ask_id)
        record["result"] = result.model_dump(mode="json")
        self.run_store.write(result.ask_id, record)


def _plan_followups(
    llm: StructuredLLM,
    *,
    question: str,
    classification_query: str,
    retrieved: list,
    help_language: str = "en_US",
) -> list[str]:
    payload = [
        {
            "source_id": chunk.source_id,
            "title": chunk.title,
            "heading": chunk.heading_path,
            "excerpt": chunk.text[:600],
        }
        for chunk in retrieved[:4]
    ]
    user = (
        f"Question: {question}\n"
        f"Help language for additional queries: {help_language}\n"
        f"Primary search query: {classification_query}\n"
        f"First retrieval hits:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    draft, _model = llm.generate_structured(PLAN_SYSTEM, user, FollowUpPlan)
    queries: list[str] = []
    seen = {classification_query.strip().lower()}
    for item in draft.additional_queries:
        cleaned = " ".join(item.split()).strip()
        if len(cleaned) < 3:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(cleaned)
        if len(queries) >= 2:
            break
    return queries


def _build_answer(
    llm: StructuredLLM,
    *,
    question: str,
    retrieved: list,
    answer_language: str = "en_US",
) -> tuple[KnowledgeAnswer | None, str | None]:
    grounded = retrieved[:8]
    answer, refused_gap = _draft_to_answer(
        llm,
        question=question,
        grounded=grounded,
        answer_language=answer_language,
    )
    if answer is not None:
        return answer, None
    if refused_gap is not None and _titles_look_relevant(question, grounded):
        answer, refused_gap = _draft_to_answer(
            llm,
            question=question,
            grounded=grounded,
            force_answer=True,
            answer_language=answer_language,
        )
        if answer is not None:
            return answer, None
    return None, refused_gap or (
        "Not enough Help coverage to answer this product question"
    )


def _draft_to_answer(
    llm: StructuredLLM,
    *,
    question: str,
    grounded: list,
    force_answer: bool = False,
    answer_language: str = "en_US",
) -> tuple[KnowledgeAnswer | None, str | None]:
    allowed_ids = {chunk.source_id for chunk in grounded}
    source_payload = [
        {
            "source_id": chunk.source_id,
            "title": chunk.title,
            "heading": chunk.heading_path,
            "url": chunk.source_url,
            "text": chunk.text[:2_000],
        }
        for chunk in grounded
    ]
    system = ANSWER_SYSTEM
    if force_answer:
        system = (
            ANSWER_SYSTEM
            + "\nIMPORTANT: Relevant Help topics were already retrieved for this question. "
            "You MUST set coverage_sufficient=true and produce grounded steps. "
            "Copy source_id values exactly from the supplied sources."
        )
    user = (
        f"Question: {question}\n"
        f"answer_language: {answer_language}\n"
        f"Official help sources:\n{json.dumps(source_payload, ensure_ascii=False)}"
    )
    draft, model = llm.generate_structured(system, user, AnswerDraft)

    steps: list[KnowledgeStep] = []
    used_citation_fallback = False
    for item in draft.steps:
        cited = [source_id for source_id in item.source_ids if source_id in allowed_ids]
        if not cited and grounded:
            cited = [grounded[0].source_id]
            used_citation_fallback = True
        if not cited:
            continue
        steps.append(
            KnowledgeStep(
                instruction=item.instruction,
                detail=item.detail,
                source_ids=cited,
            )
        )

    if steps:
        notes = [note.strip() for note in draft.notes if note.strip()]
        if not draft.coverage_sufficient:
            gap = draft.coverage_gap.strip()
            if gap:
                notes.append(f"Coverage note: {gap}")
        if used_citation_fallback:
            notes.append(
                "Step citations were normalized to retrieved Help topics "
                "because the model returned non-matching source ids."
            )
        steps = [
            KnowledgeStep(
                instruction=scrub_ask_free_text(step.instruction),
                detail=scrub_ask_free_text(step.detail),
                source_ids=step.source_ids,
            )
            for step in steps
            if scrub_ask_free_text(step.instruction)
        ]
        notes = [scrub_ask_free_text(note) for note in notes]
        notes = [note for note in notes if note]
        sources = [_as_source(chunk) for chunk in grounded]
        return (
            KnowledgeAnswer(
                summary=scrub_ask_free_text(draft.summary),
                steps=steps,
                notes=notes,
                generation_model=model,
                sources=sources,
            ),
            None,
        )

    if not draft.coverage_sufficient:
        gap = draft.coverage_gap.strip() or (
            "Not enough Help coverage to answer this product question"
        )
        return None, gap

    return None, (
        "Not enough Help coverage to answer this product question "
        "(answer steps could not be grounded in retrieved sources)"
    )


def _titles_look_relevant(question: str, retrieved: list) -> bool:
    question_tokens = _tokens(question)
    if len(question_tokens) < 2:
        return False
    for chunk in retrieved[:4]:
        title_tokens = _tokens(f"{chunk.title} {chunk.heading_path}")
        if len(question_tokens & title_tokens) >= 2:
            return True
    return False


_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "and",
    "or",
    "for",
    "in",
    "on",
    "how",
    "do",
    "i",
    "is",
}


def is_allowed_help_url(url: str) -> bool:
    cleaned = (url or "").strip().rstrip(").,;]!>?")
    low = cleaned.lower()
    return any(low.startswith(prefix) for prefix in _ALLOWED_HELP_URL_PREFIXES)


def scrub_non_help_urls(text: str) -> str:
    """Remove any non–Sage Intacct Help URLs from Ask free text."""
    if not text:
        return ""

    def _md_repl(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if is_allowed_help_url(url):
            return match.group(0)
        return label.strip()

    cleaned = _MD_LINK_RE.sub(_md_repl, text)

    def _url_repl(match: re.Match[str]) -> str:
        url = match.group(0)
        return url if is_allowed_help_url(url) else ""

    cleaned = _BARE_URL_RE.sub(_url_repl, cleaned)
    return _tidy_scrubbed_text(cleaned)


def scrub_internal_ids(text: str) -> str:
    """Remove chunk source_ids / Help file names that are useless to staff."""
    if not text:
        return ""
    cleaned = _SOURCE_ID_TOKEN_RE.sub("", text)
    cleaned = _HELP_FILE_TOKEN_RE.sub("", cleaned)
    return _tidy_scrubbed_text(cleaned)


def scrub_ask_free_text(text: str) -> str:
    """Sanitize Ask summary/steps/notes for Slack and API consumers."""
    return scrub_internal_ids(scrub_non_help_urls(text))


def _tidy_scrubbed_text(text: str) -> str:
    cleaned = re.sub(r"[ \t]{2,}", " ", text)
    cleaned = re.sub(r" ?\n ?", "\n", cleaned)
    cleaned = re.sub(r"\(\s*(?:like|e\.g\.|eg\.?|for example)?\s*\)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*\]", "", cleaned)
    cleaned = re.sub(r"[ \t]+\.", ".", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(
            ch.lower() if ch.isalnum() else " " for ch in text
        ).split()
        if len(token) > 2 and token not in _STOPWORDS
    }


def _merge_chunks(existing: list, more: list) -> list:
    by_id = {chunk.source_id: chunk for chunk in existing}
    for chunk in more:
        prior = by_id.get(chunk.source_id)
        if prior is None or chunk.score > prior.score:
            by_id[chunk.source_id] = chunk
    return sorted(by_id.values(), key=lambda item: item.score, reverse=True)


def _as_source(chunk) -> SourceReference:
    return SourceReference(
        source_id=chunk.source_id,
        source_url=chunk.source_url,
        title=chunk.title,
        heading_path=chunk.heading_path,
        score=chunk.score,
    )
