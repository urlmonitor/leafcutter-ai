"""
MODULE: kernel.bootstrap
GOAL: The composition root: load config and secrets, verify and pin the capability registry,
    build the trusted BindingTable, the file stores, the redactor, the tracer and the Jev factory
    into one KernelEnvironment that the application service runs against.
BUSINESS CONTEXT: Every other module depends on ports; exactly one place may know which concrete
    class serves which binding key, which credentials exist and where runs live on disk (Rev 3
    sections 5.1 and 13). Keeping that here lets tests swap any piece without touching the service.
ARCHITECTURE: `build_environment` is synchronous and does no network IO. The Jev adapter owns a
    pooled HTTP client bound to an event loop, so the environment stores a *factory*: the service
    calls it inside the run's loop and closes the adapter in the same loop. The tracer is ONE
    instance shared by the scheduler runtime and the Jev adapter, so generations nest under the
    same segment. Host bindings are HostOperationExecutors: they compile packets and convert results
    but never run work (the scheduler opens an interaction instead).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from knowledge.ports import KnowledgeRetriever
    from knowledge.query_catalog import QueryCatalog
    from knowledge.query_admission import QueryAdmission


import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import kernel
from knowledge.config import build_retriever
from knowledge.ports import KnowledgeRetriever
from kernel.capabilities.decision import DecisionExecutor
from kernel.capabilities.host import HostBindingExecuted as HostBindingExecuted
from kernel.capabilities.host import HostOperationExecutor
from kernel.capabilities.research import ResearchExecutor
from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.config import KernelConfig, load_kernel_config, repo_root
from kernel.capabilities.base import CapabilityExecutor
from kernel.contracts import ExecutionMode, RegistrySnapshot
from kernel.memory.backend import build_memory
from kernel.memory.port import ColonyMemory, NullColonyMemory
from kernel.observability.langfuse_tracer import LangfuseTracer
from kernel.observability.redaction import Redactor
from kernel.observability.tracer import Tracer
from kernel.persistence import FileArtifactStore, FileGapStore, FileRunStore
from kernel.providers.base import JevPort
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.registry import BindingTable
from kernel.registry.adapter import load_component_ids, load_registry
from kernel.secrets import SecretSettings, load_secrets

logger = logging.getLogger(__name__)

#: Native bindings and the version each executor implements (registry `binding` -> factory).
NATIVE_BINDINGS: dict[str, Callable[[], CapabilityExecutor]] = {
    "decision": DecisionExecutor,
    "research": ResearchExecutor,
    "retrieve.repository": RepositoryRetrievalExecutor,
}
NATIVE_VERSION = "1.0.0"
TELEMETRY_SPOOL = "telemetry_spool.jsonl"


#: Kept under its P7 name: every host_handoff binding is a HostOperationExecutor since P8.
HostMarkerExecutor = HostOperationExecutor


@dataclass
class KernelEnvironment:
    """Everything one service instance needs; built once per process.

    Attributes:
        config: Validated kernel configuration.
        secrets: Loaded credentials (presence booleans only; never printed).
        snapshot: The verified registry snapshot a new run pins.
        bindings: Trusted executor factories.
        repo_root: Root of the kernel checkout (relative config paths resolve against it).
        run_root: Directory holding runs, the checkpoint database and the telemetry spool.
        run_store: File run store.
        gap_store: File gap store.
        artifacts: File artifact store.
        tracer: The single tracer instance shared with the Jev adapter.
        redactor: Masks secrets in packets before they leave the kernel.
        jev_factory: Builds the Jev port inside the running event loop; None when no credential
            is configured (runs that need Jev then report provider_unavailable).
        memory: The approved-decision memory (file store or null, from `memory.backend`).
    """

    config: KernelConfig
    secrets: SecretSettings
    snapshot: RegistrySnapshot
    bindings: BindingTable
    repo_root: Path
    run_root: Path
    run_store: FileRunStore
    gap_store: FileGapStore
    artifacts: FileArtifactStore
    tracer: Tracer
    redactor: Redactor
    jev_factory: Callable[[], JevPort] | None
    knowledge_retriever: KnowledgeRetriever | None = None
    memory: ColonyMemory = field(default_factory=NullColonyMemory)

    async def aclose(self) -> None:
        """Await owned knowledge resources and stop the tracer for an async host."""
        closer = getattr(self.knowledge_retriever, "close", None)
        try:
            if closer is not None:
                await closer()
        finally:
            stop = getattr(self.tracer, "shutdown", None)
            if callable(stop):
                stop()

    def shutdown(self) -> None:
        """Close resources after the run loop ends; async hosts await aclose instead."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.aclose())
            return
        message = "An async host must await environment.aclose() before ending its loop"
        raise RuntimeError(message)


@dataclass
class EnvironmentOverrides:
    """Test seams: any piece set here replaces the production wiring."""

    knowledge_retriever: KnowledgeRetriever | None = None
    query_catalog: object | None = None
    query_admission: object | None = None
    tracer: Tracer | None = None
    jev_factory: Callable[[], JevPort] | None = None
    bindings: BindingTable | None = None
    snapshot: RegistrySnapshot | None = None
    secrets: SecretSettings | None = None
    memory: ColonyMemory | None = None


def resolve_run_root(config: KernelConfig, root: Path) -> Path:
    """Return the run root from config: absolute as given, else relative to the repo root.

    Args:
        config: Input to the documented operation.
        root: Input to the documented operation.

    Returns:
        Path: Result of the documented contract operation.
    """
    configured = Path(config.paths.run_root)
    return configured if configured.is_absolute() else (root / configured).resolve()


def build_bindings(snapshot: RegistrySnapshot, *, knowledge_retriever: KnowledgeRetriever | None = None,
                   query_catalog: QueryCatalog | None=None, query_admission: QueryAdmission | None=None) -> BindingTable:
    """Return the trusted table: native executors plus one host operation per host descriptor.

    Args:
        snapshot: Verified capability registry snapshot.

    Returns:
        BindingTable: Result of the documented operation.
    """
    from integrations.query_activation import QueryActivationExecutor
    table = BindingTable()
    table.register("knowledge.activate_query", NATIVE_VERSION,
                   partial(QueryActivationExecutor, query_admission))
    for key, factory in NATIVE_BINDINGS.items():
        table.register(key, NATIVE_VERSION, factory)
    if knowledge_retriever is not None:
        from integrations.knowledge_capability import KnowledgeRetrievalExecutor
        table.register("retrieve.repository", NATIVE_VERSION,
                       partial(KnowledgeRetrievalExecutor, knowledge_retriever,
                                 query_catalog=query_catalog,query_admission=query_admission))
    for descriptor in snapshot.descriptors:
        if descriptor.execution_mode is ExecutionMode.HOST_HANDOFF:
            table.register(descriptor.binding, descriptor.version,
                           partial(HostOperationExecutor, descriptor.id))
    return table


def load_snapshot(config: KernelConfig, root: Path) -> RegistrySnapshot:
    """Load and verify the registry named by config (components are checked when known).

    Args:
        config: Input to the documented operation.
        root: Input to the documented operation.

    Returns:
        RegistrySnapshot: Result of the documented contract operation.
    """
    components = root / "docs" / "components.json"
    known = load_component_ids(components) if components.is_file() else None
    registry = Path(config.paths.registry)
    return load_registry(registry if registry.is_absolute() else root / registry,
                         known_components=known)


def _jev_factory(config: KernelConfig, secrets: SecretSettings, tracer: Tracer
                 ) -> Callable[[], JevPort] | None:
    """Return the factory of the live Jev adapter, or None without an API key.

    Args:
        config: Input to the documented operation.
        secrets: Input to the documented operation.
        tracer: Input to the documented operation.

    Returns:
        Callable[[], JevPort] | None: Result of the documented contract operation.
    """
    if secrets.jev_api_key is None:
        return None
    key = secrets.jev_api_key.get_secret_value()
    return lambda: TypeSafeJevAdapter.from_config(config, key, tracer=tracer)


def build_environment(*, config_path: Path | None = None, env_file: Path | None = None,
                      overrides: EnvironmentOverrides | None = None) -> KernelEnvironment:
    """Compose the production environment (no network IO).

    Args:
        config_path: Config override file (else LEAFCUTTER_KERNEL_CONFIG, else defaults only).
        env_file: Env file with credentials (else LEAFCUTTER_ENV_FILE, then a walked-up .env).
        overrides: Test seams replacing the tracer, Jev factory, bindings, snapshot or secrets.

    Returns:
        KernelEnvironment: Ready for KernelService.

    Raises:
        ConfigError: The config is unreadable or invalid.
        RegistryError: The registry is unreadable or invalid.
    """
    seams = overrides or EnvironmentOverrides()
    root = repo_root()
    config = load_kernel_config(config_path)
    secrets = seams.secrets if seams.secrets is not None else load_secrets(env_file)
    run_root = resolve_run_root(config, root)
    snapshot = seams.snapshot or load_snapshot(config, root)
    deny = list(config.retrieval.deny_globs)
    tracer = seams.tracer or LangfuseTracer(
        secrets=secrets, config=config.langfuse, policy=config.data_policy, deny_globs=deny,
        spool_path=run_root / TELEMETRY_SPOOL, release=kernel.__version__)
    factory = seams.jev_factory or _jev_factory(config, secrets, tracer)
    knowledge = seams.knowledge_retriever or build_retriever(config.knowledge)
    from knowledge.query_admission import build_query_admission
    admission = seams.query_admission or build_query_admission(config.knowledge,knowledge)
    catalog = seams.query_catalog or (admission.catalog if admission is not None else None)
    return KernelEnvironment(
        config=config, secrets=secrets, snapshot=snapshot,
        bindings=seams.bindings or build_bindings(snapshot, knowledge_retriever=knowledge,
            query_catalog=catalog,query_admission=admission), repo_root=root, run_root=run_root,
        run_store=FileRunStore(run_root), gap_store=FileGapStore(run_root),
        artifacts=FileArtifactStore(run_root), tracer=tracer,
        redactor=Redactor(secrets.secret_values(), config.data_policy, deny), jev_factory=factory,
        knowledge_retriever=knowledge,
        memory=seams.memory or build_memory(config.memory, root, run_root))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The memory backend is chosen here from `memory.backend` (file or
#   null), so the kernel stays unaware of the store. (#KernelDecisionStore)
# - 2026-10-01 10:40 [python-coder]: The environment holds a Jev *factory*, not an adapter: the
#   adapter's pooled client is bound to one event loop and must be created and closed in the
#   loop that runs the graph. (#KernelBootstrapV0/P7)
# - 2026-10-01 11:50 [python-coder]: Host bindings are HostOperationExecutors keyed by the
#   descriptor id (an unknown id gets the generic operation); `HostMarkerExecutor` stays as an
#   alias of the P7 name and `HostBindingExecuted` is re-exported. (#KernelBootstrapV0/P8)
# - 2026-10-01 10:40 [python-coder]: Host placeholders are derived from the registry's
#   host_handoff descriptors (not a hard-coded id list), so a new host capability needs only a
#   registry entry until P8 gives it an operation. (#KernelBootstrapV0/P7)
# ====================================================================

# - 2026-10-01 20:00 [python-coder]: Bind optional knowledge through existing scoped retrieval contracts. (#TICKET-20261001-KM-400e-3)
