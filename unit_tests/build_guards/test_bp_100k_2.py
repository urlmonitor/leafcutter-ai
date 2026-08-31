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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_synthetic_full_package(workspace: Path) -> Path:
    """Copy the REAL templates/, scripts/, and config/ trees into a
    synthetic package root under ``workspace``.

    Mirrors the self-hosting production layout
    (``package_root.parent == target_root passed to build.py``) so
    ``_compute_output_mappings()``'s relative-path arithmetic behaves
    exactly as it does for a real ``python scripts/build.py --target-dir .``
    run, without mutating this worktree's own real ``.build_manifest.json``.

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
    return pkg_root


def _load_fresh_module(module_path: Path) -> types.ModuleType:
    """Load a module from an exact file path under a unique module name.

    Never reuses a ``sys.modules`` cache entry — this guarantees the module
    is read from THIS test's own synthetic package copy even if some other
    module in the same bare name (e.g. "build_phases") was already imported
    by an unrelated test file earlier in the same pytest process. This
    matters specifically for ``build_phases.py``, which resolves its own
    package root from ``Path(__file__).resolve().parent.parent`` at import
    time rather than accepting it as a call parameter.

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


# ---------------------------------------------------------------------------
# AC-4 (BP-100k-2): output_mappings names the deployed output and its source.
# ---------------------------------------------------------------------------


class TestOutputMappingNamesDeployedOutputAndSource(unittest.TestCase):
    """AC-4: output_mappings resolves a deployed agent definition to its source."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)

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


# ---------------------------------------------------------------------------
# AC-5 (BP-100k-2): the executed output-drift gate emits match-then-drift.
# ---------------------------------------------------------------------------


class TestOutputDriftGateEmitsMatchThenDrift(unittest.TestCase):
    """AC-5: check_output_drift.py must compare, not skip, the deployed output."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)

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


# ---------------------------------------------------------------------------
# AC-6 second half (BP-100k-2): the unregistered branch must never be taken
# for any output the build actually produces.
# ---------------------------------------------------------------------------


class TestGateNeverReportsBuildProducedOutputUnregistered(unittest.TestCase):
    """AC-6: no build-produced output may ever be reported as unregistered."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)

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


# ---------------------------------------------------------------------------
# AC-6 core (BP-100k-2): output_mappings coverage equals the set of files
# the deploy phases actually wrote — count- and phase-agnostic.
# ---------------------------------------------------------------------------


class TestOutputMappingCoversEveryDeployPhaseOutput(unittest.TestCase):
    """AC-6: recorded output_mappings keys == the real multi-phase deploy set."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package(self.workspace)

    def test_output_mapping_covers_every_deploy_phase_output(self) -> None:
        # covers: BP-100k-2
        build_helpers_mod, build_phases_mod, config_loader_mod = _load_pkg_modules(self.pkg_root)
        config = config_loader_mod.load_config(None, self.workspace)
        # No "platforms" override here (BP-100n-3): the build's own default
        # (claude + antigravity both active) governs which families this
        # fixture exercises, rather than a literal pinned inside the test
        # that would silently withhold a whole platform's output family from
        # the equality assertion below regardless of what the build itself
        # declares.
        output_root = self.workspace / config.get("output_root", ".leafcutter")

        # Exercise deploy phases from BOTH of build.py's phase families, so
        # the invariant is proven phase-agnostic rather than a special case
        # for the shimmed .claude/* families.
        #
        # build_rules is the load-bearing addition. It belongs to build.py's
        # ``internal_phases`` list, which -- like artifact_phases -- is invoked
        # with output_root, but unlike them has NO shim_map entry bridging its
        # output back up to target_root. Omitting it from this test is how a
        # manifest that recorded 16 .agents/rules/* keys under target_root,
        # while build_rules wrote to <output_root>/.agents/rules/, passed a
        # green suite: the one phase whose deploy target contradicted the
        # author's mental model was the one phase never invoked here.
        # Every family _compute_output_mappings claims to record must actually
        # be deployed here, or the equality check below compares the manifest
        # against a tree that was only partly built and reports phantom
        # "unresolvable" keys for families this test simply never ran.
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
        #
        # This direction did not exist, and its absence is precisely why the
        # .agents/rules defect survived. The assertion was
        # ``actual_files - mappings.keys()`` alone -- a one-directional subset
        # check. A manifest key pointing at a path nothing ever writes is
        # structurally invisible to that: it is not in actual_files, so it can
        # never appear in the difference.
        #
        # The consequence was worse than an ordinary missing entry, because it
        # was silent at BOTH ends. check_output_drift's _collect_output_files
        # skips directories that do not exist, so 16 dead keys were never
        # looked up and 16 real files were never scanned -- no GAP, no EXEMPT,
        # no warning, and a clean RESULT line. AC BP-100k-2's own test_spec
        # descriptor asked for set EQUALITY ("the set of paths recorded ...
        # EQUALS the set of files the deploy phases actually wrote"); only half
        # of it was implemented.
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
