"""
MODULE: build_phases_deploy_failures
GOAL: Accumulate every declared deploy entry whose source file was missing
    during one build run, and fail the build closed once, at the end, with
    the whole set named.
BUSINESS CONTEXT: A deploy phase declares the files it ships (e.g.
    ``AC_STORE_DEPLOY_MAP``, ``AGENT_SUPPORT_SCRIPT_DIRS``). When a declared
    source is absent, the honest outcome is a failed build -- a build that
    completes while silently omitting a declared file reports a consumer
    install that was never produced, and the omission only surfaces later as
    a ``ModuleNotFoundError`` from a deployed hook. BP-900g-9 made every
    deploy loop fail closed by recording here and continuing, so ONE build
    names the whole remediation set instead of one entry per build-fix-build
    cycle.
ARCHITECTURE: A module-level list plus five functions over it.
    ``record_deploy_failure`` appends; ``get_deploy_failures`` returns a copy;
    ``reset_deploy_failures`` clears it between runs (notably between tests in
    one process); ``raise_if_deploy_failures`` raises
    :class:`DeployDeclarationError` carrying every record, or does nothing
    when the run found none.

    WHY THIS IS A SIBLING MODULE RATHER THAN PART OF build_phases.py.
    Every phase module records through a function-scoped
    ``import build_phases as _bp`` -> ``_bp.record_deploy_failure(...)``, and
    that bare-name import always resolves to the ONE ``build_phases`` in
    ``sys.modules``. ``build_helpers._load_build_phases_module()`` also loads
    ``build_phases.py`` by PATH under a synthetic name. Had the registry
    stayed a global of ``build_phases.py``, that by-path copy would own a
    SEPARATE, always-empty list while the phases it invoked recorded into the
    bare module's -- so ``fresh_mod.get_deploy_failures()`` would answer ``[]``
    for a run that really did drop files. Keeping the single registry in a
    module that is only ever imported by bare name makes the writer and the
    reader agree no matter which ``build_phases`` object the caller holds.
    ``build_phases`` re-exports all five names, so every existing call site
    (``build.py``, ``unit_tests/test_bp_900g_9.py``) is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeployFailure:
    """One declared deploy entry whose source file was not found.

    Accumulating records rather than logging strings is what makes "report
    every entry, not only the first" implementable and testable: a log line is
    gone once emitted, a record can be counted and asserted on.

    Attributes:
        phase: The deploy phase that declared the entry (e.g. ``build_ac_store``),
            so the author knows which declaration to edit.
        entry: The declaration entry as written, so it can be located in the
            map without guessing.
        source_path: The source path that was not found.
    """

    phase: str
    entry: str
    source_path: str


class DeployDeclarationError(Exception):
    """One or more declared deploy entries had no source file.

    Raised ONCE, after every deploy phase has run, carrying the whole
    accumulated set. Raising per-entry would turn N stale entries into N
    build-fix-build cycles with a green build between each one, so an author
    who stops at the first green ships the remaining N-1.

    Args:
        failures: Every unresolvable declared entry found during the run.
    """

    def __init__(self, failures: list[DeployFailure]) -> None:
        self.failures = list(failures)
        detail = "\n".join(
            f"  - {f.phase}: declared entry '{f.entry}' has no source at "
            f"{f.source_path}"
            for f in self.failures
        )
        super().__init__(
            f"{len(self.failures)} declared deploy "
            f"{'entry' if len(self.failures) == 1 else 'entries'} could not be "
            f"resolved to a source file:\n{detail}\n"
            "A build that completes while silently omitting a declared file "
            "reports a consumer install that was never produced. Either deploy "
            "the source, or remove the entry from its declaration."
        )


# Accumulated across ALL deploy phases of one run, so a single build reports
# the whole remediation set. build.py resets this before the phases run and
# raises on it afterwards, mirroring build_phases._uptodate_count's idiom.
_deploy_failures: list[DeployFailure] = []


def reset_deploy_failures() -> None:
    """Clear the accumulated declared-deploy failures.

    Must be called before the build phases run so consecutive invocations in
    one process (notably the test suite) do not inherit each other's findings.
    """
    _deploy_failures.clear()


def record_deploy_failure(phase: str, entry: str, source_path: Path | str) -> None:
    """Record a declared deploy entry whose source file was not found.

    Callers continue iterating after calling this — the point is to reach the
    end of the declaration and report every unresolvable entry at once.

    Args:
        phase: Name of the declaring deploy phase.
        entry: The declaration entry as written.
        source_path: The path that was not found.
    """
    _deploy_failures.append(
        DeployFailure(phase=phase, entry=entry, source_path=str(source_path))
    )


def get_deploy_failures() -> list[DeployFailure]:
    """Return the declared-deploy failures accumulated so far this run."""
    return list(_deploy_failures)


def raise_if_deploy_failures() -> None:
    """Raise :class:`DeployDeclarationError` when any declared entry was unresolvable.

    A no-op when the run found none — "nothing to ship" and "everything
    shipped" are both success; only "something was promised and dropped" is a
    failure.

    Raises:
        DeployDeclarationError: Carrying every accumulated record.
    """
    if _deploy_failures:
        raise DeployDeclarationError(_deploy_failures)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved the BP-900g-9 declared-deploy
#   failure registry (DeployFailure, DeployDeclarationError, _deploy_failures,
#   reset_deploy_failures, record_deploy_failure, get_deploy_failures,
#   raise_if_deploy_failures) verbatim out of build_phases.py into this new
#   sibling module, as part of the split that brought build_phases.py under the
#   400-counted-line check-file-size limit. Beyond the line budget this also
#   fixes an isolation inconsistency the split would otherwise introduce: the
#   phase modules record through a bare-name `import build_phases as _bp`, so a
#   registry left as a global of build_phases.py would have been invisible to
#   build_helpers's by-path copy of that module (see this module's ARCHITECTURE
#   docstring). All five names are re-exported from build_phases.py, so build.py
#   and unit_tests/test_bp_900g_9.py are unchanged.
#   (#refactor/build-phases-size-limit)
# ====================================================================
