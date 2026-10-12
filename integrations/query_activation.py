"""Independent native verifier behind explicit catalog-write authorization."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts import CapabilityInvocation, CapabilityResult
    from knowledge.query_admission import QueryAdmission
from kernel.contracts import CapabilityResult, ErrorInfo, ResultStatus, schema_ids
from kernel.contracts.query import QueryActivationRequest
from knowledge.errors import KnowledgeError

class QueryActivationExecutor:
    """Activate only through the trusted injected neutral admission service."""
    def __init__(self, admission: QueryAdmission | None) -> None:
        """Retain the composition-owned admission service.

        Args:
            admission: Trusted independent query verification service.
        """
        self.admission = admission

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: ExecutionContext) -> CapabilityResult:
        """Verify candidate execution before atomically persisting a reusable query.


        Args:
            invocation: Current registered invocation and persisted continuation.
            ctx: Trusted runtime scope, budgets and services.

        Returns:
            CapabilityResult: Verified receipt or explicit failure without a forged success.
        """
        request = QueryActivationRequest.model_validate(invocation.input_payload)
        if self.admission is None or request.repository_id != ctx.config.knowledge.repository_id:
            return self._failure(invocation, "permission_denied", "Catalog is unavailable or repository differs")
        try:
            receipt = await self.admission.verify_and_activate(request.candidate,
                repository_id=request.repository_id, source_sha=request.source_sha,
                expected_active_digest=request.expected_active_digest)
        except (KnowledgeError,ValueError) as exc:
            return self._failure(invocation, getattr(exc,"code","invalid_candidate"), str(exc))
        return CapabilityResult(invocation_id=invocation.id, work_item_id=invocation.work_item_id,
            status=ResultStatus.COMPLETED, output_schema_id=schema_ids.QUERY_ACTIVATION_RECEIPT,
            output_payload={"receipt": receipt})

    @staticmethod
    def _failure(invocation: CapabilityInvocation, code: str, message: str) -> CapabilityResult:
        """Return a typed failure to the waiting retrieval parent.


        Args:
            invocation: Current registered invocation and persisted continuation.
            code: Typed failure code.
            message: Observable failure explanation.

        Returns:
            CapabilityResult: Failed activation with explicit cause.
        """
        return CapabilityResult(invocation_id=invocation.id, work_item_id=invocation.work_item_id,
            status=ResultStatus.FAILED, error=ErrorInfo(code=code,message=message))
