#!/usr/bin/env python3
"""
MODULE: _gtfa_seams
GOAL: Give every ``_gtfa_*`` sibling a late-bound handle on the
    ``generate_ticket_from_ac`` shell module, so that the handful of names a
    test patches (or a module-level reload rebinds) keep resolving through the
    shell rather than through a frozen from-import binding.
BUSINESS CONTEXT: ``generate_ticket_from_ac`` was one 4035-line module. Its
    test suites reach into it as a single namespace — patching an attribute on
    the module object, asserting on log records emitted under the module's own
    logger name, and reloading the module to re-run its module-level
    initialisation. Splitting the file across siblings must not quietly break
    any of those, because each one fails in the direction of a green test over
    dead code: a patch that lands on an attribute nobody reads, or a log
    assertion against a logger nobody writes to, both look like a pass.
ARCHITECTURE: A sibling never imports the shell at module scope (that would be
    circular). Instead the shell calls :func:`bind_shell` on itself immediately
    after importing its siblings, and siblings call :func:`shell` at CALL time.
    Binding the module OBJECT rather than copying its attributes is the whole
    point: attribute lookup is deferred to the moment of use, which is what
    makes ``unittest.mock.patch`` on a shell attribute take effect inside a
    sibling.

    This module is deliberately duplicated per import layout, and that is
    correct rather than accidental. A process can hold BOTH
    ``generate_ticket_from_ac`` (bare, after a ``sys.path`` insert) and
    ``scripts.ac_store.generate_ticket_from_ac`` (dotted) — the repo's tests
    use both. Each shell imports its own sibling set under its own package
    prefix, so each set gets its own ``_gtfa_seams`` with its own binding, and
    the two layouts can never cross-talk.

The three seams, and why each one has to be late-bound:

* ``_find_worktree_root`` — ``unit_tests/ac_store/test_tkt_500f_17.py`` does
  ``patch("generate_ticket_from_ac._find_worktree_root", ...)`` and then drives
  ``main()``. Four different siblings reach the root resolver on that code
  path (config lookup, components.json lookup, the prose path-existence gate,
  and root resolution in ``main`` itself). A from-import in any one of them
  would silently ignore the patch.
* ``_COMPONENT_MIGRATION_MAP`` — assigned in the SHELL's module body so that
  ``importlib.reload(shell)`` re-runs it, which
  ``unit_tests/ac_store/test_tkt_500f_18_i.py`` requires. Consumers therefore
  have to read the shell's current value, not a copy taken at their own import.
* the logger name — ``test_tkt_500f_18_i`` asserts with
  ``assertNoLogs(logger=_gen_module.__name__)`` and ``test_tkt_500f_17`` with
  ``assertLogs("generate_ticket_from_ac")``. A sibling logging under its own
  ``__name__`` would emit records neither assertion can see.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

#: Unqualified name of the shell module these siblings belong to.
_SHELL_BASENAME = "generate_ticket_from_ac"

#: The shell module object, set by :func:`bind_shell`. Module-global rather
#: than a parameter threaded through every sibling because the binding is a
#: property of the import layout, not of any single call.
_bound_shell: ModuleType | None = None


def shell_module_name() -> str:
    """Return the fully-qualified name of this layout's shell module.

    Derived from this module's own ``__name__`` so the answer always matches
    the layout the sibling set was imported under: ``_gtfa_seams`` (bare) gives
    ``generate_ticket_from_ac``, and ``scripts.ac_store._gtfa_seams`` gives
    ``scripts.ac_store.generate_ticket_from_ac``.

    Returns:
        The shell module's dotted name for the current import layout.
    """
    package = __name__.rpartition(".")[0]
    return f"{package}.{_SHELL_BASENAME}" if package else _SHELL_BASENAME


def logger_name() -> str:
    """Return the logger name every sibling must log under.

    This is the shell module's ``__name__``, which is what the test suites
    name when they capture or assert on this component's log output. It is
    computed rather than bound because siblings build their module-level
    ``logger`` at import time — before :func:`bind_shell` has run.

    Returns:
        The shell module's ``__name__`` for the current import layout.
    """
    return shell_module_name()


def bind_shell(module: ModuleType) -> None:
    """Record *module* as this layout's shell module.

    Called by the shell on itself, immediately after it has imported its
    siblings and before it re-exports anything. Re-running it (as
    ``importlib.reload`` does) simply rebinds.

    Args:
        module: The ``generate_ticket_from_ac`` module object.
    """
    global _bound_shell  # noqa: PLW0603 - one binding per import layout, by design
    _bound_shell = module


def shell() -> ModuleType:
    """Return this layout's shell module.

    Falls back to importing it by name when nothing has been bound yet. That
    fallback is unreachable in normal use — the shell binds itself while its
    own body is still executing, and ``sys.modules`` already holds it by then —
    but importing is the correct answer rather than raising, because a sibling
    imported on its own should still work.

    Returns:
        The ``generate_ticket_from_ac`` module object.
    """
    if _bound_shell is not None:
        return _bound_shell
    name = shell_module_name()
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    return importlib.import_module(name)


def find_worktree_root(start: Path) -> Path:
    """Call the shell's ``_find_worktree_root``, honouring any patch on it.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: Propagated when no ``.git`` marker is found.
    """
    return shell()._find_worktree_root(start)


def component_migration_map() -> dict[str, str]:
    """Return the shell's current ``_COMPONENT_MIGRATION_MAP``.

    Read through the shell (rather than held as a sibling-level copy) so that
    an ``importlib.reload`` of the shell — which re-runs the module-level
    ``_COMPONENT_MIGRATION_MAP = _load_migration_map()`` statement — is visible
    to every consumer.

    Returns:
        Mapping from kebab component namespace key to underscore graph id.
    """
    value: Any = getattr(shell(), "_COMPONENT_MIGRATION_MAP", {})
    return value if isinstance(value, dict) else {}
