"""
MODULE: unit_tests/build_guards/test_bp_100k_2.py
GOAL: BP-100k-2 — write_build_manifest()'s output_mappings section must
    resolve EVERY deployed output the build actually writes (under
    ``.claude/agents``, ``.claude/skills``, ``.claude/commands``,
    ``.claude/hooks``, etc.) back to the source template it was produced
    from, keyed the SAME way check_output_drift.py looks it up — so the
    output-drift gate never reports a build-produced file as unregistered.
BUSINESS CONTEXT: ``_compute_output_mappings()`` in scripts/build_helpers.py
    records each entry keyed by ``(target_root / "agents" / tpl.name)
    .relative_to(repo_root)`` — i.e. a path like ``agents/README.md``.
    check_output_drift.py, however, scans the REAL deployed directories
    (``repo_root / ".claude" / "agents"``, etc. — see that module's
    ``main()``) and keys its lookups as ``.claude/agents/README.md``. The
    ``.claude/`` prefix is never present in the recorded key, so EVERY
    real deployed output is permanently unregistered and the gate can never
    detect a hand-edit to a deployed file. Confirmed empirically against
    this worktree's own real build on 2026-08-18 (see ticket comments):
    153/153 output_mappings keys, 0 matches against the 81 real files
    found under a real ``.claude/{agents,commands,hooks}`` deploy.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100k-2.yaml.
ARCHITECTURE / EXERCISE STRATEGY:
    Unlike Direction A (template_hashes, tested in test_bp_100k_1.py),
    output_mappings computation calls ``_compute_output_mappings()``, which
    does a DELAYED, package_root-relative import of ``template_compiler``
    (``sys.path.insert(0, str(package_root / "scripts")); from
    template_compiler import ...``). That import can only succeed against a
    real, on-disk ``<package_root>/scripts/`` tree, so these tests build a
    FULLER synthetic package: real, copied (never paraphrased)
    ``templates/``, ``scripts/``, and ``config/`` trees, laid out at the
    same relative depth self-hosting production uses
    (``package_root.parent`` == the workspace/target root passed to
    ``build.py --target-dir``).

    Because ``build_phases.py`` (unlike ``build_helpers.write_build_manifest``)
    resolves its OWN package root from ``Path(__file__).resolve().parent
    .parent`` at import time rather than accepting it as a parameter, every
    module this suite needs (``build_helpers``, ``build_phases``,
    ``config_loader``) is loaded via ``importlib.util.spec_from_file_location``
    under a per-test unique module name, forcing it to read from THIS test's
    own synthetic package copy regardless of what any other test file in the
    same process already imported and cached under the bare module name.

    The drift-gate tests then deploy a REAL, byte-identical copy of
    check_output_drift.py (plus _resolve_root.py) into a synthesized
    deployed layout and invoke it as a subprocess — the same pattern
    proven in unit_tests/commit_guardian/
    test_ge_118b_drift_manifest_resolution.py.

RED BASELINE (captured 2026-08-18, before any production-code change):
    - test_output_mapping_names_the_deployed_output_and_its_source FAILS:
      output_mappings has no ".claude/agents/README.md" key (only the
      un-prefixed "agents/README.md").
    - test_output_drift_gate_emits_match_then_drift_for_that_output FAILS
      on both legs: check_output_drift.py reports the real deployed file
      as "not in output_mappings" instead of a match, and STILL reports it
      as unregistered (exit 0) after mutation instead of BLOCKED (exit 1).
    - test_gate_never_reports_a_build_produced_output_as_unregistered
      FAILS: "not in output_mappings" is present in stderr.
    - test_output_mapping_covers_every_deploy_phase_output FAILS: every
      real deployed file across the agents/commands/hooks phases is
      missing from output_mappings.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CONFIG_DIR = _REPO_ROOT / "config"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_RESOLVE_ROOT_SRC = _CG_TEMPLATES_SRC / "_resolve_root.py"
_CHECK_OUTPUT_DRIFT_SRC = _CG_TEMPLATES_SRC / "check_output_drift.py"

_SUBPROCESS_TIMEOUT_SECONDS = 20
_UNIQUE_COUNTER = [0]

# Top-level dirs _build_synthetic_full_package() already copies wholesale; a
# PACKAGE_ROOT chain whose first segment is one of these is not "extra".
_ALREADY_COPIED_TOP_LEVEL = frozenset({"templates", "scripts", "config"})

# Matches a literal two-segment PACKAGE_ROOT chain, e.g. `PACKAGE_ROOT /
# "docs" / "product-truth"` — see _derive_extra_package_dirs() docstring for
# why this narrow (exactly two quoted segments) shape is the safe direction.
_PACKAGE_ROOT_CHAIN_RE = re.compile(r'PACKAGE_ROOT\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"')


def _derive_extra_package_dirs(scripts_dir: Path, repo_root: Path) -> list[str]:
    """Derive extra top-level source directories the synthetic package must copy.

    ``_build_synthetic_full_package()`` copies ``templates/``, ``scripts/``,
    and ``config/`` wholesale, but the ``build_phases`` FAMILY also declares
    deploy sources OUTSIDE those three trees (e.g. ``build_product_truth``
    reads from ``PACKAGE_ROOT / "docs" / "product-truth"``). Hardcoding
    ``docs/product-truth`` into this fixture is what let it go stale before:
    the deploy phase was free to point at any directory and nothing forced
    this test fixture to notice. Deriving it FROM the real source instead
    means a new such reference is picked up automatically the next time this
    fixture builds.

    Scans every ``build_phases*.py`` file directly under ``scripts_dir`` —
    NOT just the facade — for literal ``PACKAGE_ROOT / "seg1" / "seg2"``
    chains, skips any whose first segment is already copied wholesale, and
    keeps only those that resolve to a real on-disk directory under
    ``repo_root`` (a two-segment chain can also be a FILE path, e.g.
    ``PACKAGE_ROOT / "config" / "ac_store_schema.json"`` before the
    already-copied-segment filter even applies — the is_dir() check is a
    second, independent guard against copying a false positive).

    WHY THE WHOLE FAMILY, NOT JUST ``build_phases.py`` (the bug this
    replaces): the BP size-split (2026-09-14) moved every phase function,
    including ``build_product_truth``, out of ``build_phases.py`` into
    sibling modules (``build_phases_product_truth.py``, etc.) — each
    referring to shared state through a function-scoped ``import
    build_phases as _bp`` and writing the chain as ``_bp.PACKAGE_ROOT /
    "docs" / "product-truth"`` (the regex still matches this form: it is an
    unanchored search for the literal substring ``PACKAGE_ROOT / "..." /
    "..."``, so a ``_bp.`` prefix in front of it makes no difference — this
    was verified, not assumed). After the split, a scan of ``build_phases.py``
    ALONE turns up zero such chains in real code — the sole remaining match
    is inside a DECISION HISTORY comment that a prior fix deliberately
    preserved specifically to keep this derivation non-empty. A derivation
    satisfied by prose rather than by code is exactly the kind of false
    green this fixture exists to prevent: the code path that decides what to
    copy was free to drift (or be deleted from the sibling entirely) with
    this derivation none the wiser, so long as nobody touched that one
    comment. Scanning the whole family closes that gap and makes the
    derivation code-sourced again.

    Verified against this repo (2026-09-14, post BP size-split): scanning
    the family yields exactly ``["docs/product-truth"]`` — the same result
    as before, but now sourced from the real ``_bp.PACKAGE_ROOT / "docs" /
    "product-truth"`` chains in ``build_phases_product_truth.py``, with no
    false positives.

    This derivation is itself a regex over source text and could miss a
    future PACKAGE_ROOT reference expressed some other way (an intermediate
    variable, an f-string, a three-segment chain). That is an accepted
    risk in the safe direction: a miss here makes the affected fixture-based
    test FAIL LOUDLY (the real phase raises ``DeployDeclarationError``
    against the synthetic copy because the source directory it declares is
    absent) rather than silently pass on a package tree missing a real
    directory — the same fail-loud-over-pass-false posture BP-900g-9 itself
    enforces on the production deploy loops. Never widen this back into a
    hardcoded directory list; that is exactly what went stale before.

    Args:
        scripts_dir: Absolute path to the real ``scripts/`` directory to
            scan — every ``build_phases*.py`` file directly under it (the
            source of truth, never a copy).
        repo_root: Absolute path to the repo root the derived directories
            are resolved and copied from.

    Returns:
        Repo-relative ``"seg1/seg2"`` directory strings, in first-seen order,
        deduplicated.
    """
    derived: dict[str, None] = {}
    for module_path in sorted(scripts_dir.glob("build_phases*.py")):
        text = module_path.read_text(encoding="utf-8")
        for first, second in _PACKAGE_ROOT_CHAIN_RE.findall(text):
            if first in _ALREADY_COPIED_TOP_LEVEL:
                continue
            if not (repo_root / first / second).is_dir():
                continue
            derived[f"{first}/{second}"] = None
    return list(derived)


# ---- Shared helpers ----


def _build_synthetic_full_package(workspace: Path) -> Path:
    """Copy the REAL templates/, scripts/, config/ trees, plus any extra
    declared source directories, into a synthetic package root under
    ``workspace``.

    Mirrors the self-hosting production layout
    (``package_root.parent == target_root passed to build.py``) so
    ``_compute_output_mappings()``'s relative-path arithmetic behaves
    exactly as it does for a real ``python scripts/build.py --target-dir .``
    run, without mutating this worktree's own real ``.build_manifest.json``.

    Beyond the three named trees, this ALSO copies every extra directory
    ``_derive_extra_package_dirs()`` finds declared across the real
    ``build_phases*.py`` module family (currently ``docs/product-truth``,
    declared in ``build_phases_product_truth.py`` post-split) — see that
    function's docstring for why those are derived rather than hardcoded.
    Without this, a build phase whose declared source lives outside
    ``templates/``/``scripts/``/``config/`` (e.g. ``build_product_truth``)
    raises ``DeployDeclarationError`` against every synthetic package this
    helper produces, once that phase's warn-and-continue branch is made
    fail-closed (BP-900g-9) — this fixture is what was wrong, not the guard.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    shutil.copytree(_TEMPLATES_DIR, pkg_root / "templates", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_SCRIPTS_DIR, pkg_root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_CONFIG_DIR, pkg_root / "config", ignore=shutil.ignore_patterns("__pycache__"))
    for rel in _derive_extra_package_dirs(_SCRIPTS_DIR, _REPO_ROOT):
        shutil.copytree(
            _REPO_ROOT / rel, pkg_root / rel, ignore=shutil.ignore_patterns("__pycache__")
        )
    return pkg_root


def _is_build_phases_family_key(module_name: str) -> bool:
    """Return whether ``module_name`` is a bare ``build_phases`` cache key.

    Matches the bare facade name itself (``"build_phases"``) and every bare
    sibling name (``"build_phases_agents_skills"``, ``"build_phases_docs"``,
    etc.) — but NOT the per-call unique names this file and
    ``build_helpers._load_build_phases_module`` mint (e.g.
    ``"_bp100k2_build_phases_3"``), which never collide across tests and are
    intentionally left alone.

    Args:
        module_name: A ``sys.modules`` key to test.

    Returns:
        True if the key is a bare ``build_phases`` or ``build_phases_*`` name.
    """
    return module_name == "build_phases" or module_name.startswith("build_phases_")


def _snapshot_and_clear_build_phases_cache() -> dict[str, types.ModuleType]:
    """Pop every bare ``build_phases``/``build_phases_*`` entry out of ``sys.modules``.

    Returns the popped entries keyed by name so the caller can restore them
    later. Called exactly ONCE per test, from ``_isolate_build_phases_family``
    in ``setUp`` — before the synthetic package's own modules are loaded and
    before any phase function is called against them. See
    ``_isolate_build_phases_family``'s docstring for why the clear/restore
    boundary must span the WHOLE test body rather than just the module load.

    Returns:
        Mapping of removed ``sys.modules`` key to the module object it held.
    """
    keys = [name for name in sys.modules if _is_build_phases_family_key(name)]
    snapshot = {name: sys.modules[name] for name in keys}
    for name in keys:
        del sys.modules[name]
    return snapshot


def _restore_build_phases_cache(snapshot: dict[str, types.ModuleType]) -> None:
    """Undo ``_snapshot_and_clear_build_phases_cache`` — but only for entries
    whose backing file still exists on disk.

    Registered via ``addCleanup`` by ``_isolate_build_phases_family``, so
    this runs exactly ONCE, at the very END of the test — after every phase
    function the test called has already resolved its own function-scoped
    ``import build_phases as _bp``. Discards any bare
    ``build_phases``/``build_phases_*`` entry cached DURING the test (these
    all point at THIS test's synthetic package, which its
    ``TemporaryDirectory`` cleanup is about to delete) and puts back the
    entries that were present before the snapshot, EXCEPT any whose
    ``__file__`` no longer exists on disk.

    That existence check is required, not optional, because of a second-order
    effect that mattered even before this restore was moved to span the
    whole test (see ``_isolate_build_phases_family``'s docstring for that
    history): a stale snapshot entry from an EARLIER test's own
    ``TemporaryDirectory`` (since deleted) must never be handed back to a
    later test's deferred ``_bp`` import, or ``_bp.TEMPLATES_DIR`` resolves
    into a directory that no longer exists and phases silently write zero
    files. Restoring only entries that still exist on disk means a stale
    synthetic entry is dropped for good instead of being handed back; a
    later fresh ``sys.path`` search then correctly finds the CURRENT test's
    own package (still on disk, still at the front of ``sys.path``). An
    entry backed by the real, always-on-disk ``scripts/build_phases.py``
    (e.g. one cached by an unrelated test file's own bare-name import) is
    unaffected — it always passes the existence check and is restored
    exactly as before, which is the whole point: a later, unrelated test
    file's bare ``import build_phases`` must get the REAL module back.

    Args:
        snapshot: The mapping returned by ``_snapshot_and_clear_build_phases_cache``.
    """
    stale_keys = [name for name in sys.modules if _is_build_phases_family_key(name)]
    for name in stale_keys:
        del sys.modules[name]
    for name, module in snapshot.items():
        module_file = getattr(module, "__file__", None)
        if module_file is not None and not Path(module_file).exists():
            continue
        sys.modules[name] = module


def _isolate_build_phases_family(test_case: unittest.TestCase) -> None:
    """Establish a build_phases-family ``sys.modules`` boundary for one whole test.

    MUST be called from ``setUp``, before the synthetic package's own modules
    are loaded (``_load_pkg_modules`` / ``_load_fresh_module``) and before any
    phase function is called against them. Snapshots and clears every bare
    ``build_phases``/``build_phases_*`` ``sys.modules`` entry right now, and
    registers ``_restore_build_phases_cache`` via ``test_case.addCleanup`` so
    the snapshot is restored exactly once, at the very end of the test,
    regardless of pass/fail.

    WHY THE BOUNDARY MUST SPAN THE WHOLE TEST BODY, NOT JUST THE MODULE LOAD
    (the false-green this replaces): an earlier version of this fixture
    snapshotted, cleared, and restored the bare-name cache separately around
    EACH INDIVIDUAL ``_load_fresh_module`` call — i.e. only around the brief
    window in which ``build_helpers.py`` / ``build_phases.py`` /
    ``config_loader.py`` were exec'd. That window closes before any phase
    function (``build_agents``, etc.) is ever called. Every extracted phase
    function reaches shared state via a FUNCTION-SCOPED ``import build_phases
    as _bp``, evaluated when the TEST calls the function — always AFTER that
    earlier restore had already run. And the restore, by design, puts back
    any snapshotted entry whose ``__file__`` still exists on disk — which the
    REAL, always-on-disk ``scripts/build_phases.py`` always does. So the
    instant ANYTHING ELSE in the same pytest process had ever done a bare
    ``import build_phases`` (at least 11 other unit_tests/ files do exactly
    this at module level, and pytest imports every collected test module up
    front, before running any test body) — the restore handed that REAL
    module right back, and the very next phase call's ``import build_phases
    as _bp`` resolved to it instead of the synthetic copy this fixture exists
    to exercise. ``_bp.TEMPLATES_DIR`` then read the REAL repo's templates/,
    not the synthetic one. This passed unnoticed because the synthetic tree
    is a byte-for-byte copy of the real one at build time, so reading the
    wrong root produced identical output — a textbook false green.

    Confirmed empirically with a probe (see ticket comments for the full
    transcript): priming ``sys.modules['build_phases']`` with a bare
    ``import build_phases`` before this fixture's own
    ``_deploy_agents_and_write_manifest`` ran made the subsequently-called
    ``build_agents``'s own ``_bp.TEMPLATES_DIR`` resolve to the REAL repo
    root (``.../bp-size-split/templates``); without the priming import in
    the same process it correctly resolved to the synthetic
    ``pkg_root/templates``.

    The fix: clear the bare names ONCE here, before anything in the
    synthetic package is loaded, and do not restore them until the test is
    completely done exercising phase functions (via ``addCleanup``). Every
    bare name that gets (re-)cached in between — by the facade's own
    module-level sibling imports during ``_load_fresh_module``, OR by a
    phase function's later function-scoped ``import build_phases as _bp`` —
    is therefore always a FRESH resolution against ``sys.path``, which still
    has this test's synthetic ``pkg_root/scripts`` inserted at the front (see
    ``_load_pkg_modules``), so it always lands on the synthetic copy for the
    whole test. Only ``addCleanup`` — guaranteed to run once, at teardown,
    regardless of pass/fail — puts the real snapshot back, so a later,
    unrelated test file's own bare ``import build_phases`` is unaffected;
    proven by running this file back-to-back with two unrelated test files
    in one process (see the module docstring's VERIFY commands).

    Args:
        test_case: The running ``TestCase``; used only to register the
            teardown via ``addCleanup``.
    """
    snapshot = _snapshot_and_clear_build_phases_cache()
    test_case.addCleanup(_restore_build_phases_cache, snapshot)


def _load_fresh_module(module_path: Path) -> types.ModuleType:
    """Load a module from an exact file path under a unique module name.

    Never reuses a ``sys.modules`` cache entry for the module being loaded —
    this guarantees the module ITSELF is read from THIS test's own synthetic
    package copy even if some other module of the same bare name (e.g.
    "build_phases") was already imported by an unrelated test file earlier
    in the same pytest process. This matters specifically for
    ``build_phases.py``, which resolves its own package root from
    ``Path(__file__).resolve().parent.parent`` at import time rather than
    accepting it as a call parameter.

    That guarantee alone is no longer enough now that ``build_phases.py`` is
    a FACADE over a cluster of sibling modules
    (``build_phases_agents_skills.py``, ``build_phases_docs.py``, etc.),
    re-exported via bare-name ``from build_phases_<x> import (...)``
    statements at its own module level. Bare names ARE cached in
    ``sys.modules`` across tests, even though the facade itself is loaded
    under a fresh, never-reused unique name every time. Concretely: test A
    loads its facade fresh, which caches bare ``build_phases_agents_skills``
    (etc.) pointing at test A's synthetic package; test A's
    ``TemporaryDirectory`` then deletes that package; test B loads ITS
    facade fresh, but the facade's bare-name sibling imports hit test A's
    now-stale cached siblings instead of resolving against test B's own
    copy — so a sibling function's late ``import build_phases as _bp``
    resolves ``_bp.TEMPLATES_DIR`` into a directory that no longer exists,
    and the phase silently writes zero files.

    CALLERS MUST HAVE ALREADY CALLED ``_isolate_build_phases_family(self)``
    in ``setUp`` before the first call to this function in a given test.
    This function itself does NOT snapshot, clear, or restore the bare
    ``build_phases``/``build_phases_*`` cache — an earlier version wrapped
    each individual call in its own snapshot/clear/restore, which closed the
    isolation window before any phase function was ever invoked and let an
    already-cached REAL ``build_phases`` (from any OTHER test file's bare
    ``import build_phases`` earlier in the same pytest process) leak back in
    before the test body's phase calls ran — see
    ``_isolate_build_phases_family``'s docstring for the full mechanism and
    empirical proof. The bare-name cache is left exactly as
    ``_isolate_build_phases_family`` set it up for the whole test (cleared,
    on the first load), so whatever THIS load's own module-level imports
    populate under a bare name — e.g. the facade's ``from
    build_phases_agents_skills import (...)`` — resolves fresh against
    ``sys.path`` (synthetic ``pkg_root/scripts`` at the front) and stays that
    way for the rest of the test, including every later phase-function call.
    The returned module keeps direct references to whichever synthetic
    siblings it bound at import time regardless of what happens to the bare
    cache afterwards — only the TEST's own teardown (registered by
    ``_isolate_build_phases_family``) resets it, once, so this call's
    synthetic copies never leak into a later, unrelated test's fresh load.

    Args:
        module_path: Absolute path to the ``.py`` file to load.

    Returns:
        The freshly executed module object.
    """
    _UNIQUE_COUNTER[0] += 1
    unique_name = f"_bp100k2_{module_path.stem}_{_UNIQUE_COUNTER[0]}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _load_pkg_modules(pkg_root: Path):
    """Load build_helpers, build_phases, and config_loader fresh from ``pkg_root``.

    Inserts ``pkg_root/scripts`` at the front of ``sys.path`` first, so that
    each module's own internal sibling imports (e.g. ``from build_colors
    import ...``, or build_helpers's delayed ``from template_compiler
    import ...``) resolve against this same synthetic copy.

    Args:
        pkg_root: Synthetic package root built by
            ``_build_synthetic_full_package``.

    Returns:
        Tuple of (build_helpers_module, build_phases_module, config_loader_module).
    """
    scripts_dir = str(pkg_root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    build_helpers_mod = _load_fresh_module(pkg_root / "scripts" / "build_helpers.py")
    build_phases_mod = _load_fresh_module(pkg_root / "scripts" / "build_phases.py")
    config_loader_mod = _load_fresh_module(pkg_root / "scripts" / "config_loader.py")
    return build_helpers_mod, build_phases_mod, config_loader_mod


def _deploy_hook(base: Path, hook_src: Path) -> Path:
    """Copy the real check_output_drift.py into a synthesized deployed layout.

    Mirrors the real deployed relative depth
    (``<base>/.leafcutter/scripts/commit_guardian/check_output_drift.py``) —
    the exact pattern proven in
    unit_tests/commit_guardian/test_ge_118b_drift_manifest_resolution.py.

    Args:
        base: Temp directory to build the fake deployment inside.
        hook_src: Absolute path to the real hook module to copy.

    Returns:
        Absolute path to the copied hook module.
    """
    deployed_dir = base / ".leafcutter" / "scripts" / "commit_guardian"
    deployed_dir.mkdir(parents=True, exist_ok=True)
    dest = deployed_dir / hook_src.name
    shutil.copy(hook_src, dest)
    if _RESOLVE_ROOT_SRC.exists():
        shutil.copy(_RESOLVE_ROOT_SRC, deployed_dir / "_resolve_root.py")
    return dest


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed hook copy as a subprocess, exactly as pre-commit does.

    Args:
        hook_path: Absolute path to the (copied) hook module to execute.
        cwd: Working directory to run the subprocess in.

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _deploy_agents_and_write_manifest(workspace: Path, pkg_root: Path):
    """Run the REAL build_agents phase + install_shims + write_build_manifest.

    Deploys the "agents" family for every platform the build itself declares
    active — i.e. whatever ``config["platforms"]`` resolves to (BP-100n-3: a
    fixture must never pin a platform off internally, since that silently
    withholds that platform's whole output family from any equality
    assertion built on top of this manifest, regardless of what the build's
    own configuration says). ``config`` is used exactly as
    ``config_loader.load_config`` returns it — no ``"platforms"`` override is
    applied here, so the SAME fallback default ``build_agents()`` itself uses
    (``{"claude": True, "antigravity": True, "cursor": False, "copilot":
    False, "cline": False}``) is what actually governs this fixture, read
    from the production code's own default rather than a literal duplicated
    in the test.

    Args:
        workspace: The synthetic workspace/target root.
        pkg_root: The synthetic package root under ``workspace``.

    Returns:
        Tuple of (config dict used, output_root Path).
    """
    build_helpers_mod, build_phases_mod, config_loader_mod = _load_pkg_modules(pkg_root)
    config = config_loader_mod.load_config(None, workspace)
    output_root = workspace / config.get("output_root", ".leafcutter")

    build_phases_mod.build_agents(output_root, config, dry_run=False, force=True)
    build_helpers_mod.install_shims(workspace, output_root=output_root, config=config, dry_run=False, force=True)
    build_helpers_mod.write_build_manifest(pkg_root, target_root=workspace, config=config, dry_run=False)

    return config, output_root


def _load_manifest(pkg_root: Path) -> dict:
    """Read and parse the manifest for this fixture's synthetic install.

    The manifest is written to the build's ``target_root`` — here the workspace,
    ``pkg_root.parent`` — not into the package directory. That is the same root
    the deployed outputs go to, and it is what the gates use as their comparison
    base, so every key in the manifest is relative to it (BP-100k-3).

    Args:
        pkg_root: The synthetic package root. The manifest sits in its parent.

    Returns:
        The parsed manifest dict.
    """
    manifest_path = pkg_root.parent / ".build_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ---- AC-4 (BP-100k-2): output_mappings names the deployed output and its source. ----


class TestOutputMappingNamesDeployedOutputAndSource(unittest.TestCase):
    """AC-4: output_mappings resolves a deployed agent definition to its source."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)
        # See _isolate_build_phases_family's docstring — must run before any
        # module load or phase call (BP-size-split Finding 1).
        _isolate_build_phases_family(self)

    def test_output_mapping_names_the_deployed_output_and_its_source(self) -> None:
        # covers: BP-100k-2
        _deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        manifest = _load_manifest(self.pkg_root)
        output_mappings = manifest.get("output_mappings", {})

        # The REAL key check_output_drift.py would look up: repo-root-relative,
        # under the real deployed agents directory (see that module's main()).
        expected_output_key = ".claude/agents/README.md"
        self.assertIn(
            expected_output_key,
            output_mappings,
            msg=(
                f"output_mappings has no entry for {expected_output_key!r} — "
                "the real path check_output_drift.py looks up for a deployed "
                "agent definition. Today's _compute_output_mappings() keys "
                "entries as 'agents/README.md' (missing the '.claude/' "
                "prefix the real deploy+shim path carries), so every real "
                "deployed agent is permanently unregistered (BP-100k-2). "
                f"Actual output_mappings keys sample: {sorted(output_mappings.keys())[:5]}"
            ),
        )

        entry = output_mappings.get(expected_output_key, {})
        expected_template_key = (
            (self.pkg_root / "templates" / "agents" / "README.md")
            .relative_to(self.workspace)
            .as_posix()
        )
        self.assertEqual(
            entry.get("template"),
            expected_template_key,
            msg=(
                f"output_mappings[{expected_output_key!r}]['template'] does not "
                f"name the real source template {expected_template_key!r}."
            ),
        )
        self.assertIn(
            "expected_output_hash",
            entry,
            msg=f"output_mappings[{expected_output_key!r}] has no expected_output_hash field.",
        )


# ---- AC-5 (BP-100k-2): the executed output-drift gate emits match-then-drift. ----


class TestOutputDriftGateEmitsMatchThenDrift(unittest.TestCase):
    """AC-5: check_output_drift.py must compare, not skip, the deployed output."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)
        # See _isolate_build_phases_family's docstring — must run before any
        # module load or phase call (BP-size-split Finding 1).
        _isolate_build_phases_family(self)

    def test_output_drift_gate_emits_match_then_drift_for_that_output(self) -> None:
        # covers: BP-100k-2
        _deploy_agents_and_write_manifest(self.workspace, self.pkg_root)

        deployed_file = self.workspace / ".claude" / "agents" / "README.md"
        self.assertTrue(
            deployed_file.exists(),
            f"setup bug: expected a real deployed file at {deployed_file}",
        )
        original_content = deployed_file.read_bytes()

        hook_path = _deploy_hook(self.workspace, _CHECK_OUTPUT_DRIFT_SRC)
        output_key = ".claude/agents/README.md"

        # --- Leg 1: untouched deployed output must yield a MATCH verdict ---
        result_match = _run_hook(hook_path, self.workspace)
        self.assertEqual(
            0,
            result_match.returncode,
            msg=(
                "An untouched, correctly-registered deployed output must not "
                f"block the commit. stdout:\n{result_match.stdout}\n"
                f"stderr:\n{result_match.stderr}"
            ),
        )
        self.assertNotIn(
            f"{output_key} not in output_mappings",
            result_match.stderr,
            msg=(
                "check_output_drift.py reported the deployed agent definition "
                "as absent from output_mappings instead of yielding a match "
                f"verdict — the exact BP-100k-2 symptom. stderr:\n{result_match.stderr}"
            ),
        )

        # --- Leg 2: hand-edit the deployed output — must now yield DRIFT ---
        # Resolve through the shim symlink so the write lands on the real file.
        deployed_file.resolve().write_bytes(original_content + b"\n<!-- BP-100k-2 drift probe -->\n")
        result_drift = _run_hook(hook_path, self.workspace)

        self.assertEqual(
            1,
            result_drift.returncode,
            msg=(
                "check_output_drift.py must detect a hand-edit to a deployed "
                "output once it is properly registered in output_mappings. "
                f"stdout:\n{result_drift.stdout}\nstderr:\n{result_drift.stderr}"
            ),
        )
        combined = result_drift.stdout + result_drift.stderr
        self.assertIn("BLOCKED", combined, msg=f"No BLOCKED message printed. Output:\n{combined}")
        self.assertIn(output_key, combined, msg=f"BLOCKED output does not name {output_key!r}. Output:\n{combined}")


# ---- AC-6 second half (BP-100k-2): the unregistered branch must never be
# taken for any output the build actually produces. ----


class TestGateNeverReportsBuildProducedOutputUnregistered(unittest.TestCase):
    """AC-6: no build-produced output may ever be reported as unregistered."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)
        # See _isolate_build_phases_family's docstring — must run before any
        # module load or phase call (BP-size-split Finding 1).
        _isolate_build_phases_family(self)

    def test_gate_never_reports_a_build_produced_output_as_unregistered(self) -> None:
        # covers: BP-100k-2
        _deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        hook_path = _deploy_hook(self.workspace, _CHECK_OUTPUT_DRIFT_SRC)

        result = _run_hook(hook_path, self.workspace)

        self.assertNotIn(
            "not in output_mappings",
            result.stderr,
            msg=(
                "check_output_drift.py emitted a 'not in output_mappings' "
                "notice for at least one build-produced deployed file, even "
                "though every output the build actually deployed should be "
                f"covered (BP-100k-2). stderr:\n{result.stderr}"
            ),
        )


# ---- AC-6 core (BP-100k-2): output_mappings coverage equals the set of
# files the deploy phases actually wrote — count- and phase-agnostic. ----


class TestOutputMappingCoversEveryDeployPhaseOutput(unittest.TestCase):
    """AC-6: recorded output_mappings keys == the real multi-phase deploy set."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)
        # See _isolate_build_phases_family's docstring — must run before any
        # module load or phase call (BP-size-split Finding 1).
        _isolate_build_phases_family(self)

    def test_output_mapping_covers_every_deploy_phase_output(self) -> None:
        # covers: BP-100k-2
        """Exercise deploy phases from BOTH of build.py's phase families, phase
        -agnostically, not just the shimmed .claude/* families.

        No "platforms" override is applied (BP-100n-3): the build's own
        default (claude + antigravity both active) governs which families
        run, rather than a literal pinned inside the test that would
        silently withhold a whole platform's output family from the
        equality assertion below regardless of what the build declares.

        ``build_rules`` is the load-bearing phase added here. It belongs to
        build.py's ``internal_phases`` list, which -- like artifact_phases --
        is invoked with output_root, but unlike them has NO shim_map entry
        bridging its output back up to target_root. Omitting it from this
        test is how a manifest that recorded 16 .agents/rules/* keys under
        target_root, while build_rules wrote to <output_root>/.agents/rules/,
        passed a green suite: the one phase whose deploy target contradicted
        the author's mental model was the one never invoked here. Every
        family _compute_output_mappings claims to record must actually be
        deployed here, or the equality check below compares the manifest
        against a tree that was only partly built and reports phantom
        "unresolvable" keys for families this test simply never ran.

        The equality check below runs in BOTH directions. Direction 2
        (unresolvable keys) did not exist before, and its absence is
        precisely why the .agents/rules defect survived: the old
        one-directional ``actual_files - mappings.keys()`` check is
        structurally blind to a manifest key that points at a path nothing
        ever writes, since such a key is never in actual_files and so never
        appears in that difference. The consequence was silent at both
        ends -- check_output_drift's _collect_output_files skips
        directories that do not exist, so the 16 dead keys were never
        looked up and the 16 real files were never scanned: no GAP, no
        EXEMPT, no warning, a clean RESULT line. AC BP-100k-2's own
        test_spec asked for set EQUALITY ("the set of paths recorded ...
        EQUALS the set of files the deploy phases actually wrote"); only
        half of it was implemented before Direction 2 was added.
        """
        build_helpers_mod, build_phases_mod, config_loader_mod = _load_pkg_modules(self.pkg_root)
        config = config_loader_mod.load_config(None, self.workspace)
        output_root = self.workspace / config.get("output_root", ".leafcutter")
        config.setdefault("workflows", {})["enabled"] = True
        build_phases_mod.build_agents(output_root, config, dry_run=False, force=True)
        build_phases_mod.build_commands(output_root, config, dry_run=False, force=True)
        build_phases_mod.build_workflows(output_root, config, dry_run=False, force=True)
        build_phases_mod.build_hooks(output_root, config, dry_run=False, force=True)
        build_phases_mod.build_skills(output_root, config, dry_run=False, force=True)
        build_phases_mod.build_workflow_scripts(output_root, config, dry_run=False, force=True)
        build_phases_mod.build_rules(output_root, config, dry_run=False, force=True)

        build_helpers_mod.install_shims(
            self.workspace, output_root=output_root, config=config, dry_run=False, force=True
        )
        build_helpers_mod.write_build_manifest(self.pkg_root, target_root=self.workspace, config=config, dry_run=False)

        manifest = _load_manifest(self.pkg_root)
        output_mappings = manifest.get("output_mappings", {})

        deployed_dirs = [
            self.workspace / ".claude" / d
            for d in ("agents", "commands", "hooks", "skills", "workflows")
        ]
        deployed_dirs.append(output_root / ".agents" / "rules")
        actual_files: set[str] = set()
        for d in deployed_dirs:
            if not d.is_dir():
                continue
            for f in d.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts:
                    actual_files.add(f.relative_to(self.workspace).as_posix())

        self.assertTrue(actual_files, "setup bug: no real deployed output files found to test against")

        # ---- Direction 1: every real deployed file is recorded. ----
        missing = actual_files - set(output_mappings.keys())
        self.assertFalse(
            missing,
            msg=(
                f"{len(missing)} of {len(actual_files)} real deployed output "
                "file(s) across 4 distinct deploy phases (agents, commands, "
                "hooks, rules) are not recorded in output_mappings, so "
                "check_output_drift.py would report them as unregistered "
                f"rather than comparing them. Missing sample: {sorted(missing)[:10]}. "
                "output_mappings coverage must equal the set of files the "
                "deploy phases actually wrote (BP-100k-2)."
            ),
        )

        # ---- Direction 2: every recorded key resolves to a real file. ----
        # (this direction did not exist before; see this test's docstring
        # above for why its absence let the .agents/rules defect survive
        # undetected)
        unresolvable = sorted(
            key for key in output_mappings
            if not (self.workspace / key).exists()
        )
        self.assertFalse(
            unresolvable,
            msg=(
                f"{len(unresolvable)} of {len(output_mappings)} recorded "
                "output_mappings key(s) do not resolve to any file on disk "
                "after the deploy phases ran. A manifest that names a path the "
                "build never produces is not coverage -- it is a claim of "
                "coverage that no gate can act on, because a gate scanning for "
                "these files finds an absent directory and silently skips it. "
                f"Unresolvable sample: {unresolvable[:10]}. "
                "output_mappings must EQUAL what the deploy phases write, in "
                "both directions (BP-100k-2)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
