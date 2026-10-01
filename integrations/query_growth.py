"""Checkpointed query selection, construction and admission behind registered retrieval."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any
    from collections.abc import Sequence
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts import CapabilityInvocation, CapabilityResult, Usage
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.ports import KnowledgeRetriever
    from knowledge.query_catalog import QueryCatalog
    from knowledge.query_admission import QueryAdmission
import asyncio
from integrations.query_contracts import activation_request
from integrations.query_planning import choose, waiting, clarification, build_request, human_scope
from kernel.capabilities.decision.jev_support import (StopCapability, blocked_result,
    load_output_payload, failed_result)
from kernel.contracts import CapabilityResult, ResultStatus, schema_ids
from knowledge.errors import KnowledgeError

async def _resume(invocation: CapabilityInvocation,ctx: ExecutionContext,state: dict[str, Any]) -> dict[str, Any]:
    """Read only the current wait's validated child output.


    Args:
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        state: Persisted query plan and bounded progress.

    Returns:
        dict: Current child's persisted output payload.
    """
    expected={"clarify":schema_ids.HUMAN_ANSWER,"building":schema_ids.QUERY_CANDIDATE,
              "admitting":schema_ids.QUERY_ACTIVATION_RECEIPT}[state["phase"]]
    children=[x for x in invocation.child_outcomes if x.current_wait and x.output_schema_id==expected]
    if len(children)!=1 or children[0].status is not ResultStatus.COMPLETED:
        raise KnowledgeError("build_failed","Required query continuation child did not complete")
    payload=load_output_payload(ctx,children[0])
    if payload is None:
        raise KnowledgeError("build_failed","Query child output is unavailable")
    return payload

async def _initial(port: KnowledgeRetriever,admission: QueryAdmission | None,invocation: CapabilityInvocation,ctx: ExecutionContext,payload: RetrievalRequestPayload) -> dict[str, Any]:
    """Pin source revision before any human or coding pause.


    Args:
        port: Application-owned neutral retrieval port.
        admission: Trusted independent query verification service.
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        payload: Validated original evidence request.

    Returns:
        dict: Trusted query state with original evidence need and source identity.
    """
    from integrations.knowledge_execution import _scoped_request
    capabilities=await asyncio.wait_for(port.capabilities(),timeout=3)
    _scoped_request(ctx,payload,capabilities)
    if not capabilities.get("graph"):
        raise KnowledgeError("unavailable","Graph retrieval is unavailable")
    revision=ctx.scope.revision.commit if ctx.scope.revision else "latest"
    pinned=await asyncio.wait_for(admission.pin(ctx.config.knowledge.repository_id,revision or "latest"),timeout=3)
    return {**pinned,"phase":"ready","question":payload.need.question,"need_id":payload.need.id,
            "component_ids":list(ctx.scope.component_ids),"clarifications":0,"build_attempted":False,
            "original_question":payload.need.question,"arguments":{},"planning_context":True}

async def _select(catalog: QueryCatalog,invocation: CapabilityInvocation,ctx: ExecutionContext,state: dict[str, Any]) -> tuple[str, dict, list[Usage]]:
    """Select among usable persisted descriptors or one explicit missing-query outcome.


    Args:
        catalog: Trusted persistent query catalog.
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        state: Persisted query plan and bounded progress.

    Returns:
        tuple: Selected option, descriptor map and usage.
    """
    descriptors={d["operation"]:d for d in catalog.descriptors()[:50]
                 if "graph" in d.get("modes",["graph"])}
    state["available_queries"]=list(descriptors.values())
    options={key:d["description"] for key,d in descriptors.items()}
    options.update(build="None of these queries can answer; build a bounded reusable query.",
                   clarify="The question or required arguments remain unclear.",
                   skip="Existing evidence is sufficient; no retrieval needed.")
    picked,usage=await choose(ctx,invocation,"knowledge.query_select","query",
        {"question":state["question"],"component_ids":state["component_ids"],
         "catalog":list(descriptors.values())},options)
    state["selection_reason"]="Jev selected "+picked+" from the verified scoped query catalog"
    return picked,descriptors,usage

def _arguments(descriptor: dict[str, Any],state: dict[str, Any]) -> dict:
    """Bind known IDs only; missing scalar parameters remain an explicit limitation.


    Args:
        descriptor: Verified selected operation metadata.
        state: Persisted query plan and bounded progress.

    Returns:
        dict: Typed seed argument mapping derived from established scope.
    """
    parameters=descriptor.get("parameters",{})
    args=dict(state.get("arguments",{}))
    for name,spec in parameters.items():
        if name in args:
            continue
        if name in {"component_ids","entity_ids"} and spec.get("type")=="string_list":
            args[name]=state["component_ids"]
        elif name=="component_id" and spec.get("type")=="string":
            args[name]=state["component_ids"][0]

    for name,spec in parameters.items():
        value=args.get(name)
        if spec.get("type")=="string_list" and value is not None:
            if not isinstance(value,list) or not set(value)<=set(state["component_ids"]):
                raise KnowledgeError("scope_mismatch","Query seed arguments cannot broaden clarified scope")
        if name=="component_id" and value is not None and value not in state["component_ids"]:
            raise KnowledgeError("scope_mismatch","Query component argument cannot broaden clarified scope")
    return args

async def _execute(port: KnowledgeRetriever,catalog: QueryCatalog,invocation: CapabilityInvocation,ctx: ExecutionContext,payload: RetrievalRequestPayload,source_ids: set[str],state: dict[str, Any],descriptor: dict[str, Any],usage: Sequence[Usage]) -> CapabilityResult:
    """Execute the digest-pinned selected query through existing bounded evidence mapping.


    Args:
        port: Application-owned neutral retrieval port.
        catalog: Trusted persistent query catalog.
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        payload: Validated original evidence request.
        source_ids: Authorized source identities for the evidence result.
        state: Persisted query plan and bounded progress.
        descriptor: Verified selected operation metadata.
        usage: Already measured provider usage for this invocation.

    Returns:
        CapabilityResult: Original need's canonical evidence result.
    """
    from integrations.knowledge_execution import invoke_knowledge
    arguments=_arguments(descriptor,state)
    missing=[name for name,spec in descriptor.get("parameters",{}).items()
             if spec.get("required",False) and name not in arguments]
    if missing:
        state["pending_descriptor"]=descriptor
        return clarification(invocation,ctx,state,usage)
    raw={"operation":descriptor["operation"],"operation_version":descriptor.get("version","1"),
         "operation_digest":descriptor["digest"],"mode":"graph", "arguments":arguments,
         "revision":state["source_sha"],"disclosure_level":{"locator":0,"summary":2,"excerpt":3}[payload.detail]}
    result=await invoke_knowledge(port,invocation,ctx,payload.model_copy(update={"knowledge":raw,
        "need":payload.need.model_copy(update={"question":state["question"]})}),
                                  source_ids,query_catalog=catalog)
    result=result.model_copy(update={"usage":[*usage,*result.usage]})
    result.diagnostics.update(query_operation=raw["operation"],query_digest=raw["operation_digest"],
        query_original_question=state.get("original_question",payload.need.question),
        query_effective_question=state["question"],
        query_selection_reason=state.get("selection_reason","Verified construction for the original missing query"))
    return result

async def _continued(port: KnowledgeRetriever, catalog: QueryCatalog,
                     invocation: CapabilityInvocation, ctx: ExecutionContext,
                     payload: RetrievalRequestPayload, source_ids: set[str],
                     state: dict[str, Any], usage: list[Usage]) -> dict[str, Any] | CapabilityResult:
    """Consume one completed child while preserving the research's exact pins.

    Args:
        port: Application-owned retrieval port.
        catalog: Verified persistent query catalog.
        invocation: Current invocation and its completed children.
        ctx: Trusted runtime scope and artifact access.
        payload: Original evidence request.
        source_ids: Authorized source identities.
        state: Pinned research continuation.
        usage: Current invocation's provider usage.

    Returns:
        dict[str, Any] | CapabilityResult: Updated plan, next wait or final evidence.
    """
    phase=state["phase"]
    child=await _resume(invocation,ctx,state)
    if phase=="clarify":
        state=human_scope(child,ctx,state)
        if state.get("pending_descriptor"):
            return await _execute(port,catalog,invocation,ctx,payload,source_ids,state,
                                  state["pending_descriptor"],usage)
    elif phase=="building":
        from knowledge.query_models import QueryCandidate
        from knowledge.query_compile import digest_data
        candidate=child["candidate"]
        authored=QueryCandidate.model_validate(candidate)
        state.update(phase="admitting",candidate_operation=authored.descriptor.operation,
                     candidate_version=authored.descriptor.version,candidate_digest=authored.descriptor.digest,
                     candidate_artifact_digest=digest_data(authored.model_dump()))
        return waiting(invocation,state,activation_request(candidate=candidate,
            repository_id=state["repository_id"],source_sha=state["source_sha"],
            component_ids=state["component_ids"]))
    else:
        receipt=child["receipt"]
        if (receipt.get("status")!="activated" or receipt.get("repository_id")!=state["repository_id"]
            or receipt.get("source_sha")!=state["source_sha"] or receipt.get("generation_id")!=state["generation_id"]
            or receipt.get("operation")!=state["candidate_operation"]
            or receipt.get("version")!=state["candidate_version"]
            or receipt.get("digest")!=state["candidate_digest"]
            or receipt.get("candidate_digest")!=state["candidate_artifact_digest"]):
            raise KnowledgeError("scope_mismatch","Query activation receipt does not match waiting research")
        descriptor=catalog.get(receipt["operation"],receipt["version"],receipt["digest"])
        data=descriptor.model_dump(mode="json") if hasattr(descriptor,"model_dump") else dict(descriptor)
        data["digest"]=receipt["digest"]
        return await _execute(port,catalog,invocation,ctx,payload,source_ids,state,data,usage)
    return state

async def _advance(port: KnowledgeRetriever,catalog: QueryCatalog,admission: QueryAdmission | None,invocation: CapabilityInvocation,ctx: ExecutionContext,payload: RetrievalRequestPayload,source_ids: set[str]) -> CapabilityResult:
    """Advance exactly one phase, preserving state across all external interactions.


    Args:
        port: Application-owned neutral retrieval port.
        catalog: Trusted persistent query catalog.
        admission: Trusted independent query verification service.
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        payload: Validated original evidence request.
        source_ids: Authorized source identities for the evidence result.

    Returns:
        CapabilityResult: A wait, bounded evidence result, or explicit stopping reason.
    """
    state=dict(invocation.continuation.state) if invocation.continuation else await _initial(
        port,admission,invocation,ctx,payload)
    usage=[]
    phase=state["phase"]
    if phase in {"clarify","building","admitting"}:
        resumed=await _continued(port,catalog,invocation,ctx,payload,source_ids,state,usage)
        if isinstance(resumed,CapabilityResult):
            return resumed
        state=resumed
    if phase=="ready":
        picked,usage=await choose(ctx,invocation,"knowledge.query_readiness","readiness",
            {"question":state["question"],"component_ids":state["component_ids"]},
            {"ready":"The question and intended scope are clear.","clarify":"Ask for missing scope or intent."})
        if picked=="clarify" or not state["component_ids"]:
            return clarification(invocation,ctx,state,usage)
    if state.get("planning_context") and not state.get("target_kind"):
        from knowledge.query_models import KINDS
        target,target_usage=await choose(ctx,invocation,"knowledge.query_target","kind",
            {"question":state["question"],"supported_source_kinds":state.get("supported_kinds",[])},
            {**{kind:"The requested answer consists of "+kind+" entities." for kind in sorted(KINDS)},
             "clarify":"The requested result kind is unclear."})
        usage+=target_usage
        if target=="clarify":
            return clarification(invocation,ctx,state,usage)
        state["target_kind"]=target
        if target not in state.get("supported_kinds",[]):
            return blocked_result(invocation,"source_mapping_unsupported",
                "The pinned source does not map requested "+target+" data; a query cannot create that data.",usage=usage)
    picked,descriptors,selected_usage=await _select(catalog,invocation,ctx,state)
    usage+=selected_usage
    if picked=="clarify":
        return clarification(invocation,ctx,state,usage)
    if picked=="build":
        if state["build_attempted"]:
            return blocked_result(invocation,"build_exhausted","One query construction attempt already completed")
        from knowledge.contracts import RetrievalBudget
        state.update(phase="building",build_attempted=True,remaining_budget={
            "construction_attempts_remaining":0,
            "clarifications_remaining":max(0,ctx.config.intent.max_clarifications-state["clarifications"]),
            "retrieval":RetrievalBudget().model_dump(mode="json"),
            "host_budget_remaining":None,"host_budget_policy":"Existing scheduler reserves before dispatch"})
        return waiting(invocation,state,build_request(invocation,state),usage)
    if picked=="skip":
        return blocked_result(invocation,"retrieval_not_needed","No additional query selected",usage=usage)
    return await _execute(port,catalog,invocation,ctx,payload,source_ids,state,descriptors[picked],usage)

async def invoke_query_growth(port: KnowledgeRetriever,catalog: QueryCatalog,admission: QueryAdmission | None,invocation: CapabilityInvocation,ctx: ExecutionContext,payload: RetrievalRequestPayload,source_ids: set[str]) -> CapabilityResult:
    """Contain typed query-growth failures without turning outages into construction.


    Args:
        port: Application-owned neutral retrieval port.
        catalog: Trusted persistent query catalog.
        admission: Trusted independent query verification service.
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        payload: Validated original evidence request.
        source_ids: Authorized source identities for the evidence result.

    Returns:
        CapabilityResult: Existing kernel lifecycle result.
    """
    try:
        return await _advance(port,catalog,admission,invocation,ctx,payload,source_ids)
    except StopCapability as exc:
        return exc.result
    except (KnowledgeError,ValueError,KeyError,TimeoutError) as exc:
        return failed_result(invocation,getattr(exc,"code","query_growth_invalid"),str(exc))
