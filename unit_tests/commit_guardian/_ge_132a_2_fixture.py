"""
MODULE: unit_tests/commit_guardian/_ge_132a_2_fixture.py
COVERS: shared fixture for the GE-132a-2 test files (test_ge_132a_2_*.py) -- a
    remedy declaration naming an agent or skill that does not exist, or giving the
    author no instructions, is refused. Holds no tests.

GOAL: Behavioural proof through a REAL ``git commit``. Builds on the GE-132a-1
    harness: the scratch repo is wired by a real ``pre-commit install`` with the
    generated ``check-hook-parity`` stanza, the DEPLOYED guardian scripts, and the
    REAL manifest and routing table re-serialised with ``json.dumps``. This module
    adds copies of the REAL agent and skill registries (copied verbatim, never
    hand-typed) and the files their ``template_path`` entries point at.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.2): the registered
    pre-commit hook -- ``git commit`` -> pre-commit -> generated stanza ->
    deployed run_hook.py -> deployed check_hook_parity.py.

REGISTRY PLACEMENT: ``config/agent_registry.json`` and ``config/skill_registry.json``
    under the scratch project root (the paths the AC's doc_links name), mirrored
    under ``.leafcutter/config/`` (the deployed layout). Template files are written
    for every registry entry (skill paths both as registered and without the
    ``leafcutter/`` prefix the registry carries), so "its template_path resolves"
    is true for every real entry and only a genuinely absent name is refused.

DECISION HISTORY
- 2026-10-12 [GE-132a-2/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    REPO_ROOT,
    SEED_RELS,
    _commit,
    _git,
    _head,
    _lines_naming,
    _real_manifest,
    _real_seed,
    _scratch,
    _stage,
    _undeclared,
    _with_parity,
    _write_tables,
)

AGENT_REGISTRY = REPO_ROOT / "config" / "agent_registry.json"
SKILL_REGISTRY = REPO_ROOT / "config" / "skill_registry.json"
REGISTRY_DIRS = ("config", ".leafcutter/config")
DEL = object()  # sentinel: remove the key from the rule
COMPLEXITY_INSTRUCTION = (
    "bring in the restructuring specialist to apply the complexity-reduction skill to the named function; "
    "never raise the limit"
)
DOC_LINKS_INSTRUCTION = "fix or remove the broken link"


def _stub(root: Path, rel: str, *, skill: bool) -> None:
    """Write the template file a registry entry points at (skills: a directory)."""
    rel = rel.rstrip("/")
    target = root / rel
    if skill and not rel.endswith(".md"):
        target = target / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"stub for {rel}\n", encoding="utf-8")


def _install_registries(root: Path) -> None:
    """Copy the REAL registries into the scratch repo and create their templates."""
    for directory in REGISTRY_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(AGENT_REGISTRY, root / directory / "agent_registry.json")
        shutil.copyfile(SKILL_REGISTRY, root / directory / "skill_registry.json")
    for entry in json.loads(AGENT_REGISTRY.read_text(encoding="utf-8"))["agents"]:
        if isinstance(entry.get("template_path"), str):
            _stub(root, entry["template_path"], skill=False)
    for entry in json.loads(SKILL_REGISTRY.read_text(encoding="utf-8"))["skills"]:
        path = entry.get("template_path")
        if isinstance(path, str):
            _stub(root, path, skill=True)
            _stub(root, path.removeprefix("leafcutter/"), skill=True)


def real_scratch(layout: Path, root: Path) -> tuple[Path, dict, dict]:
    """Scratch repo holding the REAL tables and registries; returns (repo, stanza, real_seed)."""
    manifest, seed = _real_manifest(), _real_seed()
    base = _with_parity(manifest, _undeclared(manifest, seed))
    repo, stanza = _scratch(layout, root, base, seed)
    _install_registries(repo)
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "--no-verify", "-m", "registries"], repo)
    return repo, stanza, base


def rule_of(seed: dict, hook_id: str) -> dict:
    """The rule dict of one hook inside a (mutable) routing table."""
    return next(r for r in seed["rules"] if r["hook_id"] == hook_id)


def declare(seed: dict, hook_id: str, **fields: object) -> dict:
    """Return a deep copy of ``seed`` with ``fields`` set on one rule (DEL removes a key)."""
    out = copy.deepcopy(seed)
    rule = rule_of(out, hook_id)
    for key, value in fields.items():
        if value is DEL:
            rule.pop(key, None)
        else:
            rule[key] = value
    return out


def complexity_decl(**overrides: object) -> dict:
    """Arm-one style engage-specialist fields for check-complexity, with overrides."""
    fields = {
        "disposition": "engage-specialist",
        "agent": "restructuring-specialist",
        "skills": ["complexity-reduction"],
        "instruction": COMPLEXITY_INSTRUCTION,
    }
    fields.update(overrides)
    return fields


def attempt(repo: Path, base: dict, seed: dict) -> tuple[str, subprocess.CompletedProcess]:
    """Reset the repo, stage ``seed`` as the routing-table change, and return (head, commit)."""
    _git(["reset", "-q", "--hard", "HEAD"], repo)
    _write_tables(repo, base, seed)
    _stage(repo, *SEED_RELS)
    return _head(repo), _commit(repo, "change the remedy declarations")


def block_around(output: str, name: str, radius: int = 1) -> str:
    """Lines naming ``name`` plus ``radius`` neighbours (a refusal message spans lines), lowercased."""
    lines = output.splitlines()
    hit = {i for i, line in enumerate(lines) if _lines_naming(line, name)}
    keep = sorted({j for i in hit for j in range(max(0, i - radius), min(len(lines), i + radius + 1))})
    return "\n".join(lines[j] for j in keep).lower()
