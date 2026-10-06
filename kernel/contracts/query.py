"""Typed handoff and activation contracts for bounded query construction."""
from pydantic import Field, JsonValue
from kernel.contracts.base import KernelModel

class QueryBuildRequest(KernelModel):
    """A trusted missing-query need supplied to a coding host."""
    question: str = Field(min_length=1, max_length=8000)
    repository_id: str = Field(min_length=1)
    source_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    generation_id: str = Field(min_length=1)
    component_ids: list[str] = Field(min_length=1, max_length=20)
    need_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    available_queries: list[dict[str, JsonValue]] = Field(default_factory=list,max_length=50)
    remaining_budget: dict[str, JsonValue] = Field(default_factory=dict)
    expected_result: str = "Attributable canonical entities for the original evidence need"

class QueryCandidate(KernelModel):
    """Untrusted authored recipe; only the native verifier can admit it."""
    candidate: dict[str, JsonValue]

class QueryActivationRequest(KernelModel):
    """Candidate bound to the trusted repository and immutable source."""
    candidate: dict[str, JsonValue]
    repository_id: str = Field(min_length=1)
    source_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    component_ids: list[str] = Field(default_factory=list,max_length=20)
    expected_active_digest: str | None = None

class QueryActivationReceipt(KernelModel):
    """Verifier-produced receipt; never accepted directly from a coding host."""
    receipt: dict[str, JsonValue]
