"""Shared helpers for the AR-400d (project-supplied abilities) tests (TDD red phase).

ASSUMED PRODUCTION CONTRACT (the coder implements exactly this; nothing here names a helper):

  * A grant ``{skill_id, mode, provided_by: project}`` in a specialist's own ``skills:`` frontmatter
    is looked up ONLY in ``<project>/.leafcutter/skills/<id>/SKILL.md``. An unmarked grant is
    looked up ONLY in the packaged ``templates/skills`` (no project fallback).
  * Marked, project has it     -> delivered; the compiled abilities row carries the PROJECT copy's
                                  description and says the ability is supplied by the project.
  * Marked, nobody ships it    -> the build exits 0 and prints ONE informational line (no
                                  ``[WARNING]`` / ``[ERROR]`` marker) naming the specialist, the
                                  ability, the project skills location and ``not found``; the compiled
                                  prompt offers no row for it and says it is ``not installed``.
  * Marked, package ships it, project lacks it -> falls back to the packaged copy; ONE informational
                                  line saying the project does not supply it / the packaged copy is used.
  * Marked, package ships it, project has it   -> project copy delivered to EVERY specialist
                                  granting the id, ONE informational line saying it is used in place
                                  of the packaged one; the build never overwrites or deletes it.

Consumer layout used by every e2e test: ``<base>`` is the project (``--target-dir``), the package
copy lives at ``<base>/pkg`` (the gate's project root is the package root's parent), the project's
own abilities area is ``<base>/.leafcutter/skills``. Frontmatter bytes come from ``yaml.safe_dump``.
Builds are real ``build.py`` subprocesses over a COPY, so each scenario is built once per process
(``built``) and only mutating tests take a ``fresh`` private scenario.
"""

from __future__ import annotations

import atexit
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
from _ar_300c_support import compiled_agent_roots  # noqa: E402

REPO_ROOT = F.REPO_ROOT
POSTGRES_BODY = "Apply the `postgres` skill before writing SQL"
SIGNOFF_BODY = "Apply the `signoff` skill before finishing"
PROJECT_MARK = "PROJECT-SUPPLIED-DESCRIPTION-MARKER"
BUILD_TIMEOUT = 900
_MARKERS = ("[WARNING]", "[ERROR]", "ERROR:", "WARNING:")


def marked(skill_id: str, mode: str = "always") -> dict:
    """A grant entry marked as supplied by the project."""
    return {"skill_id": skill_id, "mode": mode, "provided_by": "project"}


@dataclass
class Scenario:
    root: Path      # the package copy (<base>/pkg)
    project: Path   # the consumer project == build target (<base>)


def project_skill(project: Path, skill_id: str, description: str, area: str = ".leafcutter") -> Path:
    """Write ``<project>/<area>/skills/<id>/SKILL.md`` (frontmatter via ``yaml.safe_dump``)."""
    d = project / area / "skills" / skill_id
    d.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump({"name": skill_id, "description": description}, sort_keys=False).rstrip()
    (d / "SKILL.md").write_text(f"---\n{fm}\n---\n\nproject body for {skill_id}\n", encoding="utf-8")
    return d / "SKILL.md"


def _scratch() -> Path:
    base = Path(tempfile.mkdtemp(prefix="ar400d_"))
    atexit.register(shutil.rmtree, str(base), True)
    return base


def new_scenario(planted: list[tuple[str, list[str], tuple]], project_skills: dict[str, str]) -> Scenario:
    """A package copy with the planted specialists inside a fresh consumer project."""
    base = _scratch()
    root = H.make_build_package(base)
    (base / ".leafcutter" / "skills").mkdir(parents=True)
    for name, body, grants in planted:
        F.plant(root, name, body, grants=grants, described=True)
    for sid, description in project_skills.items():
        project_skill(base, sid, description)
    return Scenario(root=root, project=base)


def build(sc: Scenario, *extra: str) -> tuple[int, str]:
    """A real ``build.py --target-dir <project>`` over the package copy -> (exit, stdout+stderr)."""
    cp = subprocess.run([sys.executable, str(sc.root / "scripts" / "build.py"), "--target-dir", str(sc.project), *extra],
                        capture_output=True, text=True, timeout=BUILD_TIMEOUT, check=False)
    return cp.returncode, cp.stdout + "\n" + cp.stderr


_PROBE = "probe-coder"
SCENARIOS: dict[str, tuple[list, dict[str, str]]] = {
    "marked_present": ([(_PROBE, [POSTGRES_BODY], (marked("postgres"),))], {"postgres": PROJECT_MARK}),
    "marked_absent": ([(_PROBE, [POSTGRES_BODY], (marked("postgres"),))], {}),
    "unmarked_present": ([(_PROBE, [POSTGRES_BODY], ("postgres",))], {"postgres": PROJECT_MARK}),
    "unmarked_absent": ([(_PROBE, [POSTGRES_BODY], ("postgres",))], {}),
    "misspelt": ([(_PROBE, ["Apply the `complexity-reductio` skill"], ("complexity-reductio",))],
                 {"complexity-reductio": PROJECT_MARK}),
    "override": ([(_PROBE, [SIGNOFF_BODY], (marked("signoff"),)), ("probe-second", [SIGNOFF_BODY], ("signoff",))],
                 {"signoff": PROJECT_MARK}),
    "fallback": ([(_PROBE, [SIGNOFF_BODY], (marked("signoff"),))], {}),
    "real_empty": ([], {}),
}


def fresh(name: str) -> Scenario:
    """A new, private (unbuilt) copy of a named scenario, for tests that rebuild or mutate."""
    planted, project_skills = SCENARIOS[name]
    return new_scenario(planted, project_skills)


@dataclass
class Built:
    sc: Scenario
    rc: int
    out: str


@functools.lru_cache(maxsize=None)
def built(name: str) -> Built:
    """The named scenario, built once per process (read-only consumers only)."""
    sc = fresh(name)
    rc, out = build(sc)
    return Built(sc, rc, out)


def compiled(project: Path, agent: str) -> dict[str, str]:
    """``{platform root: compiled prompt}`` for ``agent`` in every root the build wrote."""
    texts = {str(r): (r / f"{agent}.md").read_text(encoding="utf-8")
             for r in compiled_agent_roots(project) if (r / f"{agent}.md").is_file()}
    assert texts, f"build wrote no compiled prompt for {agent} under {project / '.leafcutter'}"
    return texts


def ability_rows(text: str, skill_id: str) -> list[str]:
    """Rows of the delivered abilities table that start with ``| <skill_id> |``."""
    return [ln for ln in text.splitlines() if re.match(rf"^\|\s*{re.escape(skill_id)}\s*\|", ln)]


def info_lines(out: str, agent: str, ability: str, pattern: str) -> list[str]:
    """Output lines naming ``agent`` and ``ability`` that match ``pattern`` and are NEITHER a warning,
    an error, NOR a refusing finding: the informational severity."""
    return [ln.strip() for ln in out.splitlines()
            if agent in ln and F.names(ln, ability) and re.search(pattern, ln, re.IGNORECASE)
            and not any(m in ln for m in _MARKERS) and not any(k in ln.lower() for k in F.KINDS)]


def project_bytes(project: Path, skill_id: str) -> bytes:
    return (project / ".leafcutter" / "skills" / skill_id / "SKILL.md").read_bytes()


def finding_lines(out: str, agent: str, ability: str) -> list[str]:
    """Refusing 'does not exist' / 'not granted' findings for one (agent, ability)."""
    return [f for k in (F.NONEXIST, F.UNGRANTED) for f in F.of_kind(out, k, ability, agent)]
