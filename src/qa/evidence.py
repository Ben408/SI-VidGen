"""Ask evidence selection: scope gates, multi-query fusion, coherent page sets.

Retrieval similarity discovers candidates; it does not authorize an answer.
Coverage is always judged against the original user goal.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from config.settings import Settings
from src.llm.client import StructuredLLM
from src.models import Classification, RetrievedChunk
from src.rag.okf.enrich import enrich_retrieved_with_okf
from src.rag.okf.store import OkfStore
from src.rag.rag_retriever import InsufficientEvidenceError, retrieve_help_content
from src.rag.vector_store import VectorStore

MIN_CLASSIFY_CONFIDENCE = 0.35
LOW_CONFIDENCE_FOR_REWRITE = 0.55
MIN_REWRITE_OVERLAP = 0.18
RRF_K = 60
DEFAULT_MAX_PAGES = 4
MAX_CHUNKS_FOR_GENERATION = 8

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "your",
    "our",
    "are",
    "is",
    "was",
    "were",
    "how",
    "do",
    "does",
    "can",
    "what",
    "when",
    "where",
    "why",
    "which",
    "about",
    "using",
    "use",
    "used",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "my",
    "me",
    "we",
    "i",
    "it",
    "its",
    "or",
    "be",
    "by",
    "at",
    "as",
    "if",
    "not",
    "no",
    "yes",
    "please",
    "help",
    "need",
    "want",
    "sage",
    "intacct",
}

_TASK_VERBS = {
    "reverse",
    "reversing",
    "close",
    "closing",
    "create",
    "creating",
    "edit",
    "editing",
    "delete",
    "deleting",
    "approve",
    "approving",
    "pay",
    "paying",
    "payment",
    "reconcile",
    "reconciling",
    "import",
    "export",
    "configure",
    "configuration",
    "setup",
    "troubleshoot",
    "troubleshooting",
    "void",
    "adjust",
    "adjustment",
    "post",
    "posting",
    "allocate",
    "allocation",
    "consolidate",
    "consolidation",
    "match",
    "matching",
    "enable",
    "disable",
}

_GENERIC_TITLE_TOKENS = {
    "overview",
    "about",
    "introduction",
    "welcome",
    "home",
    "index",
    "basics",
    "getting",
    "started",
    "release",
    "notes",
    "whats",
    "new",
    "changes",
}


@dataclass
class RankedChunk:
    chunk: RetrievedChunk
    rrf: float = 0.0
    boost: float = 0.0
    provenance: set[str] = field(default_factory=set)

    @property
    def score(self) -> float:
        return self.rrf + self.boost


def tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(
            ch.lower() if ch.isalnum() else " " for ch in text
        ).split()
        if len(token) > 2 and token not in _STOPWORDS
    }


def token_overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def scope_refuse_reason(question: str, classification: Classification) -> str | None:
    """Refuse before generation when classification is weak or goal-changing."""
    if classification.confidence < MIN_CLASSIFY_CONFIDENCE:
        return (
            "Not enough confidence that this is an in-scope Sage Intacct Help question "
            f"(classification confidence {classification.confidence:.2f})."
        )

    q_tokens = tokens(question)
    rewrite_tokens = tokens(classification.search_query)
    overlap = token_overlap_ratio(q_tokens, rewrite_tokens)
    if (
        classification.confidence < LOW_CONFIDENCE_FOR_REWRITE
        and overlap < MIN_REWRITE_OVERLAP
        and len(q_tokens) >= 3
    ):
        return (
            "The classifier rewrite does not preserve the original goal with enough "
            "confidence to answer from Help."
        )
    return None


def _page_key(chunk: RetrievedChunk) -> str:
    return (chunk.source_url or "").split("#", 1)[0].rstrip("/").lower()


def _retrieve_one(
    query: str,
    vector_store: VectorStore,
    llm: StructuredLLM,
    settings: Settings,
    *,
    help_language: str,
) -> list[RetrievedChunk]:
    try:
        return retrieve_help_content(
            query,
            vector_store,
            llm,
            top_k=settings.rag_top_k,
            min_score=settings.rag_min_score,
            language=help_language,
        )
    except InsufficientEvidenceError:
        return []


def fuse_rankings(
    ranked_lists: dict[str, list[RetrievedChunk]],
) -> dict[str, RankedChunk]:
    """Reciprocal rank fusion across query provenance lists."""
    fused: dict[str, RankedChunk] = {}
    for provenance, chunks in ranked_lists.items():
        for rank, chunk in enumerate(chunks, start=1):
            entry = fused.get(chunk.source_id)
            if entry is None:
                entry = RankedChunk(chunk=chunk, provenance={provenance})
                fused[chunk.source_id] = entry
            else:
                entry.provenance.add(provenance)
                if chunk.score > entry.chunk.score:
                    entry.chunk = chunk
            entry.rrf += 1.0 / (RRF_K + rank)
    return fused


def _boost_chunk(question: str, ranked: RankedChunk) -> float:
    q_tokens = tokens(question)
    chunk = ranked.chunk
    title_tokens = tokens(chunk.title)
    heading_tokens = tokens(chunk.heading_path)
    text_tokens = tokens(chunk.text[:1_200])
    page_tokens = title_tokens | heading_tokens

    boost = 0.0
    title_overlap = len(q_tokens & title_tokens)
    heading_overlap = len(q_tokens & heading_tokens)
    if title_overlap:
        boost += 0.35 * title_overlap
    if heading_overlap:
        boost += 0.15 * heading_overlap

    # Prefer pages that cover more of the user's entities/verbs.
    coverage = token_overlap_ratio(q_tokens, page_tokens | text_tokens)
    boost += 0.5 * coverage

    q_verbs = q_tokens & _TASK_VERBS
    if q_verbs and (q_verbs & (page_tokens | text_tokens)):
        boost += 0.25

    # Prefer exact / near-exact title matches for troubleshooting pages.
    if title_tokens and title_tokens <= q_tokens:
        boost += 0.4
    if q_tokens and title_tokens and len(title_tokens & q_tokens) >= max(2, len(title_tokens) - 1):
        boost += 0.3

    generic = title_tokens & _GENERIC_TITLE_TOKENS
    if generic and title_overlap <= 1:
        boost -= 0.35 * len(generic)

    body = (chunk.text or "").strip()
    if len(body) < 80:
        boost -= 0.25
    if body.lower().count("click") > 12 and title_overlap == 0:
        boost -= 0.15

    # Slight preference for chunks also found via the original question.
    if "original" in ranked.provenance:
        boost += 0.08
    return boost


def select_coherent_pages(
    question: str,
    fused: dict[str, RankedChunk],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[RetrievedChunk]:
    if not fused:
        return []

    for ranked in fused.values():
        ranked.boost = _boost_chunk(question, ranked)

    by_page: dict[str, list[RankedChunk]] = defaultdict(list)
    for ranked in fused.values():
        by_page[_page_key(ranked.chunk)].append(ranked)

    page_scores: list[tuple[float, str, list[RankedChunk]]] = []
    for page, items in by_page.items():
        page_score = max(item.score for item in items)
        # Soft cohesion: pages with multiple strong chunks rank higher.
        if len(items) > 1:
            page_score += 0.05 * min(len(items), 4)
        page_scores.append((page_score, page, items))

    page_scores.sort(key=lambda row: row[0], reverse=True)
    if not page_scores:
        return []

    top_score = page_scores[0][0]
    selected_pages: list[list[RankedChunk]] = []
    for score, _page, items in page_scores:
        if len(selected_pages) >= max_pages:
            break
        if selected_pages and score < top_score * 0.45:
            break
        selected_pages.append(items)

    selected: list[RankedChunk] = []
    for items in selected_pages:
        selected.extend(sorted(items, key=lambda item: item.score, reverse=True))
    selected.sort(key=lambda item: item.score, reverse=True)

    # Re-stamp chunk.score with fused score for downstream source display.
    out: list[RetrievedChunk] = []
    for ranked in selected[:MAX_CHUNKS_FOR_GENERATION]:
        out.append(ranked.chunk.model_copy(update={"score": ranked.score}))
    return out


def evidence_covers_goal(question: str, selected: list[RetrievedChunk]) -> str | None:
    """Post-retrieval gate against the original user goal."""
    if not selected:
        return "Not enough Help coverage to answer this product question"

    q_tokens = tokens(question)
    if len(q_tokens) < 2:
        return None

    best = selected[0]
    best_tokens = tokens(f"{best.title} {best.heading_path} {best.text[:800]}")
    overlap = token_overlap_ratio(q_tokens, best_tokens)
    title_hit = len(q_tokens & tokens(best.title))

    # Strong title match always passes.
    if title_hit >= 2 or (tokens(best.title) and tokens(best.title) <= q_tokens):
        return None
    if overlap >= 0.28 or (overlap >= 0.18 and title_hit >= 1):
        return None

    # At least one selected page must share a task verb or 2+ entities.
    for chunk in selected[:4]:
        page_tokens = tokens(f"{chunk.title} {chunk.heading_path}")
        if len(q_tokens & page_tokens) >= 2:
            return None
        if (q_tokens & _TASK_VERBS) & page_tokens:
            return None

    return (
        "Retrieved Help topics do not directly support the original question. "
        "Refusing rather than answering from weakly related pages."
    )


def retrieve_and_select_evidence(
    llm: StructuredLLM,
    vector_store: VectorStore,
    okf_store: OkfStore | None,
    settings: Settings,
    *,
    question: str,
    classification_query: str,
    help_language: str,
    plan_followups,
) -> tuple[list[RetrievedChunk], list[str]]:
    """Retrieve with provenance, fuse ranks, enrich, then pick a coherent page set."""
    lists: dict[str, list[RetrievedChunk]] = {}
    original = _retrieve_one(
        question,
        vector_store,
        llm,
        settings,
        help_language=help_language,
    )
    if original:
        lists["original"] = original

    classifier_q = " ".join(classification_query.split()).strip()
    if classifier_q and classifier_q.lower() != question.strip().lower():
        classified = _retrieve_one(
            classifier_q,
            vector_store,
            llm,
            settings,
            help_language=help_language,
        )
        if classified:
            lists["classifier"] = classified
    elif classifier_q and "original" not in lists:
        classified = _retrieve_one(
            classifier_q,
            vector_store,
            llm,
            settings,
            help_language=help_language,
        )
        if classified:
            lists["classifier"] = classified

    seed = lists.get("original") or lists.get("classifier") or []
    follow_ups = plan_followups(
        llm,
        question=question,
        classification_query=classifier_q or question,
        retrieved=seed[:4],
        help_language=help_language,
    )
    for index, query in enumerate(follow_ups):
        more = _retrieve_one(
            query,
            vector_store,
            llm,
            settings,
            help_language=help_language,
        )
        if more:
            lists[f"followup:{index}"] = more

    if not lists:
        return [], follow_ups

    fused = fuse_rankings(lists)
    # Enrich before boosts so procedure text / section assets can influence selection.
    id_order = list(fused.keys())
    enriched = enrich_retrieved_with_okf(
        [fused[source_id].chunk for source_id in id_order],
        okf_store,
    )
    for source_id, chunk in zip(id_order, enriched, strict=True):
        fused[source_id].chunk = chunk

    selected = select_coherent_pages(question, fused)
    return selected, follow_ups
