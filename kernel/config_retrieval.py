"""
MODULE: kernel.config_retrieval
GOAL: The `retrieval` section of the kernel configuration: bounds, ranking and rerank settings
    for repository retrieval.
BUSINESS CONTEXT: What counts as relevant evidence and how much of it is read are reviewed
    configuration, so retrieval quality is tuned without a code change.
ARCHITECTURE: A frozen, extra-forbidding Pydantic section with no field defaults, split out of
    `kernel.config` (which re-exports it) to stay under the file-size limit.
"""

from __future__ import annotations

from pydantic import Field

from kernel.config_sections import Probability, _Section


class RetrievalConfig(_Section):
    """Repository retrieval bounds."""

    relevance_threshold: Probability
    """Relevance a candidate needs to be kept as evidence at all."""
    top_k: int = Field(ge=1)
    """Most evidence items kept per need."""
    max_candidates: int = Field(ge=1)
    """Most candidates gathered per need before reranking."""
    excerpt_context_lines: int = Field(ge=0)
    """Lines of context kept around the best-matching lines of an excerpt."""
    max_excerpt_chars: int = Field(ge=1)
    """Longest excerpt kept per item."""
    max_file_bytes: int = Field(ge=1)
    """Largest file retrieval reads."""
    deny_globs: list[str]
    """Path patterns retrieval must never read (secrets, build output)."""
    coverage_relevance_threshold: Probability
    """Relevance a kept item needs to count towards a need's coverage (lower ones stay context)."""
    sections_per_file: int = Field(ge=1)
    """Sections (headings, top-level keys, top-level defs) returned per file, best first."""
    max_section_lines: int = Field(ge=10)
    """Longest section (lines) scored whole; a longer one is cut into windows of this many lines."""
    source_candidate_floor: int = Field(ge=1)
    """Fewest candidates a source may offer when it is small (capped by `max_candidates`)."""
    source_candidate_ratio: float = Field(gt=0)
    """Candidates a source may offer per scanned file (bounded by `max_candidates`)."""
    max_explicit_locators: int = Field(ge=0)
    """Most explicit locators fetched per request (`retrieval_request.explicit_locators`)."""
    max_query_terms: int = Field(ge=1)
    """Most search terms one retrieval query carries (goal first, then hints, then need filler)."""
    rerank_max_per_need: int = Field(ge=1)
    (
        "Candidates one rerank batch sends to Jev (`max_candidates` is the pool); with "
        "`jev.max_questions_per_call` at least this large a batch is one call."
    )
    rerank_max_batches: int = Field(ge=1)
    (
        "Batches one need may judge; further ones only until it has enough evidence "
        "(rerank_min_items)."
    )
    satisfied_min_items: int = Field(ge=1)
    (
        "A need is `satisfied` only with at least this many kept items at or above "
        "`coverage_relevance_threshold` ..."
    )
    satisfied_strong_threshold: Probability
    """... or with a single kept item whose relevance reaches this stronger bar."""
    self_reference_ratio: Probability
    (
        "A candidate repeating this share of the goal near-verbatim reviews the run asking, not "
        "evidence for it, and is demoted (0 disables this and the review test)."
    )
    self_reference_penalty: Probability
    """Factor on the relevance of a self-referencing candidate (cited ones are exempt)."""
    path_match_weight: int = Field(ge=0)
    """Score per rarity unit of each distinctive path word (a file NAMED after the topic)."""
    bm25_k1: float = Field(gt=0)
    """BM25 term-count saturation and length-normalisation strength (0 = none); orders only."""
    bm25_b: Probability
    (
        "Length-normalisation strength of the keyword ranking (0 none, 1 full); orders "
        "candidates only."
    )
    pool_sections_per_file: int = Field(ge=1)
    (
        "Sections of one file the FIRST rerank batch may hold (later pool places: "
        "sections_per_file)."
    )
    pool_fair_share: int = Field(ge=0)
    """Candidates per source guaranteed in the first batch if they score this share of the best."""
    pool_fair_min_ratio: Probability
    (
        "Share of the best score a source's candidate must reach to take a guaranteed place in "
        "the first rerank batch."
    )
    rerank_min_items: int = Field(ge=0)
    """A need judges more batches until this many items passed `relevance_threshold` ..."""
    rerank_stop_ratio: Probability
    """... and skips one when the best unjudged candidate scores below this share of the judged."""
    review_quote_ratio: Probability
    (
        "Goal share a document quotes (beside a run or trace id), or file-name marker, to review "
        "its run."
    )
    review_path_markers: list[str]
    """File-name markers that identify a review of a run rather than evidence for it."""
    registry_pin_min_terms: int = Field(ge=1)
    """A JSON registry is pinned when this many query words are names in its vocabulary."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Split out of config.py with a purpose on every retrieval field.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# ====================================================================
