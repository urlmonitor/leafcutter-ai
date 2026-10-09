"""
Shared helpers + constants for the TQ-600a-9 family test files:
``test_tq_600a_9.py``, ``test_tq_600a_9_i.py``, ``test_tq_600a_9_ii.py``.

NOT ``test_tq_600a_9_iii.py``, deliberately. TQ-600a-9-iii is held at
``readiness: reviewed`` and is NOT approved: its own it_requirements state
that it must not be built without the owner of ACD-2100d-2-i agreeing,
because it revises a written order-independence decision that author
recorded. It was authored as a separable record precisely so the rest of
this family can ship without it. Do not add it here on the assumption the
omission is an oversight.

Source of truth: docs/acceptance-criteria/testing-quality/
TQ-600-suite-feedback-latency/TQ-600a-9*.yaml (test_spec + test_rationale +
it_requirements). Where the ticket's derived ``## Test Requirements`` differs
from the YAML, the YAML wins.

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds
this to make the tests below green -- Source-of-Truth Discipline Rule 5).

COUNTING. TQ-600a-9's own it_requirements name the package's ONE real
build-subprocess counter -- ``emit_execution_signal`` /
``EXECUTION_LOG_ENV_VAR`` in ``scripts/suite_performance/
_shared_layout_coordination.py`` -- and name the exact call sites that must
start calling it:
  - ``unit_tests/portability/_bp1500g1_harness.py``: ``run_build()`` (line 97),
    shared by the six adopter files (incl. ``test_bp_1500g_2_i.py``).
  - ``unit_tests/portability/test_inf_400c_4_i.py``: five inline
    ``subprocess.run`` call sites.
  - ``unit_tests/build_guards/test_build_leaves_tracked_files_clean.py``:
    ``_run_build()`` (line 29).
  - ``unit_tests/build_guards/test_acd_2100d_2_i.py``: ``_run_build()``
    (line 115).
No test below patches ``subprocess.run`` or counts any way other than
reading the real emitted ``deploy_executed`` JSONL signal -- "a mocked
build is not a build" (TQ-600a-9 it_requirement).

RED TODAY, UNIFORMLY. None of the four call sites above calls
``emit_execution_signal`` yet, so every count this helper reads is 0
regardless of how the real subprocess(es) that ran actually behaved. Every
test below asserts the COUNT first, which is therefore the first thing to
go red -- a deliberate design choice (not an oversight) so that the
subtler per-test isolation/ordering assertions later in the same test body
activate only once python-coder's sharing implementation exists; today they
are simply unreached code, which is the correct RED shape for a TDD stub
(Step 2g).

BREAK-PROPERTY TEST HOOK (test-writer's own interface choice, same posture
as TQ-600a-5's assumed marker names -- documented here so the mechanism is
unambiguous). TQ-600a-9's and TQ-600a-9-i's "cannot be dropped" descriptors
require "breaking only the property a test names" to be demonstrated BY
EXECUTION. Rather than hand-editing the real production harness file (which
would need restoring after every run and risks corrupting a file under
test), this hook is entirely TEST-SIDE: a pytest plugin, generated fresh
per run into a scratch directory and loaded via ``-p <modname>`` with that
directory prepended to the child session's ``PYTHONPATH``. Its
``pytest_configure`` hook runs before collection, so it can monkeypatch the
named function on the real ``_bp1500g2_harness`` module BEFORE
``test_bp_1500g_2_i.py`` does its own ``from _bp1500g2_harness import
...`` -- the patched reference is what import binds. No production file is
ever edited; the real ``run_build()``/package code is untouched, so the
break genuinely isolates only the one named property. Selected by the env
var ``LEAFCUTTER_TQ600A9_BREAK_PROPERTY`` ("survival" | "message" |
"declared_winner" | "cross_platform_winner"); a no-op when unset.
======================================================================
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from ._test_helpers import _read_jsonl, _WORKTREE_ROOT  # noqa: F401 - re-exported
from ._test_helpers_tq_600a_5 import run_child_session  # noqa: F401 - re-exported

from scripts.suite_performance._shared_layout_coordination import (  # noqa: E402
    EXECUTION_LOG_ENV_VAR,
)

BREAK_PROPERTY_ENV_VAR = "LEAFCUTTER_TQ600A9_BREAK_PROPERTY"

_PORTABILITY_DIR = _WORKTREE_ROOT / "unit_tests" / "portability"

_COLLISION_GROUP_TESTS: dict[str, str] = {
    "survival": (
        "test_bp_1500g_2_i_the_adopter_version_of_a_contested_name_is_"
        "present_and_unchanged_after_the_run"
    ),
    "message": (
        "test_bp_1500g_2_i_the_run_names_the_contested_name_and_states_"
        "which_version_the_project_will_run"
    ),
    "declared_winner": (
        "test_bp_1500g_2_i_the_stated_winner_is_the_one_the_project_"
        "actually_resolves_afterwards"
    ),
    "cross_platform_winner": (
        "test_bp_1500g_2_i_the_stated_winner_holds_on_every_active_"
        "platform_surface_not_only_claude"
    ),
}

COLLISION_GROUP_KEXPR = " or ".join(_COLLISION_GROUP_TESTS.values())
COLLISION_GROUP_FILE = "unit_tests/portability/test_bp_1500g_2_i.py"

_BREAK_PLUGIN_SOURCE = '''
"""Generated at test time by _test_helpers_tq_600a_9.py -- see that module's
ASSUMED PRODUCTION CONTRACT docstring for the full rationale. Monkeypatches
exactly ONE named collision property on the real _bp1500g2_harness module,
selected by LEAFCUTTER_TQ600A9_BREAK_PROPERTY, before collection imports
test_bp_1500g_2_i.py's own `from _bp1500g2_harness import ...`.
"""
import os
import sys

# pytest_configure runs BEFORE collection, so unit_tests/portability/ is not
# yet on sys.path (that insertion happens when test_bp_1500g_2_i.py itself
# is imported, later) -- without this, the bare `import _bp1500g2_harness`
# below always raises ModuleNotFoundError regardless of _PROPERTY. The
# concrete path is baked in at generation time by write_collision_break_plugin
# (see __PORTABILITY_DIR__ below), since this file is written into a throwaway
# scratch plugin_dir, not unit_tests/suite_performance/ itself.
sys.path.insert(0, "__PORTABILITY_DIR__")

_PROPERTY = os.environ.get("LEAFCUTTER_TQ600A9_BREAK_PROPERTY")


def pytest_configure(config):
    if not _PROPERTY:
        return
    import _bp1500g2_harness as h

    if _PROPERTY == "message":
        h.mentions_collision = lambda *a, **k: False
    elif _PROPERTY == "declared_winner":
        h.parse_stated_collision_winner = lambda *a, **k: None
    elif _PROPERTY == "cross_platform_winner":

        def _broken(*a, **k):
            raise AssertionError(
                "tq600a9 break-plugin: cross_platform_winner broken"
            )

        h.assert_declared_winner_holds_on_every_active_surface = _broken
    elif _PROPERTY == "survival":
        _orig = h.plant_colliding_capability

        def _broken_plant(target_root, name):
            d = _orig(target_root, name)
            d["skill_md"] = target_root / "_tq600a9_break_survival_missing.md"
            return d

        h.plant_colliding_capability = _broken_plant
'''


def write_collision_break_plugin(plugin_dir: Path) -> str:
    """Write the break-plugin module into *plugin_dir*; return its bare
    importable module name (``plugin_dir`` must be put on PYTHONPATH by the
    caller -- see ``break_env`` below)."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    modname = "tq600a9_break_plugin"
    source = _BREAK_PLUGIN_SOURCE.replace("__PORTABILITY_DIR__", str(_PORTABILITY_DIR))
    (plugin_dir / f"{modname}.py").write_text(source, encoding="utf-8")
    return modname


def break_env(
    plugin_dir: Path,
    log_path: Path,
    *,
    break_property: str | None = None,
) -> dict[str, str]:
    """Build the env_overrides dict for a run_child_session call that needs
    the break-plugin's directory importable AND the execution log set.

    Prepends plugin_dir to any existing PYTHONPATH rather than replacing it
    (run_child_session's env_overrides REPLACE a key wholesale)."""
    existing_pp = os.environ.get("PYTHONPATH", "")
    new_pp = f"{plugin_dir}{os.pathsep}{existing_pp}" if existing_pp else str(plugin_dir)
    env = {
        EXECUTION_LOG_ENV_VAR: str(log_path),
        "PYTHONPATH": new_pp,
    }
    if break_property is not None:
        env[BREAK_PROPERTY_ENV_VAR] = break_property
    return env


def count_events(log_path: Path, event: str = "deploy_executed") -> int:
    return len(events(log_path, event))


def events(log_path: Path, event: str = "deploy_executed") -> list[dict]:
    return [e for e in _read_jsonl(log_path) if e.get("event") == event]


# ---------------------------------------------------------------------------
# PRODUCE-ONCE, SHARED ACROSS SIBLING TEST FUNCTIONS (test-writer practising
# the exact principle TQ-600a-9 itself specifies). Several descriptors in
# this build set independently need "the plain (unbroken) real run of file
# X" -- the four-way collision group, the whole consumer-install file, the
# whole tracked-files file, the whole installer-announcement file -- and a
# naive per-test implementation would spawn that same real, expensive run
# once per test that needs it. This cache produces it ONCE per pytest
# session (keyed by a caller-chosen string) and hands the SAME
# (CompletedProcess, log_path, basetemp) tuple to every caller, exactly the
# produce-once-then-read-only-share shape the AC under test specifies.
# Never used for a BROKEN or order-varied run -- those must each be a fresh
# OS process by the AC's own must_catch list, and call run_child_session /
# break_env directly instead.
# ---------------------------------------------------------------------------

_SHARED_RUN_CACHE: dict[str, tuple] = {}
_SHARED_CACHE_ROOT = Path(tempfile.gettempdir()) / "tq600a9_test_writer_shared_cache"


def run_plain_once(
    key: str,
    children_dir,
    *,
    extra_args: list[str] | None = None,
    with_basetemp: bool = True,
) -> tuple:
    """Run the PLAIN (unbroken) real session for *key* at most once per
    process; every subsequent call with the same *key* returns the cached
    result instead of spawning another real subprocess tree.

    Always requests `--basetemp` (default True) so every caller -- whether
    it only needs the build count or also needs to inspect the produced
    tree -- can share the one cache entry; the extra `--basetemp` flag is
    free on a run that would happen anyway.

    Returns:
        ``(result, log_path, basetemp)``.
    """
    if key in _SHARED_RUN_CACHE:
        return _SHARED_RUN_CACHE[key]
    cache_dir = _SHARED_CACHE_ROOT / key
    # Scrub any stale directory left by a PRIOR OS process's run of this
    # same key -- the in-memory _SHARED_RUN_CACHE dict is process-local and
    # empty at the start of every fresh process, but a leftover exec_log
    # file on disk from an earlier invocation would otherwise accumulate
    # deploy_executed entries across unrelated runs once a real builder
    # starts calling emit_execution_signal, corrupting every count below.
    shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_path = cache_dir / "exec_log.jsonl"
    basetemp = cache_dir / "basetemp"
    args = list(extra_args or [])
    if with_basetemp:
        args += [f"--basetemp={basetemp}"]
    env = break_env(cache_dir / "plugin_unused", log_path)
    result = run_child_session(children_dir, extra_args=args, env_overrides=env)
    entry = (result, log_path, basetemp)
    _SHARED_RUN_CACHE[key] = entry
    return entry


def failed_nodeids(stdout: str) -> list[str]:
    """Parse pytest's own ``-q`` output for ``FAILED <nodeid>`` lines -- the
    real run's own report, never an in-process structure."""
    out = []
    for line in stdout.splitlines():
        if line.startswith("FAILED "):
            out.append(line[len("FAILED "):].split(" ")[0].strip())
    return out
