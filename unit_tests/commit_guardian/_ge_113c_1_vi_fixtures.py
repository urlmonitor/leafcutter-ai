"""
MODULE: unit_tests/commit_guardian/_ge_113c_1_vi_fixtures.py
GOAL: Shared fixture helpers for GE-113c-1-vi's test suite (RED, hand-driven
      build; the AC YAML is the spec — see docs/acceptance-criteria/
      guardrail-engine/GE-113-artifacts-cant-land-in-the-wrong-place/
      GE-113c-1-vi.yaml). Not a test file itself — mirrors the existing
      unit_tests/build_orchestration/_bo2400a1iii_fixtures.py and
      unit_tests/commit_guardian/test_ge_118b_drift_manifest_resolution.py
      helper-module conventions already used in this repo for exercising a
      commit-time hook as a real subprocess from a deployed location against
      a real temporary git repository.

THE DEFECT UNDER TEST: templates/scripts/commit_guardian/check_agent_registry.py
(live copy scripts/commit_guardian/check_agent_registry.py) computes
``package_root = repo_root / "leafcutter"`` and returns 0 — without reading
anything — when that literal path is absent. In THIS repository the package
IS the repository root (no "leafcutter/" subdirectory exists), so the
commit-time gate has never actually run here. See
docs/known-issues/commit-guardian/open-high-ki-cg-20260928-check-agent-
registry-never-runs-in-this-repo.md.

THE REQUIRED FIX (not presumed in shape — only in observable layout): locate
the package root via the shared project-root resolver
(scripts/commit_guardian/_resolve_root.py's find_project_root(), which
prefers ``git rev-parse --show-toplevel`` run from the current process's
cwd) joined with the offset recorded under the ``package_root`` key of
``.build_manifest.json`` — the SAME manifest field check_build_drift.py and
check_output_drift.py already read (see their _resolve_manifest_path() /
KI-CG-20260831-manifest-shadowing.md for the real-world shape of that
offset: "" when the package IS the project root, as in this repository, or
a subdirectory name such as "leafcutter-ai" in an outer consumer project,
where the manifest sits at that outer project's own root — a SIBLING of the
package directory, not nested inside it).

Every fixture here builds a REAL temporary git repository, deploys a REAL
copy of the hook script (either the templates/ source under review, or the
live scripts/ copy, per the "deployed" and "live vs packaged" test
requirements) under ``.leafcutter/scripts/commit_guardian/`` — the exact
relative depth the real deployed layout uses — and runs it as a REAL OS
subprocess with ``cwd`` set to the fixture repo root, exactly as
run_hook.py / pre-commit invokes it in production. ``find_project_root()``
resolves via the CURRENT PROCESS'S cwd (a real ``git rev-parse
--show-toplevel`` call), so setting the subprocess's cwd to the fixture repo
root is what makes ``find_project_root()`` resolve to that fixture repo,
regardless of where the hook script itself physically lives.

check_agent_registry.py's own registry_validator import loads sibling
modules (registry_verification_flags.py, step_kinds_validator.py,
template_compiler.py) unconditionally, so every fixture "package" copies
the ENTIRE real ``scripts/`` tree (never a hand-picked subset) — the same
completeness reasoning _bo2400a1iii_fixtures.build_git_fixture_repo's
docstring already documents for this exact hook.

step_kinds_validator.check_step_kinds() ALWAYS reads
``package_root/config/agent_registry.schema.json`` for every registry
validation (not merely when an agent sets step_kinds) and reports a hard
"step_kinds validation error" if that schema cannot be read or has no
step_kinds definition (BO-2400a-1-iii, already on origin/main as of this
worktree's base). Every fixture here therefore always writes the REAL,
unmodified schema (which already defines step_kinds) — never a hand-typed
stub schema — so the only error a broken fixture registry produces is the
one each test is actually about.

Every JSON fixture (registry, schema, manifest) is written via json.dump
from a real, loaded copy of the shipped schema or a plain Python dict —
never a hand-typed JSON string literal — per the Fixture Authenticity Rule
(test-writer skill SS2h.2).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

TEMPLATES_CG_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
TEMPLATES_HOOK_SRC = TEMPLATES_CG_DIR / "check_agent_registry.py"
LIVE_HOOK_SRC = REPO_ROOT / "scripts" / "commit_guardian" / "check_agent_registry.py"
RESOLVE_ROOT_SRC = TEMPLATES_CG_DIR / "_resolve_root.py"
CHECK_HOOK_PARITY_SRC = TEMPLATES_CG_DIR / "check_hook_parity.py"

BUILD_PY_SRC = REPO_ROOT / "scripts" / "build.py"
REAL_SCRIPTS_DIR = REPO_ROOT / "scripts"
REAL_CONFIG_DIR = REPO_ROOT / "config"
REAL_TEMPLATES_DIR = REPO_ROOT / "templates"
REAL_SCHEMA_PATH = REAL_CONFIG_DIR / "agent_registry.schema.json"
REAL_REGISTRY_PATH = REAL_CONFIG_DIR / "agent_registry.json"

_SUBPROCESS_TIMEOUT_SECONDS = 30

FIXTURE_TEMPLATE_BODY = (
    "---\n"
    "name: Fixture Agent\n"
    "produces: configuration\n"
    "---\n"
    "\n"
    "Fixture agent body for GE-113c-1-vi test fixtures.\n"
)


# ---------------------------------------------------------------------------
# Real-data loaders (Fixture Authenticity Rule SS2h.2)
# ---------------------------------------------------------------------------


def load_real_schema() -> dict[str, Any]:
    """Return a fresh in-memory copy of the REAL, shipped registry schema."""
    return json.loads(REAL_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_real_registry_agents() -> list[dict[str, Any]]:
    """Return a fresh in-memory copy of the REAL, shipped registry's agents list."""
    data = json.loads(REAL_REGISTRY_PATH.read_text(encoding="utf-8"))
    return data["agents"]


# ---------------------------------------------------------------------------
# Fixture-agent construction
# ---------------------------------------------------------------------------


def make_fixture_agent(
    template_path: str = "templates/agents/fixture-agent.md",
    **overrides: Any,
) -> dict[str, Any]:
    """Build a minimal, schema-valid registry agent entry named 'fixture-agent'.

    portable is True by default (unlike BO-2400a-1-iii's make_agent helper)
    because this AC's own scenario requires _check_template_paths to actually
    fire: "an agent entry 'fixture-agent' names a template file that does not
    exist". spawned_by is empty per the AC's test_spec description
    ("'fixture-agent' (empty spawned_by)").
    """
    entry: dict[str, Any] = {
        "id": "fixture-agent",
        "name": "Fixture Agent",
        "tier": "utility",
        "role": "testing",
        "portable": True,
        "spawn_allowlist": [],
        "spawned_by": [],
        "is_ticket_phase": False,
        "template_path": template_path,
        "skills_used": [],
        "produces": "configuration",
    }
    entry.update(overrides)
    return entry


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_registry(path: Path, agents: list[dict[str, Any]]) -> None:
    """Serialize {"agents": agents} via the real json.dump — never a hand-typed string."""
    write_json(path, {"agents": agents})


def write_schema(path: Path, schema: dict[str, Any] | None = None) -> None:
    write_json(path, schema if schema is not None else load_real_schema())


# ---------------------------------------------------------------------------
# Package construction
# ---------------------------------------------------------------------------


def build_minimal_package(
    pkg_root: Path,
    agents: list[dict[str, Any]],
    include_fixture_template: bool = False,
) -> Path:
    """A minimal but structurally-complete package: the REAL scripts/ tree
    (copied wholesale so registry_validator's sibling-module imports resolve),
    a fixture registry/schema, and an (empty by default) templates/agents/ dir.

    Used for commit-time hook subprocess scenarios, where the registry
    content is exactly the point under test and pulling in the real,
    100+-agent registry would obscure which error belongs to this test.
    """
    shutil.copytree(REAL_SCRIPTS_DIR, pkg_root / "scripts")
    write_registry(pkg_root / "config" / "agent_registry.json", agents)
    write_schema(pkg_root / "config" / "agent_registry.schema.json")
    templates_agents_dir = pkg_root / "templates" / "agents"
    templates_agents_dir.mkdir(parents=True, exist_ok=True)
    if include_fixture_template:
        (templates_agents_dir / "fixture-agent.md").write_text(
            FIXTURE_TEMPLATE_BODY, encoding="utf-8"
        )
    return pkg_root


def add_fixture_template(pkg_root: Path) -> Path:
    """Add the fixture-agent.md template file to an existing package (the
    'corrected registry' step: the missing template is supplied).
    """
    templates_agents_dir = pkg_root / "templates" / "agents"
    templates_agents_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = templates_agents_dir / "fixture-agent.md"
    tpl_path.write_text(FIXTURE_TEMPLATE_BODY, encoding="utf-8")
    return tpl_path


def build_full_real_package_copy(dest: Path) -> Path:
    """Copy the REAL scripts/, config/, templates/ trees into `dest`, so
    build.py's own __file__-derived package_root (Path(__file__).parent.parent)
    lands on real, unmodified production data when the copied scripts/build.py
    is invoked as a subprocess — the same pattern
    _bo2400a1iii_fixtures.build_full_package_copy already uses for this exact
    purpose against this exact hook family.
    """
    shutil.copytree(REAL_SCRIPTS_DIR, dest / "scripts")
    shutil.copytree(REAL_CONFIG_DIR, dest / "config")
    shutil.copytree(REAL_TEMPLATES_DIR, dest / "templates")
    return dest


def append_agent_to_registry(pkg_root: Path, agent: dict[str, Any]) -> None:
    """Append one entry to a copied package's real agent_registry.json in place."""
    reg_path = pkg_root / "config" / "agent_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["agents"].append(agent)
    write_json(reg_path, data)


# ---------------------------------------------------------------------------
# Deployment + git plumbing
# ---------------------------------------------------------------------------


def deploy_hook(base: Path, source: Path = TEMPLATES_HOOK_SRC) -> Path:
    """Copy a hook module into a synthesized deployed layout under `base`,
    mirroring the REAL deployed relative depth:
    <base>/.leafcutter/scripts/commit_guardian/check_agent_registry.py.

    _resolve_root.py is copied alongside so that a fix which imports it (the
    it_requirements name it as the resolver to reuse) resolves without any
    extra sys.path plumbing — Python auto-adds a script's own directory to
    sys.path when it is run as __main__.
    """
    deployed_dir = base / ".leafcutter" / "scripts" / "commit_guardian"
    deployed_dir.mkdir(parents=True, exist_ok=True)
    dest = deployed_dir / "check_agent_registry.py"
    shutil.copy(source, dest)
    if RESOLVE_ROOT_SRC.exists():
        shutil.copy(RESOLVE_ROOT_SRC, deployed_dir / "_resolve_root.py")
    return dest


def git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)


def git_add(repo: Path, *rel_paths: str) -> None:
    subprocess.run(["git", "add", *rel_paths], cwd=str(repo), check=True)


def write_manifest(root: Path, package_root_value: str) -> Path:
    """Write .build_manifest.json at `root`, recording `package_root` the
    same way build_helpers.write_build_manifest() does: "" when the package
    IS `root`, or a subdirectory name when the package is a named sibling
    child of `root` (KI-CG-20260831-manifest-shadowing's real-world shape).
    """
    manifest_path = root / ".build_manifest.json"
    write_json(manifest_path, {"package_root": package_root_value})
    return manifest_path


def run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed hook copy as a subprocess, exactly as pre-commit does."""
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def run_build_validate_only(pkg_root: Path, target_dir: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL `python scripts/build.py --validate-only --target-dir <target>`
    CLI entry point as a subprocess, rooted at pkg_root (see
    build_full_real_package_copy). build.py resolves its own package_root as
    Path(__file__).resolve().parent.parent — there is no CLI override — so
    pointing it at fixture data means giving it its own copy of the package.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            str(pkg_root / "scripts" / "build.py"),
            "--validate-only",
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(pkg_root),
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def run_check_hook_parity_against_real_worktree() -> subprocess.CompletedProcess:
    """Invoke the REAL check_hook_parity.py hook against THIS real worktree,
    exactly as pre-commit does (cwd = repo root)."""
    return subprocess.run(
        [sys.executable, str(CHECK_HOOK_PARITY_SRC)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
