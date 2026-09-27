"""
MODULE: scripts/ac_store/_kind_plugin.py
GOAL: A tiny pytest plugin (loaded via ``-p _kind_plugin``) that records each
    test's FINAL raised exception type name to a JSON file -- pr-reviewer
    finding H-1's fix for TQ-500f-3-i's absence-vs-assertion classifier.
BUSINESS CONTEXT: The classifier used to scrape ``E   <ExceptionType>:``
    lines out of ``pytest -v --tb=line`` stdout and pair them POSITIONALLY
    against the ordered list of failing nodeids. Two real pytest output
    shapes broke that: a bare, message-less ``assert x == y`` prints
    ``E   assert 1 == 2`` (no colon after the first word -- the regex never
    matches it at all), and a chained ``raise X from Y`` prints TWO
    ``E   <Type>:`` lines for ONE failing test. Either shape shifts the
    global positional count out of alignment for the WHOLE BATCH, collapsing
    every declared test's kind to "undetermined" and letting the gate report
    the misleading ``all_new_tests_green_at_baseline`` reason even though
    real tests genuinely failed.

    This plugin replaces that scrape entirely: it reads the exception pytest
    itself already caught, per node, via the ``call.excinfo`` object the
    ``pytest_exception_interact`` hook receives -- never formatted text.
    ``call.excinfo.type`` is the exception actually raised and caught (the
    re-raised exception of a ``raise X from Y`` chain, never its
    ``__cause__``/``__context__``), so chain depth cannot corrupt the result,
    and a bare assert (AssertionError, no message) is captured by TYPE, not
    by scraping a colon that was never printed.

    ``pytest_exception_interact`` fires for BOTH a test's own failure AND a
    collection-time error (e.g. a module-level ``ImportError``) -- for the
    latter, *node* is the Module collector, so its recorded key names the
    MODULE (every test in that file failed to even collect); the reader
    (``_done_proof_kind_support._load_kind_map``) falls back to this
    module-level entry for any individual test nodeid it has no direct entry
    for.

    H-4 FIX (pr-reviewer finding): the recorded key is now a FULL identity --
    the test's ABSOLUTE file path (POSIX, via ``node.path``/``node.fspath``,
    never pytest's own ``node.nodeid``, whose file segment is rootdir-relative
    and can spell a DIFFERENT string than the reader's own cwd-relative
    resolution of the same file) plus its ``::``-delimited class/function
    chain with any ``[params]`` suffix stripped from the final segment. The
    earlier ``(file_basename, bare_func_name)`` key silently cross-attributed
    one test's exception type to an unrelated test sharing only a basename
    and method name (two classes in one file, or two files sharing a
    basename in different package directories) -- this key cannot collide
    for two genuinely distinct tests, since it is exactly the same identity
    Python's own import system already guarantees is unique.
ARCHITECTURE: Standalone -- imports nothing from this package's other
    modules, so it stays importable via ``-p _kind_plugin`` in a fresh pytest
    subprocess whose PYTHONPATH is set to just this directory (see
    ``_done_proof_kind_support._run_pytest_and_parse_with_kind``), without
    dragging in done_proof.py's own heavier import chain. The output-path
    env var name is a small literal duplicated (not imported) from
    ``_done_proof_kind_support.py`` for exactly this reason.

    Deployment: scripts/ac_store/ is deployed via a HARDCODED list
    (AC_STORE_DEPLOY_MAP in scripts/build_phases_ac_store.py). This module is
    registered there -- omitting it would leave the deployed fast-lane gate
    crashing (pytest's ``-p _kind_plugin`` would fail to import) the first
    time a caller passes ``ac_root``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Duplicated literal (not imported) from _done_proof_kind_support.py -- see
# this module's own ARCHITECTURE note for why.
_KIND_OUTPUT_ENV_VAR = "LEAFCUTTER_KIND_PLUGIN_OUTPUT"


def _full_identity(node: Any) -> str:
    """Build node's full identity: absolute POSIX file path [+ ``::`` chain].

    Duplicated (not imported) from ``_done_proof_kind_support.py``'s own
    ``_strip_params_suffix`` shape -- see this module's ARCHITECTURE note.

    Args:
        node: The ``Item`` or ``Collector`` to build an identity for.

    Returns:
        ``"<abs_posix_path>"`` for a module-level identity, or
        ``"<abs_posix_path>::<class>::<func>"`` (params stripped from the
        final segment) for a test-level identity.
    """
    path = getattr(node, "path", None) or Path(str(node.fspath))
    file_posix = Path(path).resolve().as_posix()
    nodeid = node.nodeid
    if "::" not in nodeid:
        return file_posix
    segments = nodeid.split("::", 1)[1].split("::")
    segments[-1] = segments[-1].split("[", 1)[0]
    return file_posix + "::" + "::".join(segments)


def pytest_configure(config: Any) -> None:
    """Initialise this session's in-memory nodeid -> exception-type-name map.

    Args:
        config: pytest's session ``Config`` object.
    """
    config._leafcutter_kind_map = {}


def pytest_exception_interact(node: Any, call: Any, report: Any) -> None:  # noqa: ARG001 -- report is part of the pytest hook signature
    """Record *node*'s FINAL raised exception type name.

    Args:
        node: The ``Item`` (test) or ``Collector`` (module, on a collection
            error) the exception was raised from/for.
        call: pytest's ``CallInfo``; ``call.excinfo.type`` is the exception
            actually raised and caught -- never its ``__cause__``/``__context__``.
        report: Unused; required by the hook's own signature.
    """
    if call.excinfo is None:
        return
    kind_map = getattr(node.config, "_leafcutter_kind_map", None)
    if kind_map is None:
        return
    kind_map[_full_identity(node)] = call.excinfo.type.__name__


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:  # noqa: ARG001 -- exitstatus is part of the pytest hook signature
    """Write the session's accumulated kind map to the configured output path.

    A missing/unset output-path env var means this plugin's caller did not
    opt in (e.g. an ordinary pytest run with no ``LEAFCUTTER_KIND_PLUGIN_OUTPUT``
    set) -- writes nothing in that case. A write failure is swallowed rather
    than raised: this plugin must never fail an otherwise-successful pytest
    run over a diagnostics-file write.

    Args:
        session: pytest's ``Session`` object.
        exitstatus: Unused; required by the hook's own signature.
    """
    output_path = os.environ.get(_KIND_OUTPUT_ENV_VAR)
    if not output_path:
        return
    kind_map = getattr(session.config, "_leafcutter_kind_map", {})
    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(kind_map, fh)
    except OSError:
        pass


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-27 [python-coder/TQ-500f-3-i H-1]: New standalone pytest plugin.
#   Replaces the positional "E   <Type>:" text-scraping approach
#   (_pair_failure_kinds_with_nodeids, removed from _done_proof_kind_support.py)
#   with a direct read of pytest's own exception-info object via the
#   pytest_exception_interact hook -- immune to bare asserts (no colon line)
#   and chained exceptions (multiple colon lines) corrupting a positional zip.
# ====================================================================
