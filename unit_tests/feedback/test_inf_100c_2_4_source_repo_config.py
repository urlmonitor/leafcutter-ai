"""
MODULE: unit_tests/feedback/test_inf_100c_2_4_source_repo_config.py
GOAL: AC INF-100c-2 -- submit_feedback.py run from the leafcutter source at
      leafcutter-ai/scripts/feedback/ finds leafcutter-ai/config/
      feedback_categories.yaml, with backward compatibility preserved.
      AC INF-100c-4 -- when the file is found nowhere, the error names every
      absolute path that was checked and says how to fix it.
      Parent INF-100c -- from a deployed project, every listed writer submits.
BUSINESS CONTEXT: In the source repo, scripts/feedback/ is the gitignored build
      shim, a symlink into .leafcutter/scripts/feedback/. Before INF-100c-2 the
      script then looked only in .leafcutter/config/ and never in the repo's
      own config/. Every test runs the real script in a subprocess, from a small
      temporary copy of that layout. The script directory has to be copied
      rather than linked, because a link would resolve into templates/ and so
      test a different layout. No build.py is spawned.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_FEEDBACK_DIR = _REPO_ROOT / "templates" / "scripts" / "feedback"
_SOURCE_CATEGORIES = _REPO_ROOT / "config" / "feedback_categories.yaml"
_FEEDBACK_ID_RE = r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$"
_CATEGORIES = "feedback_categories.yaml"

# A deployed copy that lacks the "complete" category, so a run that reads it is
# told apart from one that reads the source copy.
_DEPLOYED_ONLY_YAML = (
    "categories:\n"
    "  - id: deployed-only\n"
    "    default_severity: low\n"
    "    allowed_writers: [test-runner]\n"
)


def _make_repo(base: Path, *, shim: bool, deployed: str | None, source: bool) -> Path:
    """Lay out a source repo under *base* and return its root.

    Args:
        base: Empty temporary directory.
        shim: True for scripts/feedback as a symlink into
            .leafcutter/scripts/feedback (the current build shim); False for a
            real scripts/feedback directory (the older layout).
        deployed: Text for .leafcutter/config/feedback_categories.yaml, or
            None to leave that file absent.
        source: Whether config/feedback_categories.yaml exists in the repo.
    """
    repo = base / "leafcutter-ai"
    (repo / ".leafcutter" / "config").mkdir(parents=True)
    (repo / "scripts").mkdir()
    ignore = shutil.ignore_patterns("__pycache__")
    if shim:
        shutil.copytree(_SOURCE_FEEDBACK_DIR, repo / ".leafcutter" / "scripts" / "feedback", ignore=ignore)
        os.symlink(Path("..") / ".leafcutter" / "scripts" / "feedback", repo / "scripts" / "feedback")
    else:
        shutil.copytree(_SOURCE_FEEDBACK_DIR, repo / "scripts" / "feedback", ignore=ignore)
    if deployed is not None:
        (repo / ".leafcutter" / "config" / _CATEGORIES).write_text(deployed, encoding="utf-8")
    if source:
        (repo / "config").mkdir()
        shutil.copy2(_SOURCE_CATEGORIES, repo / "config" / _CATEGORIES)
    return repo


def _submit(script: Path | str, cwd: Path, jsonl: Path) -> subprocess.CompletedProcess[str]:
    """Run the real CLI with an explicit --jsonl sink; never touches a real log."""
    return subprocess.run(
        [sys.executable, str(script), "--ticket", "tickets/x.md", "--phase", "test-runner",
         "--category", "complete", "--note", "INF-100c-2/4 probe", "--jsonl", str(jsonl)],
        capture_output=True, text=True, cwd=str(cwd), timeout=30,
    )


def _probe_categories_file(script: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Print _CATEGORIES_FILE as the script computes it, from a fresh process.

    A fresh process keeps the script's sibling imports out of this one.
    """
    code = (
        "import runpy, sys; "
        "g = runpy.run_path(sys.argv[1], run_name='inf_100c_probe'); "
        "print(g['_CATEGORIES_FILE'])"
    )
    return subprocess.run(
        [sys.executable, "-c", code, str(script)],
        capture_output=True, text=True, cwd=str(cwd), timeout=30,
    )


class TestSourceRepoLocation(unittest.TestCase):
    """AC INF-100c-2: config resolution works from the source repo location."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="lc_inf100c2_")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.jsonl = self.base / "fb.jsonl"

    def _resolved_categories_file(self, script: Path) -> str:
        result = _probe_categories_file(script, self.base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_shim_without_deployed_copy_submits_using_source_config(self):
        # covers: INF-100c-2
        # angle: criterion
        """Run through leafcutter-ai/scripts/feedback/ (the shim) with no
        deployed copy: the submission succeeds on leafcutter-ai/config/."""
        repo = _make_repo(self.base, shim=True, deployed=None, source=True)
        result = _submit(repo / "scripts" / "feedback" / "submit_feedback.py", self.base, self.jsonl)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout.strip(), _FEEDBACK_ID_RE)
        self.assertTrue(self.jsonl.is_file())

    def test_shim_without_deployed_copy_resolves_to_source_config_file(self):
        # covers: INF-100c-2
        # angle: criterion
        """The file the script resolves is leafcutter-ai/config/feedback_categories.yaml."""
        repo = _make_repo(self.base, shim=True, deployed=None, source=True)
        found = self._resolved_categories_file(repo / "scripts" / "feedback" / "submit_feedback.py")
        self.assertEqual(os.path.realpath(found), os.path.realpath(repo / "config" / _CATEGORIES))

    def test_shim_still_prefers_deployed_copy_when_present(self):
        # covers: INF-100c-2
        # angle: regression
        """Backward compatibility with INF-100c-1: the deployed copy, when it
        exists, is still the one read, ahead of the source copy."""
        repo = _make_repo(self.base, shim=True, deployed=_DEPLOYED_ONLY_YAML, source=True)
        script = repo / "scripts" / "feedback" / "submit_feedback.py"
        found = self._resolved_categories_file(script)
        self.assertEqual(
            os.path.realpath(found),
            os.path.realpath(repo / ".leafcutter" / "config" / _CATEGORIES),
        )
        result = _submit(script, self.base, self.jsonl)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Unknown category 'complete'", result.stderr)

    def test_real_directory_layout_still_submits(self):
        # covers: INF-100c-2
        # angle: regression
        """Backward compatibility: a real scripts/feedback/ directory in the
        repo still reads the repo's config/."""
        repo = _make_repo(self.base, shim=False, deployed=None, source=True)
        result = _submit(repo / "scripts" / "feedback" / "submit_feedback.py", self.base, self.jsonl)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout.strip(), _FEEDBACK_ID_RE)

    def test_canonical_source_script_in_place_still_submits(self):
        # covers: INF-100c-2
        # angle: regression
        """Backward compatibility: the canonical source script, run in place
        from templates/scripts/feedback/, still finds its config."""
        script = _SOURCE_FEEDBACK_DIR / "submit_feedback.py"
        result = _submit(script, self.base, self.jsonl)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout.strip(), _FEEDBACK_ID_RE)


class TestMissingConfigNamesEveryPathChecked(unittest.TestCase):
    """AC INF-100c-4: the error names the absolute path(s) that were checked."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="lc_inf100c4_")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.jsonl = self.base / "fb.jsonl"
        self.repo = _make_repo(self.base, shim=True, deployed=None, source=False)
        self.deployed_path = str(self.repo / ".leafcutter" / "config" / _CATEGORIES)
        self.source_path = str(self.repo / "config" / _CATEGORIES)

    def _checked_lines(self, stderr: str) -> list[str]:
        prefix = "Checked path:"
        return [ln.strip()[len(prefix):].strip() for ln in stderr.splitlines() if ln.strip().startswith(prefix)]

    def test_missing_everywhere_lists_every_absolute_path_checked(self):
        # covers: INF-100c-4
        # angle: criterion
        """Neither copy exists: exit 1, and one 'Checked path:' line per
        location tried -- the deployed one and the source-repo one."""
        result = _submit(self.repo / "scripts" / "feedback" / "submit_feedback.py", self.base, self.jsonl)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        checked = [os.path.realpath(p) for p in self._checked_lines(result.stderr)]
        self.assertEqual(
            checked,
            [os.path.realpath(self.deployed_path), os.path.realpath(self.source_path)],
            result.stderr,
        )

    def test_paths_are_absolute_when_script_is_invoked_by_relative_path(self):
        # covers: INF-100c-4
        # angle: edge
        """Invoked as a relative path from the parent directory, every checked
        path is still printed absolute, and a fix is named."""
        relative = Path("leafcutter-ai") / "scripts" / "feedback" / "submit_feedback.py"
        result = _submit(relative, self.base, self.jsonl)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        checked = self._checked_lines(result.stderr)
        self.assertEqual(len(checked), 2, result.stderr)
        for path in checked:
            self.assertTrue(os.path.isabs(path), f"not absolute: {path!r}\n{result.stderr}")
        self.assertIn("To fix:", result.stderr)

    def test_missing_config_writes_nothing_and_prints_no_id(self):
        # covers: INF-100c-4
        # angle: edge
        """The failure is clean: empty stdout and no sink file created."""
        result = _submit(self.repo / "scripts" / "feedback" / "submit_feedback.py", self.base, self.jsonl)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(self.jsonl.exists())


_EVERY_WRITER_PROBE = """
import json, runpy, sys
g = runpy.run_path(sys.argv[1], run_name="inf_100c_probe")
failed = []
for writer, category in json.loads(sys.argv[2]):
    args = ["--ticket", "tickets/x.md", "--phase", writer, "--category", category,
            "--note", "INF-100c probe", "--jsonl", sys.argv[3]]
    try:
        code = g["main"](args)
    except SystemExit as exc:
        code = exc.code
    if code != 0:
        failed.append([writer, category, code])
print(json.dumps({"categories_file": str(g["_CATEGORIES_FILE"]), "failed": failed}))
"""


class TestDeployedProjectSubmission(unittest.TestCase):
    """Parent INF-100c: from a deployed project, the config is found at the
    deployed path and every listed writer is accepted."""

    def test_every_listed_writer_submits_from_a_deployed_project(self):
        # covers: INF-100c
        # angle: criterion
        """Copy the real script into <project>/.leafcutter/scripts/feedback/
        with the real categories file at .leafcutter/config/ only, then submit
        once for every writer the file lists: each submission succeeds."""
        import json

        import yaml

        with tempfile.TemporaryDirectory(prefix="lc_inf100c_") as tmp:
            base = Path(tmp)
            lc = base / "project" / ".leafcutter"
            shutil.copytree(_SOURCE_FEEDBACK_DIR, lc / "scripts" / "feedback",
                            ignore=shutil.ignore_patterns("__pycache__"))
            (lc / "config").mkdir()
            shutil.copy2(_SOURCE_CATEGORIES, lc / "config" / _CATEGORIES)
            cats = yaml.safe_load(_SOURCE_CATEGORIES.read_text(encoding="utf-8"))["categories"]
            pairs: dict[str, str] = {}
            for cat in cats:
                for writer in cat.get("allowed_writers") or []:
                    if writer != "hook":
                        pairs.setdefault(writer, cat["id"])
            self.assertTrue(pairs, "the real categories file lists no agent writers")
            jsonl = base / "fb.jsonl"
            result = subprocess.run(
                [sys.executable, "-c", _EVERY_WRITER_PROBE,
                 str(lc / "scripts" / "feedback" / "submit_feedback.py"),
                 json.dumps(sorted(pairs.items())), str(jsonl)],
                capture_output=True, text=True, cwd=str(base), timeout=120,
                env={**os.environ, "TMPDIR": str(base)},
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(
                os.path.realpath(report["categories_file"]),
                os.path.realpath(lc / "config" / _CATEGORIES),
            )
            self.assertEqual(report["failed"], [])
            self.assertEqual(len(jsonl.read_text(encoding="utf-8").splitlines()), len(pairs))


if __name__ == "__main__":
    unittest.main()
