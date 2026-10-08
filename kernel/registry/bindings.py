"""
MODULE: kernel.registry.bindings
GOAL: The trusted binding table that maps (binding key, version) to executor factories.
BUSINESS CONTEXT: Implementation bindings resolve only through trusted application
    registration; a name returned by Jev or found in a document must never be imported or run
    (Rev 3 section 7.5).
ARCHITECTURE: Only the composition root (bootstrap, P7) and tests populate the table. Registry
    `binding` fields are keys into it, never import paths.
"""

from __future__ import annotations

from collections.abc import Callable

from kernel.capabilities.base import CapabilityExecutor

ExecutorFactory = Callable[[], CapabilityExecutor]


class BindingUnavailable(LookupError):
    """No executor is registered for the requested binding key and version."""

    def __init__(self, key: str, version: str) -> None:
        """Build the message from the key and version."""
        super().__init__(f"no executor bound for {key}@{version}")
        self.key = key
        self.version = version


class BindingTable:
    """Trusted table of executor factories keyed by (binding key, version)."""

    def __init__(self) -> None:
        """Create an empty table."""
        self._factories: dict[tuple[str, str], ExecutorFactory] = {}

    def register(self, key: str, version: str, factory: ExecutorFactory) -> None:
        """Register a factory; re-registering the same key and version replaces it.

        Args:
            key: Binding key used in registry entries.
            version: Semver the factory implements.
            factory: Zero-argument callable returning a CapabilityExecutor.
        """
        self._factories[(key, version)] = factory

    def has(self, key: str, version: str) -> bool:
        """Return True if an executor is registered for key at version."""
        return (key, version) in self._factories

    def resolve(self, key: str, version: str) -> CapabilityExecutor:
        """Build the executor for key at version.

        Args:
            key: Binding key.
            version: Pinned capability version.

        Returns:
            CapabilityExecutor: A new executor instance.

        Raises:
            BindingUnavailable: Nothing is registered for this key and version.
        """
        factory = self._factories.get((key, version))
        if factory is None:
            raise BindingUnavailable(key, version)
        return factory()

    def keys(self) -> list[tuple[str, str]]:
        """Return the registered (key, version) pairs in sorted order."""
        return sorted(self._factories)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Factories (not instances) are stored so each invocation
#   can get fresh executor state. (#KernelBootstrapV0/P1)
# ====================================================================
