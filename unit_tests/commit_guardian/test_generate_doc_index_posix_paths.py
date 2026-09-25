"""
MODULE: test_generate_doc_index_posix_paths
GOAL: TDD failing test stubs for TICKET-20260925-DocIndexPosixPaths.
      scripts/generate_doc_index.py interpolates ``Path.relative_to(repo_root)``
      directly into Markdown (lines 261 and 298 on origin/main 4b05997a). On a
      Windows host that renders backslash-separated link paths, and the
      transform-doc-index pre-commit hook re-stages the corrupted index on
      every commit that touches docs/*.md.
BUSINESS CONTEXT: See TICKET-20260925-DocIndexPosixPaths.md ## Context for the
      four observed real-world corruption incidents this defect has already
      caused.
ARCHITECTURE: Three areas under test:
        1. AC-1 / AC-4 — generate_index() must never emit a backslash in a
           link target or link text, and the check must reproduce on POSIX
           as well as Windows hosts (it must not rely on the host's own
           os.sep). This is done by monkeypatching ``pathlib.Path.relative_to``
           so it returns a ``PureWindowsPath`` — a pure, non-concrete path
           class whose string form always uses backslashes regardless of the
           platform Python is actually running on. Only the OS-dependent path
           *type* returned by relative_to is substituted; file discovery
           (``glob``/``exists``) and description extraction all still run for
           real against the real docs/ tree.
        2. AC-2 — every link target in a freshly generated index (real docs/
           tree, unpatched) must resolve to a file that exists relative to the
           repo root.
        3. AC-3 — the transform-doc-index hook, invoked through its REAL
           registered entry point (run_hook.py -> transform_doc_index.py, the
           exact command .pre-commit-config.yaml wires), must leave
           docs/INDEX.md with no backslash link paths after staging a docs
           change in a fresh temporary git repository.
ARCHITECTURE NOTE ON HOST-DEPENDENCE: AC-1/AC-4's test is engineered to fail
      on POSIX and Windows alike (see above). AC-3's test is NOT similarly
      patched — it shells out to the real hook entry point, which uses
      whatever pathlib flavour the host Python provides, exactly like a real
      commit would. On this authoring host (win32) it reproduces the bug
      natively. On a POSIX CI host, generate_index() already emits
      forward-slash paths natively, so this specific test would not
      reproduce the defect there — that asymmetry is inherent to a defect
      that is *itself* platform-conditional at the integration layer, and is
      not a gap in AC-4 (AC-4 only names the AC-1 test).

====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/TICKET-20260925-DocIndexPosixPaths]: Initial TDD
  stubs. Tests are RED until python-coder emits ``rel.as_posix()`` (or
  equivalent) at both interpolation sites in scripts/generate_doc_index.py
  (_render_single_file and _render_directory).
====================================================================
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CG_TEMPLATES_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_GENERATE_DOC_INDEX_SRC = _SCRIPTS_DIR / "generate_doc_index.py"
_RUN_HOOK_SRC = _CG_TEMPLATES_DIR / "run_hook.py"
_TRANSFORM_DOC_INDEX_SRC = _CG_TEMPLATES_DIR / "transform_doc_index.py"
_CHECK_OUTCOME_SRC = _CG_TEMPLATES_DIR / "check_outcome.py"

# generate_doc_index already exists on origin/main — import it directly so the
# test module always loads even before python-coder's fix lands.
sys.path.insert(0, str(_SCRIPTS_DIR))
import generate_doc_index as gdi  # noqa: E402

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")


def _extract_links(markdown: str) -> list[tuple[str, str]]:
    """Return every ``(link_text, link_target)`` pair in *markdown*."""
    return _LINK_RE.findall(markdown)


# ---------------------------------------------------------------------------
# AC-1 / AC-4: no backslash in emitted links, reproducible on any host
# ---------------------------------------------------------------------------


class TestGenerateIndexPosixLinkSeparators(unittest.TestCase):
    """AC-1: every emitted link target/text uses ``/`` as the separator.
    AC-4: this must fail against current code on POSIX as well as Windows —
    driven via ``PureWindowsPath`` rather than the host's own ``os.sep``.
    """

    def test_ac1_ac4_link_paths_have_no_backslash_on_any_host(self):
        # covers: AC-1
        # covers: AC-4
        # angle: criterion
        """Emitted link targets/text must contain no backslash, even when the
        relative path is produced as a Windows-flavoured path object.

        Monkeypatches ``pathlib.Path.relative_to`` so that every relative
        path handed to the two f-string interpolation sites in
        generate_doc_index.py (_render_single_file line ~261,
        _render_directory line ~298) arrives as a ``PureWindowsPath``. That
        class always renders with backslashes regardless of the platform the
        test suite happens to run on (it is a *pure*, non-concrete path
        class — exactly the "Windows-style paths" the AC calls for), so this
        reproduces the defect identically on POSIX and Windows CI hosts. Glob
        / exists / description-extraction all still run against the real,
        on-disk docs/ tree — only the path *type* returned by relative_to is
        substituted.

        Current state: generate_index() interpolates the Path object
        directly (``f"[{rel}]({rel})"``), so this fails with an
        AssertionError listing every backslash-containing link. Passes once
        python-coder emits ``rel.as_posix()`` at both sites.
        """
        original_relative_to = Path.relative_to

        def _as_windows_relative(self, *other, **kwargs):
            rel = original_relative_to(self, *other, **kwargs)
            return PureWindowsPath(*rel.parts)

        with patch.object(Path, "relative_to", _as_windows_relative):
            content = gdi.generate_index(_REPO_ROOT)

        links = _extract_links(content)
        self.assertGreater(
            len(links),
            0,
            "generate_index() produced no Markdown links at all against the "
            "real docs/ tree — the fixture/tree assumption is broken, not "
            "just the separator.",
        )

        offenders = [
            (text, target)
            for text, target in links
            if "\\" in text or "\\" in target
        ]
        self.assertEqual(
            offenders,
            [],
            "Every emitted link target/text must use '/' as the path "
            "separator, even when relative_to() yields a Windows-flavoured "
            f"path. Found {len(offenders)} backslash-containing link(s), "
            f"e.g. {offenders[:5]!r}. Fix: emit rel.as_posix() at both "
            "interpolation sites in scripts/generate_doc_index.py "
            "(_render_single_file, _render_directory).",
        )


# ---------------------------------------------------------------------------
# AC-2: emitted link targets resolve to real files
# ---------------------------------------------------------------------------


class TestGenerateIndexLinksResolve(unittest.TestCase):
    """AC-2: every link target in a freshly generated index resolves,
    relative to docs/ (where INDEX.md lives, KM-300a-2), to a file that exists — so the
    fix does not trade backslashes for broken paths.
    """

    def test_ac2_real_docs_tree_link_targets_resolve_to_existing_files(self):
        # covers: AC-2
        # angle: real_artifact
        """Generate the index for the REAL docs/ tree (no patching, no
        synthetic fixture) and assert every link target names a file that
        exists on disk relative to the repo root.

        Honest baseline note: on THIS host (win32) this assertion passes
        today even though the bug is confirmed present (every link target
        currently contains a backslash — see the AC-1/AC-4 test above),
        because Windows accepts '\\' as a path separator just as readily as
        '/', so Path(repo_root, target).exists() resolves correctly either
        way. This test is not forced red: it genuinely already holds, for a
        reason other than the bug being absent (per the ticket's explicit
        instruction to say so plainly rather than force it). It remains
        valuable as a regression guard once python-coder switches to
        rel.as_posix() — a broken prefix-stripping fix could still produce
        forward-slash paths that no longer resolve, and this test would
        catch that.
        """
        content = gdi.generate_index(_REPO_ROOT)
        links = _extract_links(content)
        self.assertGreater(
            len(links),
            0,
            "generate_index() produced no Markdown links against the real "
            "docs/ tree.",
        )

        missing = [
            target for _text, target in links
            if not (_REPO_ROOT / "docs" / target).exists()
        ]
        self.assertEqual(
            missing,
            [],
            f"{len(missing)} link target(s) do not resolve to an existing "
            f"file relative to docs/ (the folder INDEX.md lives in): {missing[:5]!r}",
        )


# ---------------------------------------------------------------------------
# AC-3: transform-doc-index hook via its REAL registered entry point
# ---------------------------------------------------------------------------


class TestTransformDocIndexHookEntryPointPosixPaths(unittest.TestCase):
    """AC-3: through the real transform-doc-index entry point
    (run_hook.py -> transform_doc_index.py, the exact command
    .pre-commit-config.yaml wires: 'python .leafcutter/scripts/commit_guardian/
    run_hook.py .leafcutter/scripts/commit_guardian/transform_doc_index.py'),
    a commit that stages a docs/*.md change must leave docs/INDEX.md with no
    backslash link paths.
    """

    def _build_deployed_hook_tree(self, tmp_path: Path) -> None:
        """Recreate the deployed .leafcutter/scripts/... layout in tmp_path.

        Mirrors the real deployment: run_hook.py, transform_doc_index.py and
        check_outcome.py live together under
        .leafcutter/scripts/commit_guardian/, and generate_doc_index.py is a
        sibling one level up at .leafcutter/scripts/ (the exact candidate
        _find_generator_module() searches first).
        """
        leafcutter_scripts = tmp_path / ".leafcutter" / "scripts"
        hook_dir = leafcutter_scripts / "commit_guardian"
        hook_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(_RUN_HOOK_SRC, hook_dir / "run_hook.py")
        shutil.copy2(_TRANSFORM_DOC_INDEX_SRC, hook_dir / "transform_doc_index.py")
        shutil.copy2(_CHECK_OUTCOME_SRC, hook_dir / "check_outcome.py")
        shutil.copy2(_GENERATE_DOC_INDEX_SRC, leafcutter_scripts / "generate_doc_index.py")

    def test_ac3_hook_via_run_hook_entrypoint_leaves_no_backslash_index(self):
        # covers: AC-3
        # angle: reachability
        """Stage a docs/*.md change in a fresh temp git repo, invoke the real
        'python run_hook.py transform_doc_index.py' command exactly as
        .pre-commit-config.yaml wires it, and assert the resulting
        docs/INDEX.md has no backslash link paths.

        Reachability: this drives the real production entry point (a
        subprocess invocation of run_hook.py, which itself subprocess-
        delegates to transform_doc_index.py — not a direct call to
        generate_index() or to transform_doc_index.main()) and asserts on
        the artifact it leaves on disk, not on any mock's call_args.

        Host-dependence: on THIS host (win32) this reproduces the defect
        natively, since the hook's own subprocess uses this host's pathlib
        flavour exactly as a real commit would. See the module docstring's
        "ARCHITECTURE NOTE ON HOST-DEPENDENCE" for why this specific test is
        not additionally patched to force reproduction on POSIX hosts.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._build_deployed_hook_tree(tmp_path)

            subprocess.run(
                ["git", "init", str(tmp_path)], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "-C", str(tmp_path), "config", "user.email", "test@test.test"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
                check=True, capture_output=True,
            )

            docs_dir = tmp_path / "docs" / "reference"
            docs_dir.mkdir(parents=True, exist_ok=True)
            doc_file = docs_dir / "sample.md"
            doc_file.write_text(
                "---\ntitle: Sample\ndescription: A sample doc.\n---\n\n"
                "# Sample\n\nContent.\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(tmp_path), "add", str(doc_file)],
                check=True, capture_output=True,
            )

            hook_dir = tmp_path / ".leafcutter" / "scripts" / "commit_guardian"
            result = subprocess.run(
                [
                    sys.executable,
                    str(hook_dir / "run_hook.py"),
                    str(hook_dir / "transform_doc_index.py"),
                ],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(
                result.returncode,
                0,
                f"run_hook.py -> transform_doc_index.py must exit 0 "
                f"(fail-open). stdout: {result.stdout!r} stderr: {result.stderr!r}",
            )

            index_path = tmp_path / "docs" / "INDEX.md"
            self.assertTrue(
                index_path.exists(),
                "docs/INDEX.md must be created by the real hook entry point. "
                f"Hook stdout: {result.stdout!r} stderr: {result.stderr!r}",
            )

            index_content = index_path.read_text(encoding="utf-8")
            links = _extract_links(index_content)
            offenders = [
                (text, target)
                for text, target in links
                if "\\" in text or "\\" in target
            ]
            self.assertEqual(
                offenders,
                [],
                f"docs/INDEX.md written by the real transform-doc-index "
                f"entry point must contain no backslash link paths. Found "
                f"{len(offenders)}: {offenders[:5]!r}. Hook stderr: "
                f"{result.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
