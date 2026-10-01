"""
MODULE: kernel.capabilities.host.registry
GOAL: Look up the host operation of a capability id and the template versions to record on an
    invocation.
BUSINESS CONTEXT: Exactly one module serves each `host.*` capability, and the set is fixed in
    code: a registry entry cannot make the kernel run or convert anything it has no operation for
    (Rev 3 section 13.3, allowlisted bindings). An unknown host capability still gets a packet,
    built by the generic template, but its result is not converted.
ARCHITECTURE: A constant table built from the four operation classes. Pure lookups; nothing is
    registered at runtime.
"""

from __future__ import annotations

from kernel.capabilities.host.base import GenericHostOperation, HostOperation
from kernel.capabilities.host.formulate_question import FormulateQuestion
from kernel.capabilities.host.generate_options import GenerateOptions
from kernel.capabilities.host.research import Research
from kernel.capabilities.host.spec import TEMPLATE_VERSION
from kernel.capabilities.host.synthesize import Synthesize

OPERATIONS: dict[str, HostOperation] = {
    op.capability_id: op for op in (GenerateOptions(), Synthesize(), Research(),
                                    FormulateQuestion())}
GENERIC = GenericHostOperation()
TEMPLATE_VERSION_KEY = "host_template"


def host_operation(capability_id: str) -> HostOperation | None:
    """Return the operation serving a capability id, or None when there is none."""
    return OPERATIONS.get(capability_id)


def compiler_for(capability_id: str) -> HostOperation:
    """Return the operation that compiles a packet for the capability (generic if unknown)."""
    return OPERATIONS.get(capability_id, GENERIC)


def template_versions(capability_id: str) -> dict[str, str]:
    """Return the version-map entry recording the packet template (empty for unknown ids)."""
    op = OPERATIONS.get(capability_id)
    return {TEMPLATE_VERSION_KEY: f"{op.template_id}@{TEMPLATE_VERSION}"} if op else {}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:40 [python-coder]: The operation table is code, not registry data: the registry
#   declares what a capability accepts and produces, while only this table decides what the
#   kernel compiles and converts. (#KernelBootstrapV0/P8)
# ====================================================================
