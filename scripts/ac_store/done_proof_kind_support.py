"""
MODULE: scripts/ac_store/_done_proof_kind_support.py
GOAL: Additive failure-KIND (absence vs assertion) classification layered on
    top of done_proof.py's own pytest-output contract, for TQ-500f-3-i's
    red-baseline absence-only-refusal rule.
BUSINESS CONTEXT: TQ-500f-3-i extends the fast lane's ONE existing
    verify_red_baseline reader (scripts/build_orchestration/fast_lane.py +
    _fl_red_baseline_support.py) to refuse a newly-added covering test whose
    AC test_spec entry declares ``must_catch`` (non-empty) or
    ``angle: discrimination`` when that test's ONLY red is an absence red
    (an import, name, or attribute lookup error for the named thing, raised
    before any code under test ran). Telling absence from assertion needs
    the pytest run's OWN exception-type output per failing test -- something
    done_proof.py's existing ``_run_pytest_and_parse`` deliberately discards
    (it runs with ``--tb=no`` and returns only ``{nodeid: outcome}``).
    TQ-500f-3-i's own it_requirements: "the pytest-output parsing stays
    shared with done_proof (reuse, not a fork)... extend the shared parser
    additively so that done_proof's {nodeid: outcome} contract and its
    verdicts are unchanged, and the gate still makes a single pytest run."
ARCHITECTURE: This module REUSES done_proof.py's own timeout-budget
    computation (``_resolve_pytest_timeout_seconds``) and its own outcome
    parser (``_parse_pytest_verbose_output``, ``_PYTEST_RUN_INCOMPLETE_SENTINEL``)
    rather than re-deriving either -- the classification rule this module
    adds is a read of the SAME single pytest run's output, not a second
    reader of test outcomes. done_proof.py's own ``_run_pytest_and_parse``
    function and its ``{nodeid: outcome}`` contract are untouched: this
    module is a strictly ADDITIVE sibling, never an edit to that file.
    That is a hard file-size-ratchet constraint, not merely a style
    preference -- done_proof.py already measures ~1300 content lines
    (the check-file-size hook's own counter) against the repository's
    400-line limit, so any further GROWTH in that already-oversized file is
    mechanically refused at commit time (GE-127b-1). Placing this module's
    new code here, rather than as an in-place addition to done_proof.py,
    keeps done_proof.py's own content-line count at zero net change.

    ``verify_red_baseline`` (scripts/build_orchestration/fast_lane.py) calls
    ``_run_pytest_and_parse_with_kind`` ONCE, instead of the existing
    ``_run_pytest_and_parse``, ONLY when its caller supplies ``ac_root``
    (TQ-500f-3-i's absence-refusal rule is opt-in via that kwarg) -- so the
    gate still makes exactly one pytest subprocess run per invocation either
    way, never two.

    H-1 FIX (pr-reviewer finding): the kind per test is now read from a tiny
    pytest plugin (``_kind_plugin.py``, loaded via ``-p _kind_plugin``) that
    records each test's FINAL raised exception TYPE via pytest's own
    ``call.excinfo`` object -- never scraped from ``--tb=line`` text. The
    previous scrape paired ``E   <Type>:`` lines POSITIONALLY against the
    ordered list of failing nodeids, which silently collapsed to "no kinds
    determined for the whole batch" whenever a bare, message-less assert
    (prints no colon-bearing line at all) or a chained exception (prints TWO
    colon-bearing lines for one test) shifted the count out of alignment.
    The plugin writes ``{identity: exception_type_name}`` to a JSON file this
    module points it at via ``LEAFCUTTER_KIND_PLUGIN_OUTPUT``, keyed by a
    per-test identity for a normal test failure or by a per-module identity
    for a collection-time error (every test in that module shares that one
    entry, see ``_load_kind_map``'s fallback). ``--tb`` reverts to ``--tb=no``
    -- the SAME flag ``_run_pytest_and_parse`` itself uses -- since the kind
    no longer comes from stdout text at all.

    H-4 FIX (pr-reviewer finding): that identity is now the test's FULL
    identity (absolute POSIX file path + ``::``-delimited class/function
    chain, params stripped) rather than the earlier ``(file_basename,
    bare_func_name)`` pair -- see ``_normalize_outcome_identity`` and
    ``_kind_plugin.py``'s own ``_full_identity`` (the SAME shape, built from
    two different starting representations because pytest's own internal
    nodeid and its ``-v`` stdout display can spell the SAME test's file
    segment as two different strings -- see that function's own docstring).
    The basename+bare-name key silently cross-attributed one test's kind to
    an unrelated test sharing only a basename and method name (two classes
    in one file, or two files sharing a basename in different package
    directories); the full identity cannot collide for two genuinely
    distinct tests.

    Deployment: scripts/ac_store/ is deployed via a HARDCODED list
    (AC_STORE_DEPLOY_MAP in scripts/build_phases_ac_store.py), unlike
    scripts/build_orchestration/ (deployed via a directory glob). This
    module AND ``_kind_plugin.py`` are both registered there alongside
    done_proof.py and _done_proof_phase_helpers.py -- omitting either entry
    would leave the deployed fast-lane gate crashing the first time a caller
    passes ``ac_root``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from done_proof import (
    _PYTEST_RUN_INCOMPLETE_SENTINEL,
    _parse_pytest_verbose_output,
    _resolve_pytest_timeout_seconds,
)

# The declared signal's OBSERVED-outcome half (TQ-500f-3-i it_requirements):
# an absence red is an import, name, or attribute lookup error for the named
# thing, raised before any code under test ran. Any other exception type
# (AssertionError chief among them) is an assertion red -- a failure AFTER
# the code under test ran.
_ABSENCE_EXCEPTION_TYPES: frozenset[str] = frozenset(
    {"ImportError", "ModuleNotFoundError", "AttributeError", "NameError"}
)

# Duplicated literal (not imported) -- MUST match _kind_plugin.py's own
# _KIND_OUTPUT_ENV_VAR; see that module's ARCHITECTURE note for why it stays
# a standalone, import-free plugin rather than importing this name.
_KIND_OUTPUT_ENV_VAR = "LEAFCUTTER_KIND_PLUGIN_OUTPUT"

# The plugin module's bare (unqualified) name, loaded via pytest's -p flag.
# Resolvable because _run_pytest_and_parse_with_kind puts this module's own
# directory (where _kind_plugin.py lives, as a sibling) on the child
# process's PYTHONPATH.
_KIND_PLUGIN_MODULE_NAME = "_kind_plugin"


def _classify_failure_kind(exception_type: str) -> str:
    """Classify one exception class name into ``"absence"`` or ``"assertion"``.

    Args:
        exception_type: The bare exception class name (e.g. ``"ImportError"``)
            ``_kind_plugin.py`` recorded for one nodeid.

    Returns:
        ``"absence"`` when *exception_type* is an import/name/attribute
        lookup error; ``"assertion"`` for every other exception type.
    """
    return "absence" if exception_type in _ABSENCE_EXCEPTION_TYPES else "assertion"


def _normalize_outcome_identity(nodeid: str) -> str:
    """Build the SAME full identity ``_kind_plugin.py``'s ``_full_identity`` builds.

    *nodeid* comes from ``_parse_pytest_verbose_output`` -- the ``-v`` stdout
    display, which is resolved relative to the INVOCATION directory (this
    process's own ``os.getcwd()``, since the pytest subprocess never has its
    ``cwd`` overridden -- see ``_run_pytest_with_kind_plugin``). Resolving
    the file segment against ``Path.resolve()`` (cwd-relative by definition)
    therefore lands on the SAME absolute file the plugin recorded via
    ``node.path`` -- even though the plugin's OWN ``node.nodeid`` spells that
    file's segment differently (pytest's internal nodeid is rootdir-relative,
    not invocation-dir-relative, and the two need not be the same directory).

    Args:
        nodeid: A pytest nodeid from ``_parse_pytest_verbose_output``'s keys.

    Returns:
        ``"<abs_posix_path>"`` when *nodeid* names a module only (no ``::``),
        or ``"<abs_posix_path>::<class>::<func>"`` (params stripped from the
        final segment) for a test-level nodeid.
    """
    file_part, sep, rest = nodeid.partition("::")
    file_posix = Path(file_part).resolve().as_posix()
    if not sep:
        return file_posix
    segments = rest.split("::")
    segments[-1] = segments[-1].split("[", 1)[0]
    return file_posix + "::" + "::".join(segments)


def _index_kind_plugin_output(raw: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Split ``_kind_plugin.py``'s JSON map into per-test and per-module indexes.

    *raw*'s keys are ALREADY full identities (see ``_kind_plugin._full_identity``)
    -- this function only separates per-test entries (containing ``::``) from
    per-module entries (collection errors, no ``::``) into two lookup dicts;
    no further transformation of the key is needed on this side.

    Args:
        raw: The plugin's own ``{identity: exception_type_name}`` JSON map.

    Returns:
        ``(per_test_index, per_module_index)`` -- both keyed verbatim on the
        identity string *raw* already carries.
    """
    per_test_index: dict[str, str] = {}
    per_module_index: dict[str, str] = {}
    for identity, exception_type in raw.items():
        if "::" in identity:
            per_test_index[identity] = exception_type
        else:
            per_module_index[identity] = exception_type
    return per_test_index, per_module_index


def _load_kind_map(kind_output_path: str, outcomes: dict[str, str]) -> dict[str, str]:
    """Read ``_kind_plugin.py``'s JSON output and classify each outcome nodeid.

    A nodeid with no direct full-identity match falls back to its MODULE's
    own entry (the identity's file segment alone) -- the shape a
    collection-time error (e.g. a module-level ``ImportError``) writes,
    since no individual test was ever collected from that module to carry
    its own entry.

    Args:
        kind_output_path: Path ``_kind_plugin.py`` wrote its JSON map to.
        outcomes: ``{nodeid: outcome}`` from ``_parse_pytest_verbose_output``
            -- only these nodeids are looked up (a passing test has no
            recorded exception and is correctly absent from the result).

    Returns:
        ``{nodeid: "absence" | "assertion"}`` for every nodeid whose kind
        could be resolved, directly or via its module's fallback entry. A
        missing/unreadable output file yields an empty dict (fail-closed:
        every kind is then "undetermined" to the caller).
    """
    try:
        with open(kind_output_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    per_test_index, per_module_index = _index_kind_plugin_output(raw)
    kinds: dict[str, str] = {}
    for nodeid in outcomes:
        if "::" not in nodeid:
            continue
        identity = _normalize_outcome_identity(nodeid)
        exception_type = per_test_index.get(identity)
        if exception_type is None:
            module_identity = identity.split("::", 1)[0]
            exception_type = per_module_index.get(module_identity)
        if exception_type is not None:
            kinds[nodeid] = _classify_failure_kind(exception_type)
    return kinds


def _run_pytest_and_parse_with_kind(
    test_files: list[Path],
) -> tuple[dict[str, str], dict[str, str]]:
    """Execute pytest ONCE on *test_files*; return outcomes AND failure kinds.

    Shares done_proof.py's own timeout-budget computation
    (``_resolve_pytest_timeout_seconds``) and outcome parser
    (``_parse_pytest_verbose_output``), so the first returned dict has the
    IDENTICAL shape and values ``_run_pytest_and_parse`` would return for the
    same *test_files*. The second dict is populated by loading
    ``_kind_plugin.py``'s own JSON output (see ``_load_kind_map``) --
    ``-p _kind_plugin`` on the pytest command line and
    ``LEAFCUTTER_KIND_PLUGIN_OUTPUT`` in the child environment wire it in.

    Args:
        test_files: Absolute paths to Python test files to execute.

    Returns:
        ``({nodeid: outcome}, {nodeid: kind})``. On a timeout or an OS
        error launching pytest, the first dict carries the same fail-closed
        sentinel/empty shapes ``_run_pytest_and_parse`` uses and the second
        dict is empty.
    """
    if not test_files:
        return {}, {}
    kind_output_fd, kind_output_path = tempfile.mkstemp(
        suffix=".json", prefix="leafcutter_kind_"
    )
    os.close(kind_output_fd)
    try:
        return _run_pytest_with_kind_plugin(test_files, kind_output_path)
    finally:
        try:
            os.unlink(kind_output_path)
        except OSError:
            pass


def _run_pytest_with_kind_plugin(
    test_files: list[Path], kind_output_path: str
) -> tuple[dict[str, str], dict[str, str]]:
    """The actual subprocess launch + parse for ``_run_pytest_and_parse_with_kind``.

    Split out as its own function purely so the caller's ``finally``-guarded
    temp-file cleanup reads as a single, unindented block around one call.

    Args:
        test_files: Absolute paths to Python test files to execute.
        kind_output_path: Pre-allocated path the plugin will write its JSON
            kind map to.

    Returns:
        Same ``({nodeid: outcome}, {nodeid: kind})`` shape as
        ``_run_pytest_and_parse_with_kind``.
    """
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=no",
        "--no-header",
        "-p",
        _KIND_PLUGIN_MODULE_NAME,
    ]
    cmd.extend(str(f) for f in test_files)
    plugin_dir = str(Path(__file__).resolve().parent)
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    child_pythonpath = (
        plugin_dir + os.pathsep + existing_pythonpath
        if existing_pythonpath
        else plugin_dir
    )
    child_env = {
        **os.environ,
        "AC_ENFORCE_STRICT": "1",
        _KIND_OUTPUT_ENV_VAR: kind_output_path,
        "PYTHONPATH": child_pythonpath,
    }
    timeout_seconds = _resolve_pytest_timeout_seconds(test_files)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        message = (
            f"pytest could not verify {len(test_files)} linked file(s) within "
            f"its {timeout_seconds:.1f}s timeout budget (command: pytest): {exc}"
        )
        print(f"WARNING: fast_lane: {message}", file=sys.stderr)
        return {_PYTEST_RUN_INCOMPLETE_SENTINEL: message}, {}
    except OSError as exc:
        print(f"WARNING: fast_lane: cannot run pytest: {exc}", file=sys.stderr)
        return {}, {}
    if proc.returncode not in (0, 1):
        message = (
            f"pytest run unfinished: {len(test_files)} file(s), "
            f"returncode {proc.returncode}"
        )
        print(f"WARNING: fast_lane: {message}", file=sys.stderr)
        return {_PYTEST_RUN_INCOMPLETE_SENTINEL: message}, {}
    outcomes = _parse_pytest_verbose_output(proc.stdout)
    kinds = _load_kind_map(kind_output_path, outcomes)
    return outcomes, kinds


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-27 [python-coder/TQ-500f-3-i]: New additive module. Adds
#   absence-vs-assertion failure-kind classification derived from a single
#   pytest run, reusing done_proof.py's own timeout budget and outcome
#   parser rather than forking either. Created as a sibling module (not an
#   in-place addition to done_proof.py) because done_proof.py already sits
#   over the file-size ratchet's limit and any growth there is mechanically
#   refused at commit time.
# - 2026-09-27 [python-coder/TQ-500f-3-i H-1]: Replaced the positional
#   "E   <Type>:" text-scrape (_pair_failure_kinds_with_nodeids, removed)
#   with _kind_plugin.py, a pytest plugin reading pytest's own exception-info
#   object per node -- see that module's DECISION HISTORY for the bug this
#   fixes (bare asserts and chained exceptions corrupting the whole batch's
#   kinds under the old positional pairing).
# ====================================================================
