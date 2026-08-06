"""Unit tests for Ask Help quality gate and English-mismatch helpers."""

from __future__ import annotations

from src.models import KnowledgeAnswer, KnowledgeStep, SourceReference
from src.qa.help_gate import help_overlap_score, pick_better_translation
from src.qa.localize_compose import answer_looks_english


def test_help_overlap_prefers_published_wording() -> None:
    help_texts = [
        "Pour créer une facture fournisseur, ouvrez Comptes fournisseurs "
        "et sélectionnez Factures fournisseurs."
    ]
    candidate = "ouvrez Comptes fournisseurs et sélectionnez Factures fournisseurs"
    gate = help_overlap_score(candidate, help_texts)
    assert gate.score >= 0.25
    assert gate.prefer_candidate is True


def test_pick_tm_over_mt_when_help_aligned() -> None:
    help_texts = ["facture fournisseur approuvée pour paiement"]
    chosen, reason = pick_better_translation(
        mt_candidate="La facture du vendeur est OK",
        tm_or_help_candidate="facture fournisseur approuvée pour paiement",
        help_texts=help_texts,
    )
    assert "facture fournisseur" in chosen
    assert "tm" in reason


def test_answer_looks_english_detects_leak() -> None:
    answer = KnowledgeAnswer(
        summary="GAAP is the accounting framework used in Sage Intacct.",
        steps=[
            KnowledgeStep(
                instruction="Open General Ledger",
                detail="Choose journals",
                source_ids=["abc"],
            )
        ],
        notes=[],
        generation_model="test",
        sources=[
            SourceReference(
                source_id="abc",
                source_url="https://www.intacct.com/ia/docs/en_US/x.htm",
                title="GAAP",
                heading_path="",
                score=0.9,
            )
        ],
    )
    assert answer_looks_english(answer, "de_DE") is True


def test_answer_looks_english_false_for_en() -> None:
    answer = KnowledgeAnswer(
        summary="Hello",
        steps=[],
        notes=[],
        generation_model="test",
        sources=[],
    )
    assert answer_looks_english(answer, "en_US") is False
