"""Typed handoff and activation contracts for bounded query construction."""
from pydantic import Field, JsonValue
from kernel.contracts.base import KernelModel

class QueryBuildRequest(KernelModel):
    """A trusted missing-query need supplied to a coding host."""
    question: str = Field(min_length=1, max_length=8000)
    """The evidence question no existing query could answer."""
    repository_id: str = Field(min_length=1)
    """Repository the new query is for."""
    source_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    """Immutable commit the query is authored and checked against."""
    generation_id: str = Field(min_length=1)
    """Immutable generation of the repository knowledge graph the query will run against."""
    component_ids: list[str] = Field(min_length=1, max_length=20)
    """Components the query may read."""
    need_id: str = Field(min_length=1)
    """The evidence need that found no query."""
    attempt_id: str = Field(min_length=1)
    """Id of this authoring attempt, so retries are told apart."""
    available_queries: list[dict[str, JsonValue]] = Field(default_factory=list,max_length=50)
    """Queries that already exist, so the host reuses rather than duplicates them."""
    remaining_budget: dict[str, JsonValue] = Field(default_factory=dict)
    """What the host may still spend on authoring, so it stays within limits."""
    expected_result: str = "Attributable canonical entities for the original evidence need"
    """What a good query should return, as a check for the author."""

class QueryCandidate(KernelModel):
    """Untrusted authored recipe; only the native verifier can admit it."""
    candidate: dict[str, JsonValue]
    """The authored query recipe; untrusted until the native verifier admits it."""

class QueryActivationRequest(KernelModel):
    """Candidate bound to the trusted repository and immutable source."""
    candidate: dict[str, JsonValue]
    """The recipe to verify and activate."""
    repository_id: str = Field(min_length=1)
    """Repository the recipe is bound to."""
    source_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    """Immutable commit the recipe is verified against."""
    component_ids: list[str] = Field(default_factory=list,max_length=20)
    """Components the recipe is allowed to read."""
    expected_active_digest: str | None = None
    (
        "Digest of the active query this recipe replaces; required when replacing, so a "
        "concurrent change is detected."
    )

class QueryActivationReceipt(KernelModel):
    """Verifier-produced receipt; never accepted directly from a coding host."""
    receipt: dict[str, JsonValue]
    """The verifier's proof that the recipe was admitted; never accepted from a coding host."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Field purposes added so the query-building schemas explain
#   themselves to the coding host. (#TICKET-20261009-KernelContractFieldDescriptions)
# ====================================================================
