"""
MODULE: test_bp017_shim_relative_targets
GOAL: Failing (RED) test baseline for BP-017 — install_shims() must record
    symlink targets RELATIVE to the link's own parent directory, not as
    absolute, developer-machine paths.
TICKET: BP-017
ACS: BP-017

BUSINESS CONTEXT (see docs/acceptance-criteria/build_pipeline/BP-017.yaml):
    install_shims() (scripts/build_helpers.py) builds both canonical_path and
    source_path as absolute paths and passes the absolute source_path
    straight into Path.symlink_to() (both the directory-shim path via
    _create_shim and the single-file-shim path via _create_file_shim). Every
    shim therefore bakes in one machine's directory layout, which breaks any
    tree that is moved, copied, rsynced, or bind-mounted to a different
    absolute path (this is what made BP-016's damage possible). This ticket
    requires:
      1. Reading a link back returns a relative path (no leading "/", no
         machine-specific directory name), expressed from the LINK'S OWN
         parent directory — not the build's invocation cwd. A link nested one
         level deep (.claude/agents, scripts/commit_guardian) carries one
         leading "../" step; a link at the project root (.gemini,
         .pre-commit-config.yaml) carries none.
      2. Each link still resolves to exactly the same real file/directory it
         did when the target was absolute.
      3. Moving/copying the whole tree (links + output root together) to a
         different absolute path leaves every link resolvable — none goes
         dangling.
      4. Re-running the build over an already-relative shim leaves the
         recorded target byte-for-byte unchanged.
      5. Re-running the build over a shim left absolute by an earlier build
         REPLACES the recorded target with the relative form.
      6. When the canonical location and the output root have no common
         ancestor (no relative path can be expressed), the link falls back to
         an absolute target and the build still completes (does not raise).
      7. The copy strategy is untouched by this AC — a copy records no
         target at all.

ARCHITECTURE: Real-artifact behavioral tests (BP-1100f-2 / repo CLAUDE.md
    "Real-artifact behavioral spot-check"). Every test below invokes the REAL
    install_shims() against REAL temporary directories (tempfile), lets it
    actually create the shims on disk, and reads the shims back with
    os.readlink() / Path.resolve() — it does not mock the symlink call or
    assert on call_args. This is deliberate: a topology-only test (asserting
    that Path.symlink_to was *called* with some argument) cannot distinguish
    "records a relative target" from "records an absolute target", which is
    exactly the defect this AC exists to fix.

Currently RED: install_shims()/_create_shim()/_create_file_shim() pass the
absolute source_path directly to symlink_to(); every assertion here that
checks for a relative recorded target fails against today's implementation.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Path setup — resolves to leafcutter-ai repo root, then scripts/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_helpers  # noqa: E402  (path must be set up first)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

# Directory shims that sit ONE level below the target root (expect one
# leading "../" once relative).
_NESTED_DIR_SHIMS = (
    (".claude/agents", "agents"),
    (".claude/skills", "skills"),
    (".claude/commands", "commands"),
    (".claude/hooks", "hooks"),
    (".claude/workflows", "workflows"),
    ("scripts/commit_guardian", "scripts/commit_guardian"),
    ("scripts/doc_compliance", "scripts/doc_compliance"),
    ("scripts/feedback", "scripts/feedback"),
)

# Directory shim that sits AT the target root (expect zero leading "../").
_ROOT_DIR_SHIM = (".gemini", "gemini")

# File shim that sits AT the target root (expect zero leading "../").
_ROOT_FILE_SHIM = (".pre-commit-config.yaml", "pre-commit-config.yaml")

_ALL_OUTPUT_RELS = (
    "agents",
    "skills",
    "commands",
    "hooks",
    "workflows",
    "gemini",
    "scripts/commit_guardian",
    "scripts/doc_compliance",
    "scripts/feedback",
    "pre-commit-config.yaml",
    "settings.json",
)


def _populate_output_root(output_root: Path) -> None:
    """Create real, non-empty source artifacts for every shim source_path."""
    for rel in _ALL_OUTPUT_RELS:
        dest = output_root / rel
        if rel.endswith(".yaml") or rel.endswith(".json"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"# fixture content for {rel}\n")
        else:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "marker.txt").write_text(f"fixture marker for {rel}\n")


class TestBP017ShimRelativeTargets(unittest.TestCase):
    """RED baseline: install_shims() must record relative symlink targets."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bp017_shim_test_")
        self.addCleanup(self._tmp.cleanup)
        self.target_root = Path(self._tmp.name) / "project"
        self.target_root.mkdir(parents=True)
        self.output_root = self.target_root / ".leafcutter"
        self.output_root.mkdir(parents=True)
        _populate_output_root(self.output_root)

    # -- AC-BP-017 core: relative target format ---------------------------

    def test_ac_bp017_nested_dir_shim_reads_back_relative_with_one_parent_step(self) -> None:
        # covers: BP-017
        """.claude/agents (one level below target_root) must read back as
        "../.leafcutter/agents" — one leading parent step, relative to the
        LINK's own parent directory (.claude/), not the process cwd.
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / ".claude" / "agents"
        self.assertTrue(canonical.is_symlink(), f"{canonical} is not a symlink")
        recorded_target = os.readlink(canonical)
        self.assertFalse(
            recorded_target.startswith("/"),
            f"expected a relative target, got absolute path: {recorded_target!r}",
        )
        self.assertEqual(
            recorded_target,
            "../.leafcutter/agents",
            f"expected '../.leafcutter/agents', got {recorded_target!r}",
        )

    def test_ac_bp017_root_dir_shim_reads_back_relative_with_zero_parent_steps(self) -> None:
        # covers: BP-017
        """.gemini (at target_root) must read back as ".leafcutter/gemini" —
        zero leading parent steps.
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / ".gemini"
        self.assertTrue(canonical.is_symlink(), f"{canonical} is not a symlink")
        recorded_target = os.readlink(canonical)
        self.assertEqual(
            recorded_target,
            ".leafcutter/gemini",
            f"expected '.leafcutter/gemini', got {recorded_target!r}",
        )

    def test_ac_bp017_root_file_shim_reads_back_relative(self) -> None:
        # covers: BP-017
        """.pre-commit-config.yaml (at target_root) must read back as
        ".leafcutter/pre-commit-config.yaml".
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / ".pre-commit-config.yaml"
        self.assertTrue(canonical.is_symlink(), f"{canonical} is not a symlink")
        recorded_target = os.readlink(canonical)
        self.assertEqual(
            recorded_target,
            ".leafcutter/pre-commit-config.yaml",
            f"expected '.leafcutter/pre-commit-config.yaml', got {recorded_target!r}",
        )

    def test_ac_bp017_nested_scripts_shim_reads_back_relative(self) -> None:
        # covers: BP-017
        """scripts/commit_guardian must read back as
        "../.leafcutter/scripts/commit_guardian" (explicit example from the
        AC criteria).
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / "scripts" / "commit_guardian"
        self.assertTrue(canonical.is_symlink(), f"{canonical} is not a symlink")
        recorded_target = os.readlink(canonical)
        self.assertEqual(
            recorded_target,
            "../.leafcutter/scripts/commit_guardian",
            f"expected '../.leafcutter/scripts/commit_guardian', got {recorded_target!r}",
        )

    # -- AC-BP-017: destination unchanged ----------------------------------

    def test_ac_bp017_relative_target_resolves_to_same_destination_as_absolute_would(
        self,
    ) -> None:
        # covers: BP-017
        """Regardless of how the target is recorded, the link must resolve
        to exactly the same real file/directory inside the output root.
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / ".claude" / "agents"
        expected_destination = (self.output_root / "agents").resolve()
        self.assertEqual(canonical.resolve(), expected_destination)
        # Explicitly assert the recorded target is NOT the absolute
        # destination string — i.e. it must actually be relative, not just
        # coincidentally resolve correctly because it's absolute.
        recorded_target = os.readlink(canonical)
        self.assertNotEqual(
            recorded_target,
            str(expected_destination),
            "recorded target is the absolute destination path — not relative",
        )

    # -- AC-BP-017: survives move/copy of the whole tree -------------------

    def test_ac_bp017_shims_survive_relocation_of_the_whole_tree(self) -> None:
        # covers: BP-017
        """After copying BOTH the links and the output root they point into
        to a different absolute path, every link must still resolve inside
        the relocated tree — none may be left dangling.
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        relocated_parent = Path(self._tmp.name) / "relocated"
        relocated_root = relocated_parent / "project"
        shutil.copytree(self.target_root, relocated_root, symlinks=True)

        canonical = relocated_root / ".claude" / "agents"
        self.assertTrue(canonical.is_symlink(), f"{canonical} is not a symlink")
        self.assertTrue(
            canonical.exists(),
            "shim is dangling after relocation — recorded target must have "
            "been absolute (baked in the original machine path)",
        )
        resolved = canonical.resolve()
        self.assertTrue(
            str(resolved).startswith(str(relocated_root.resolve())),
            f"shim resolved OUTSIDE the relocated tree: {resolved} "
            f"(relocated root: {relocated_root.resolve()}) — target was not "
            "relative to the link's own location",
        )

    # -- AC-BP-017: idempotent on an already-relative shim ------------------

    def test_ac_bp017_rerun_over_already_relative_shim_leaves_target_unchanged(
        self,
    ) -> None:
        # covers: BP-017
        """Re-running the build over a shim that is already relative must
        leave the recorded target unchanged, character for character.
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / ".claude" / "agents"
        first_target = os.readlink(canonical)

        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )
        second_target = os.readlink(canonical)
        self.assertEqual(
            first_target,
            second_target,
            "rebuilding over an already-relative shim changed the recorded "
            "target",
        )
        # Anchor: the unchanged value itself must actually be relative —
        # otherwise this assertion is vacuously true against today's
        # absolute-only implementation.
        self.assertFalse(first_target.startswith("/"))

    # -- AC-BP-017: absolute shim from an earlier build gets replaced ------

    def test_ac_bp017_rerun_over_absolute_shim_replaces_it_with_relative_target(
        self,
    ) -> None:
        # covers: BP-017
        """A shim left absolute by an earlier (unfixed) build must have its
        target REPLACED with the relative form on the next rebuild — no
        absolute shim should survive a rebuild.
        """
        canonical = self.target_root / ".claude" / "agents"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        absolute_source = (self.output_root / "agents").resolve()
        canonical.symlink_to(absolute_source, target_is_directory=True)
        self.assertTrue(os.readlink(canonical).startswith("/"))  # sanity

        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "symlink"},
            dry_run=False,
            force=True,
        )

        recorded_target = os.readlink(canonical)
        self.assertFalse(
            recorded_target.startswith("/"),
            f"absolute shim from a prior build was NOT replaced with a "
            f"relative target on rebuild: {recorded_target!r}",
        )
        self.assertEqual(recorded_target, "../.leafcutter/agents")

    # -- AC-BP-017: no-common-ancestor fallback stays absolute + completes -

    def test_ac_bp017_no_common_ancestor_falls_back_to_absolute_and_build_completes(
        self,
    ) -> None:
        # covers: BP-017
        """When no relative path can be expressed between the canonical
        location and the output root (e.g. different drives on Windows,
        simulated here by forcing os.path.relpath to raise ValueError for
        exactly one shim pair), that ONE shim falls back to an absolute
        target and install_shims() still completes without raising — while
        every OTHER shim in the same run is still recorded relative.
        """
        real_relpath = os.path.relpath

        def _relpath_raises_for_agents(path, start=os.curdir):
            # Simulate "no common ancestor" only for the .claude/agents pair;
            # every other pair must still succeed and be recorded relative.
            if str(path).endswith(str(Path("agents"))) or "agents" in str(path):
                if "agents" in str(path) and ".claude" in str(start or ""):
                    raise ValueError("path is on mount point with no relative path")
            return real_relpath(path, start)

        with mock.patch("os.path.relpath", side_effect=_relpath_raises_for_agents):
            try:
                build_helpers.install_shims(
                    self.target_root,
                    output_root=self.output_root,
                    config={"shim_strategy": "symlink"},
                    dry_run=False,
                    force=True,
                )
            except ValueError as exc:
                self.fail(
                    "install_shims() must catch the no-common-ancestor case "
                    f"and fall back to an absolute target, not raise: {exc}"
                )

        agents_link = self.target_root / ".claude" / "agents"
        self.assertTrue(agents_link.is_symlink())
        agents_target = os.readlink(agents_link)
        self.assertTrue(
            agents_target.startswith("/"),
            "expected the no-common-ancestor fallback to record an absolute "
            f"target, got {agents_target!r}",
        )

        # A shim NOT affected by the simulated fallback must still be
        # relative in the SAME run.
        gemini_link = self.target_root / ".gemini"
        self.assertTrue(gemini_link.is_symlink())
        gemini_target = os.readlink(gemini_link)
        self.assertFalse(
            gemini_target.startswith("/"),
            f"unaffected shim should still be relative, got {gemini_target!r}",
        )

    # -- AC-BP-017: copy strategy is untouched (must NOT regress) ----------

    def test_ac_bp017_copy_strategy_unaffected_no_target_recorded(self) -> None:
        # covers: BP-017
        """A copy-strategy shim is a real copied directory, not a symlink —
        this AC imposes nothing on it. Guards against a fix that accidentally
        starts treating copies as links.
        """
        build_helpers.install_shims(
            self.target_root,
            output_root=self.output_root,
            config={"shim_strategy": "copy"},
            dry_run=False,
            force=True,
        )
        canonical = self.target_root / ".claude" / "agents"
        self.assertTrue(canonical.is_dir())
        self.assertFalse(canonical.is_symlink())


if __name__ == "__main__":
    unittest.main()
