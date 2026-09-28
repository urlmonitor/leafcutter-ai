"""
MODULE: unit_tests/build_orchestration/_bo2400a1iii_fixtures.py
GOAL: Shared fixture helpers for BO-2400a-1-iii's step_kinds test suite
      (test_bo2400a_1_iii_step_kinds.py). Not a test file itself — mirrors the
      existing _bo2400f13_fixtures.py helper-module convention in this directory.

Every JSON fixture here is DERIVED from the real, on-disk artifacts
(config/agent_registry.schema.json, config/agent_registry.json) via json.load +
in-memory mutation + json.dump — never a hand-typed literal — per the Fixture
Authenticity Rule (test-writer skill §2h.2). The only hand-authored piece is the
minimal "fixture-agent" registry entry itself, which is intentionally synthetic
(it must not exist in the real registry) but is written to disk through the
real json.dump serializer, exactly as build.py / the registry itself would.

ASSUMED PRODUCTION API (none of this exists yet — see the report for the
full rationale):
  - scripts/registry_validator.py gains:
      * get_agent_step_kinds(agent: dict) -> frozenset[str]
        The one shared reader. Returns frozenset() for both an absent
        'step_kinds' key and an explicit empty list.
      * A new internal check (wired into validate_agent_registry()) that
        reads the allowed-kinds enum from
        package_root/config/agent_registry.schema.json's
        definitions.agent.properties.step_kinds.items.enum and rejects any
        agent entry whose step_kinds contains an unknown or duplicated
        value, naming both the offending kind and the agent id.
  - config/agent_registry.schema.json gains
    definitions.agent.properties.step_kinds = {type: array, uniqueItems: true,
    items: {enum: [reads_store, changes_store, changes_repository, publishes]}},
    NOT added to definitions.agent.required.
No new CLI flag or env var is assumed for build.py or check_agent_registry.py:
both are invoked exactly as they exist today (see the two subprocess helpers
below), because a full package_root copy is sufficient to point each real
entry point at fixture data without a new seam.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "config" / "agent_registry.schema.json"
REGISTRY_PATH = REPO_ROOT / "config" / "agent_registry.json"
CHECK_AGENT_REGISTRY_SCRIPT = (
    REPO_ROOT / "scripts" / "commit_guardian" / "check_agent_registry.py"
)
TEMPLATES_CHECK_AGENT_REGISTRY_SCRIPT = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_agent_registry.py"
)
BUILD_PY = REPO_ROOT / "scripts" / "build.py"

KNOWN_KINDS = ("reads_store", "changes_store", "changes_repository", "publishes")

_SCRIPTS_DIR = str(REPO_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def load_real_schema() -> dict[str, Any]:
    """Return a fresh in-memory copy of the REAL, shipped registry schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def make_agent(agent_id: str = "fixture-agent", step_kinds: list | None = None, **overrides: Any) -> dict[str, Any]:
    """Build a minimal, schema-valid (apart from step_kinds) registry agent entry.

    portable is False by default so the entry never needs a real template file
    or skills directory to satisfy validate_agent_registry()'s other checks —
    keeping every test's fixture registry a single, self-contained entry.
    """
    entry: dict[str, Any] = {
        "id": agent_id,
        "name": "Fixture Agent",
        "tier": "utility",
        "role": "testing",
        "portable": False,
        "spawn_allowlist": [],
        "spawned_by": ["user"],
        "is_ticket_phase": False,
        "template_path": None,
        "skills_used": [],
        "produces": "configuration",
    }
    if step_kinds is not None:
        entry["step_kinds"] = step_kinds
    entry.update(overrides)
    return entry


def write_registry(path: Path, agents: list[dict[str, Any]]) -> None:
    """Serialize {"agents": agents} via the real json.dump — never a hand-typed string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump({"agents": agents}, fh, indent=2)


def write_schema(path: Path, schema: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2)


def build_min_package(tmp_path: Path, agents: list[dict[str, Any]], schema: dict[str, Any] | None = None) -> Path:
    """Minimal package_root (config/ only) for an IN-PROCESS validate_agent_registry() call.

    registry_validator.py itself is never copied — the REAL worktree copy
    (already on sys.path via _SCRIPTS_DIR above) is imported directly and
    simply pointed at this fixture package_root, the same pattern
    unit_tests/test_build_guard_real_package.py already uses for
    _check_script_reference_guard(synthetic_root).
    """
    pkg = tmp_path / "pkg"
    write_registry(pkg / "config" / "agent_registry.json", agents)
    write_schema(
        pkg / "config" / "agent_registry.schema.json",
        schema if schema is not None else load_real_schema(),
    )
    return pkg


def schema_with_extra_kind(extra_kind: str = "fixture_kind") -> dict[str, Any]:
    """Real schema, deep-mutated in memory to add a 5th step_kinds enum value.

    Raises KeyError today (pre-implementation: no step_kinds definition
    exists yet) — that KeyError IS this fixture's honest red signal for
    test_fifth_kind_added_to_schema_is_accepted_without_gate_edit, not a
    fixture bug: it disappears the moment the schema gains the step_kinds
    definition this AC requires.
    """
    schema = load_real_schema()
    step_kinds_def = schema["definitions"]["agent"]["properties"]["step_kinds"]
    enum = list(step_kinds_def["items"]["enum"])
    enum.append(extra_kind)
    step_kinds_def["items"]["enum"] = enum
    return schema


def build_package_with_broken_schema(tmp_path: Path, agents: list[dict[str, Any]], mode: str) -> Path:
    """Minimal package_root whose config/agent_registry.schema.json is broken
    in one of three ways, for the fail-closed regression test.

    Args:
        mode: one of "missing" (no schema file at all), "invalid_json" (the
            file exists but is not parseable JSON), or "no_step_kinds_def"
            (valid JSON, real shipped schema, but
            definitions.agent.properties.step_kinds has been removed).

    "invalid_json" is the one case in this whole fixture module that is NOT
    derived from a real serializer: a real json.dump can never produce
    invalid JSON, so there is no "real producer" for this fixture to be
    authentic to — a hand-typed broken string is the only way to represent
    "corrupted file on disk" at all. The other two modes still derive from
    the real, loaded schema (mode "no_step_kinds_def" deletes a key from the
    real, loaded dict before writing it back via json.dump).
    """
    pkg = tmp_path / "pkg"
    write_registry(pkg / "config" / "agent_registry.json", agents)
    schema_path = pkg / "config" / "agent_registry.schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "missing":
        pass  # deliberately do not write the schema file at all
    elif mode == "invalid_json":
        schema_path.write_text("{ not valid json ", encoding="utf-8")
    elif mode == "no_step_kinds_def":
        schema = load_real_schema()
        del schema["definitions"]["agent"]["properties"]["step_kinds"]
        write_schema(schema_path, schema)
    else:
        raise ValueError(f"unknown mode: {mode!r}")

    return pkg


def build_full_package_copy(tmp_path: Path) -> Path:
    """Copy scripts/, config/, templates/ into a tmp dir so build.py's own
    __file__-derived package_root resolution (Path(__file__).parent.parent)
    lands on fixture data when the copied scripts/build.py is invoked.

    This is the only way to point the real `build.py --validate-only` CLI at
    fixture data: build.py never accepts a package-root override, so
    "pointed at a temporary fixture package" means giving it its own copy of
    the package to be the root of, not a new CLI flag.
    """
    pkg = tmp_path / "full_pkg"
    shutil.copytree(REPO_ROOT / "scripts", pkg / "scripts")
    shutil.copytree(REPO_ROOT / "config", pkg / "config")
    shutil.copytree(REPO_ROOT / "templates", pkg / "templates")
    return pkg


def append_agent_to_registry(pkg: Path, agent: dict[str, Any]) -> None:
    """Append one entry to a copied package's real agent_registry.json in place."""
    reg_path = pkg / "config" / "agent_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["agents"].append(agent)
    reg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_build_validate_only(pkg_root: Path, target_dir: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL `python scripts/build.py --validate-only --target-dir <target>`
    CLI entry point as a subprocess, rooted at pkg_root (see build_full_package_copy).
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
    )


def build_git_fixture_repo(tmp_path: Path, agents: list[dict[str, Any]], schema: dict[str, Any] | None = None) -> Path:
    """A REAL git repo with a REAL staged leafcutter/config/agent_registry.json,
    so the unmodified check_agent_registry.py's own `git diff --cached` discovers
    it exactly as it would at a real commit — no HOOK_TEST_STAGED_FILES seam
    needed; real `git add` already satisfies the hook's own staged-file check.

    package_root = <repo>/leafcutter (no leading dot) because that is what
    check_agent_registry.py's own `main()` computes today
    (`repo_root / "leafcutter"`) — confirmed empirically against this very
    repo, which uses `.leafcutter/` (with a dot) as its build OUTPUT root and
    therefore has no bare `leafcutter/` directory: the commit-time gate is a
    silent no-op here today absent this fixture layout.

    The entire scripts/ tree is copied (not just registry_validator.py)
    because validate_verification_flags() unconditionally imports the sibling
    template_compiler module before its own template_dir.exists() guard —
    confirmed empirically; copying only registry_validator.py raises
    ModuleNotFoundError('template_compiler') from inside the real,
    unmodified check_agent_registry.py, which is a fixture-completeness bug,
    not a signal about the code under test.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    pkg = repo / "leafcutter"
    shutil.copytree(REPO_ROOT / "scripts", pkg / "scripts")
    write_registry(pkg / "config" / "agent_registry.json", agents)
    write_schema(
        pkg / "config" / "agent_registry.schema.json",
        schema if schema is not None else load_real_schema(),
    )

    subprocess.run(
        ["git", "add", "leafcutter/config/agent_registry.json"],
        cwd=repo,
        check=True,
    )
    return repo


def run_check_agent_registry(repo_root: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL, unmodified scripts/commit_guardian/check_agent_registry.py
    (the check-agent-registry hook's own script) as a subprocess, cwd'd into a
    fixture git repo built by build_git_fixture_repo().
    """
    return subprocess.run(
        [sys.executable, str(CHECK_AGENT_REGISTRY_SCRIPT)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
