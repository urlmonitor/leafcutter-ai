"""INF-700b-2 follow-up (pr-reviewer 2026-10-23 13:00, M-1 and M-3) -- TDD red phase.

M-1  ``scripts/check_skill_refs.py`` must fail (non-zero, naming the registry) when the
     registry file EXISTS but is unreadable / malformed JSON / has no ``agents`` list / an
     empty one. Only an ABSENT registry may tolerate an empty population. Run as the real CLI
     (subprocess) over a temp package copy, one registry variant per test.

M-3  The widened ``check-agent-registry`` hook is in scope only for the PACKAGE's templates
     (paths under the resolved package root's ``templates/``), never a consumer project's own
     ``templates/*.md``. Run the entry string from a generated pre-commit config, as a real
     subprocess, in a consumer-style temp git repo where the package lives under
     ``leafcutter-ai/`` (manifest ``package_root`` = ``leafcutter-ai``) and the hook is deployed
     under ``.leafcutter/scripts/commit_guardian/``.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_HOOK_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
CLI = REPO_ROOT / "scripts" / "check_skill_refs.py"
HOOK_ID = "check-agent-registry"
DANGLING = "no-such-skill"
DANGLING_SENTENCE = f"Load the `{DANGLING}` skill before you continue."
PKG = "leafcutter-ai"
PKG_SKILL = "templates/skills/signoff/SKILL.md"
_TIMEOUT = 180
_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
_GENERATE_CONFIG = (
    "import sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from build_precommit import build_precommit_config\n"
    "build_precommit_config(Path(sys.argv[2]), {'output_root': '.leafcutter'}, False, True)\n"
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=_TIMEOUT,
                          env=_ENV, check=False)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=str(repo),
                   check=True, capture_output=True, env=_ENV)


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


class TestCliRegistryPresenceM1(unittest.TestCase):
    """The CLI is run over a temp package copy whose registry file is varied."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.root = Path(cls._tmp.name) / "pkg"
        cls.root.mkdir()
        # templates/agents is left out on purpose: sql-coder's `provided_by: project` skills are
        # only resolvable through the real registry, so with it present every registry variant
        # would exit 1 for that unrelated reason and the refusals could not be told apart from it.
        shutil.copytree(REPO_ROOT / "templates", cls.root / "templates",
                        ignore=shutil.ignore_patterns("__pycache__", "agents"))
        (cls.root / "config").mkdir()

    def _run_with_registry(self, content: str | None) -> tuple[int, str]:
        reg = self.root / "config" / "agent_registry.json"
        if reg.exists():
            reg.unlink()
        if content is not None:
            reg.write_text(content, encoding="utf-8")
        cp = _run([sys.executable, str(CLI), "--repo-root", str(self.root)], REPO_ROOT)
        return cp.returncode, cp.stdout + "\n" + cp.stderr

    def _assert_refused(self, content: str) -> None:
        code, out = self._run_with_registry(content)
        self.assertNotEqual(code, 0, f"registry {content!r} present but unusable yet CLI exited 0: {out}")
        self.assertRegex(out, r"(?i)registry|agent_registry", out)
        self.assertNotIn("OK:", out)

    def test_m1_malformed_json_registry_is_refused(self):
        # covers: INF-700b-2
        # angle: failure
        """Registry file exists but is not JSON: non-zero, naming the registry. Red: prints OK."""
        self._assert_refused("{ this is not json")

    def test_m1_registry_without_agents_key_is_refused(self):
        # covers: INF-700b-2
        # angle: failure
        """Registry is valid JSON but has no ``agents`` list. Red: prints OK."""
        self._assert_refused("{}")

    def test_m1_registry_with_empty_agents_list_is_refused(self):
        # covers: INF-700b-2
        # angle: boundary
        """Registry exists with ``"agents": []``: zero definitions examined must fail."""
        self._assert_refused('{"agents": []}')

    def test_m1_registry_with_non_list_agents_is_refused(self):
        # covers: INF-700b-2
        # angle: boundary
        """``agents`` present but not a list is malformed, not an empty population."""
        self._assert_refused('{"agents": "oops"}')

    def test_m1_absent_registry_still_tolerated_control(self):
        # covers: INF-700b-2
        # angle: criterion
        """CONTROL: no registry file at all (bare templates/ tree) keeps exiting 0 -- the only
        state allowed to tolerate an empty population. Passes for a different reason than the
        refusals above (nothing to read vs. something unusable)."""
        code, out = self._run_with_registry(None)
        self.assertEqual(code, 0, out)


class TestHookScopeIsPackageTemplatesOnlyM3(unittest.TestCase):
    """Consumer-style layout: package under ``leafcutter-ai/``, consumer's own ``templates/``."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        base = Path(cls._tmp.name)
        dest = base / "generated"
        dest.mkdir()
        cp = subprocess.run([sys.executable, "-c", _GENERATE_CONFIG, str(REPO_ROOT / "scripts"),
                             str(dest)], capture_output=True, text=True, timeout=_TIMEOUT,
                            env=_ENV, check=False)
        assert cp.returncode == 0, cp.stderr
        produced = sorted(p for p in dest.iterdir() if p.name.endswith("pre-commit-config.yaml"))
        assert produced, f"no pre-commit config generated: {cp.stdout} {cp.stderr}"
        config = yaml.safe_load(produced[0].read_text(encoding="utf-8"))
        stanzas = [h for r in config["repos"] for h in r["hooks"] if h.get("id") == HOOK_ID]
        assert len(stanzas) == 1, stanzas
        cls.entry = stanzas[0]["entry"]
        cls.repo = base / "project"
        cls.repo.mkdir()
        for name in ("scripts", "config", "templates"):
            _copy(REPO_ROOT / name, cls.repo / PKG / name)
        _copy(SHIPPED_HOOK_DIR, cls.repo / ".leafcutter" / "scripts" / "commit_guardian")
        (cls.repo / ".build_manifest.json").write_text(f'{{"package_root": "{PKG}"}}', encoding="utf-8")
        (cls.repo / "templates").mkdir()
        (cls.repo / "templates" / "notes.md").write_text("# consumer notes\n", encoding="utf-8")
        _git(cls.repo, "init", "-q")
        _git(cls.repo, "add", "-A")
        _git(cls.repo, "commit", "-q", "-m", "baseline")

    def setUp(self) -> None:
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        _git(self.repo, "reset", "-q", "--hard")
        _git(self.repo, "clean", "-fdq")

    def _stage_append(self, rel: str, sentence: str) -> None:
        path = self.repo / rel
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + sentence + "\n",
                        encoding="utf-8")
        _git(self.repo, "add", rel)

    def _plant_broken_registry(self) -> None:
        """Unstaged, so ONLY a validator run can notice it."""
        (self.repo / PKG / "config" / "agent_registry.json").write_text("{ broken", encoding="utf-8")

    def _hook(self) -> tuple[int, str]:
        argv = shlex.split(self.entry)
        self.assertEqual(argv[0], "python", self.entry)
        argv[0] = sys.executable
        cp = _run(argv, self.repo)
        return cp.returncode, cp.stdout + "\n" + cp.stderr

    def test_m3_consumer_own_templates_markdown_is_out_of_scope(self):
        # covers: INF-700b-2
        # angle: failure
        """Staging the CONSUMER's own ``templates/notes.md`` exits 0 even though the package
        registry is deliberately broken (a validator run would reject it): the hook must not run
        the validator at all for a path outside the package's templates. Red today: any
        ``*/templates/*.md`` triggers full package validation."""
        self._plant_broken_registry()
        self._stage_append("templates/notes.md", "A consumer note naming no skill.")
        code, out = self._hook()
        self.assertEqual(code, 0, f"consumer's own templates/ markdown triggered validation: {out}")
        self.assertNotIn("validation failed", out)

    def test_m3_package_template_with_dangling_reference_is_refused(self):
        # covers: INF-700b-2
        # angle: reachability
        """Staging ``leafcutter-ai/templates/skills/signoff/SKILL.md`` with a dangling skill
        reference is refused naming the template path and the skill (package scope kept)."""
        self._stage_append(f"{PKG}/{PKG_SKILL}", DANGLING_SENTENCE)
        code, out = self._hook()
        self.assertNotEqual(code, 0, out)
        self.assertTrue([ln for ln in out.splitlines() if PKG_SKILL in ln and DANGLING in ln],
                        f"no error line names {PKG_SKILL} and {DANGLING}: {out}")
        self.assertTrue([ln for ln in out.splitlines() if ln.startswith(f"[{HOOK_ID}]")
                         and re.search(r"skill[- ]reference", ln, re.I)], out)

    def test_m3_broken_registry_is_rejected_for_a_package_template_control(self):
        # covers: INF-700b-2
        # angle: criterion
        """CONTROL for the consumer-own test: the SAME planted broken registry makes the hook
        fail when a PACKAGE template is staged, so the consumer-own exit 0 there can only mean
        the validator was not run (not that the plant is harmless). Green today."""
        self._plant_broken_registry()
        self._stage_append(f"{PKG}/{PKG_SKILL}", "This paragraph names no skill.")
        code, out = self._hook()
        self.assertNotEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
