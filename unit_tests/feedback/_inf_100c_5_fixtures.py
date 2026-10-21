"""
MODULE: _inf_100c_5_fixtures
GOAL: Shared helpers for the INF-100c-5 / -i / -ii / -iii / -iv / -v test files (KI-FC-003:
    an agent that signs off but is in no feedback category's allowed_writers is silently
    refused by submit_feedback.py, and nothing checks the two lists agree).

ASSUMED PRODUCTION CONTRACT (the coder implements exactly this; the tests are red until then)
    Module ``scripts/build_phases_feedback_writers.py`` exposes one function::

        check_feedback_writers(agents_dir: Path, categories_path: Path, registry_path: Path) -> dict

    It is read-only and deterministic, and returns a dict with exactly these keys:

      missing_writers  list[str]   sorted ids of agents whose definition frontmatter sets
                                   ``signoff: true`` and that no category's allowed_writers admits
                                   (admits = submission's own rule, ``validate_writer``).
      unknown_writers  list[dict]  sorted by writer: ``{"writer": str, "categories": list[str]}``
                                   (categories sorted); a writer that is neither a submission
                                   sentinel nor an id in the agent registry. Reported once per writer.
      failures         list[str]   blocking messages. ONE message names every missing writer
                                   (sorted) as agents that sign off but can write to no feedback
                                   category; a malformed signoff value or an unreadable/malformed
                                   agent definition or categories file adds a message naming the file.
      warnings         list[str]   one line per unknown writer, naming the writer and its categories.

    ``build.py`` runs it inside ``_validate_all`` (so ``--validate-only`` runs it): a non-empty
    ``failures`` aborts the build before success is reported (exit 1, no "Config validation
    complete" line); each unknown writer is printed as ONE line that carries a ``[WARNING]`` (or
    higher) marker and the word "writer", without failing the build. The registered-agent set is
    read from ``config/agent_registry.json`` (``agents[].id``); the signing-off set from each
    ``templates/agents/*.md`` frontmatter ``signoff`` field; the writer lists from
    ``templates/config/feedback_categories.yaml``.

REAL-ARTIFACT NOTE: agent frontmatter, the categories file and the registry are written with
    ``yaml.safe_dump`` / ``json.dumps`` in the shipped shapes (never hand-typed literals). Build
    tests run the REAL ``scripts/build.py --validate-only`` as a subprocess over a copy of
    ``scripts/``, ``templates/`` and ``config/`` (no deploy, so no 60s build).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

SIX = ("complete", "knowledge-gap", "tooling-issue", "convention-ambiguity", "blocker", "success-pattern")
NINE = (*SIX, "quality-concern", "subagent-quality", "process-finding")
NEWLY_REGISTERED = ("restructuring-specialist", "change-scope-reviewer")
BUILD_TIMEOUT = 300
FEEDBACK_ID_RE = re.compile(r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$")
_REPORT_MARKER = re.compile(r"\[(WARNING|ERROR)\]|ERROR:|WARNING:")
_ABSENT = object()


def load_check():
    """Import the (not yet existing) check module; ImportError is the absence red."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import build_phases_feedback_writers  # noqa: PLC0415

    return build_phases_feedback_writers


# ---------------------------------------------------------------------------
# Unit-level world: agents dir + categories file + registry, all written by real serializers
# ---------------------------------------------------------------------------

@dataclass
class World:
    agents_dir: Path
    categories_path: Path
    registry_path: Path


def write_agent(agents_dir: Path, name: str, signoff: object = _ABSENT, **extra: object) -> Path:
    """Write ``<agents_dir>/<name>.md`` with ``yaml.safe_dump`` frontmatter (``signoff`` omitted when absent)."""
    front: dict = {"name": name, "description": f"fixture agent {name}", **extra}
    if signoff is not _ABSENT:
        front["signoff"] = signoff
    body = yaml.safe_dump(front, sort_keys=False)
    path = agents_dir / f"{name}.md"
    path.write_text(f"---\n{body}---\n\nFixture body for {name}.\n", encoding="utf-8")
    return path


def write_categories(path: Path, lists: dict[str, list[str]]) -> Path:
    """Write a categories file in the shipped shape; unspecified categories get [] (process-finding: [hook])."""
    entries = []
    for cid in NINE:
        writers = lists.get(cid, ["hook"] if cid == "process-finding" else [])
        entries.append({"id": cid, "description": f"fixture {cid}", "allowed_writers": list(writers),
                        "default_severity": "low"})
    path.write_text(yaml.safe_dump({"categories": entries}, sort_keys=False), encoding="utf-8")
    return path


def write_registry(path: Path, ids: list[str]) -> Path:
    path.write_text(json.dumps({"agents": [{"id": i, "name": i} for i in sorted(set(ids))]}, indent=2), encoding="utf-8")
    return path


def make_world(
    base: Path,
    *,
    signing: list[str],
    others: list[str] | None = None,
    lists: dict[str, list[str]],
    extra_registered: list[str] | None = None,
) -> World:
    """Agents that sign off (``signoff: true``) plus ``others`` (as given: a ``(name, signoff)`` pair or a bare name)."""
    agents_dir = base / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)  # also creates ``base``
    registered = list(signing) + list(extra_registered or [])
    for name in signing:
        write_agent(agents_dir, name, True)
    for item in others or []:
        name, signoff = item if isinstance(item, tuple) else (item, _ABSENT)
        write_agent(agents_dir, name, signoff)
        registered.append(name)
    return World(
        agents_dir,
        write_categories(base / "feedback_categories.yaml", lists),
        write_registry(base / "agent_registry.json", registered),
    )


def run_check(world: World) -> dict:
    return load_check().check_feedback_writers(world.agents_dir, world.categories_path, world.registry_path)


def failure_text(result: dict) -> str:
    return "\n".join(result["failures"])


def tree_bytes(*roots: Path) -> dict[str, bytes]:
    """Every file beneath ``roots`` -> its bytes (used to prove a check wrote and changed nothing)."""
    return {str(p): p.read_bytes() for r in roots for p in sorted(r.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# Package-copy world: real build.py --validate-only over a copy (no deploy)
# ---------------------------------------------------------------------------

def copy_package(base: Path) -> Path:
    """Copy scripts/, templates/ and config/ of the package into ``base/pkg``."""
    root = base / "pkg"
    for name in ("scripts", "templates", "config"):
        shutil.copytree(REPO_ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def categories_files(root: Path) -> list[Path]:
    return [root / "templates" / "config" / "feedback_categories.yaml", root / "config" / "feedback_categories.yaml"]


def edit_categories(root: Path, edit: Callable[[dict[str, list[str]]], None]) -> None:
    """Apply ``edit`` to the id -> allowed_writers mapping of BOTH categories files in the copy."""
    for path in categories_files(root):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        lists = {c["id"]: c["allowed_writers"] for c in data["categories"]}
        edit(lists)
        for entry in data["categories"]:
            entry["allowed_writers"] = lists[entry["id"]]
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def register_newly_registered(lists: dict[str, list[str]]) -> None:
    """What INF-100c-5-iv ships, applied to a copy so a test does not depend on the coder's order."""
    for cid in SIX:
        for name in NEWLY_REGISTERED:
            if name not in lists[cid]:
                lists[cid].append(name)


def drop_everywhere(name: str) -> Callable[[dict[str, list[str]]], None]:
    def _edit(lists: dict[str, list[str]]) -> None:
        for cid in lists:
            lists[cid] = [w for w in lists[cid] if w != name]

    return _edit


def add_to(category: str, *names: str) -> Callable[[dict[str, list[str]]], None]:
    def _edit(lists: dict[str, list[str]]) -> None:
        lists[category].extend(n for n in names if n not in lists[category])

    return _edit


def compose(*edits: Callable[[dict[str, list[str]]], None]) -> Callable[[dict[str, list[str]]], None]:
    def _edit(lists: dict[str, list[str]]) -> None:
        for one in edits:
            one(lists)

    return _edit


def validate_only(root: Path, cwd: Path) -> tuple[int, str]:
    """Run ``<root>/scripts/build.py --validate-only`` as a subprocess -> (exit code, stdout + stderr)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1")
    proc = subprocess.run(
        [sys.executable, "-B", str(root / "scripts" / "build.py"), "--validate-only"],
        capture_output=True, text=True, cwd=str(cwd), timeout=BUILD_TIMEOUT, check=False, env=env,
    )
    return proc.returncode, proc.stdout + "\n" + proc.stderr


def report_lines(output: str) -> list[str]:
    """Output lines that carry a WARNING/ERROR marker AND talk about a writer: the unknown-writer report."""
    return [ln for ln in output.splitlines() if _REPORT_MARKER.search(ln) and "writer" in ln.lower()]


def success_line_printed(output: str) -> bool:
    return "Config validation complete" in output


# ---------------------------------------------------------------------------
# Shipped categories parsing and deployed submission (INF-100c-5-iv / -v)
# ---------------------------------------------------------------------------

def shipped_lists(relative: str = "templates/config/feedback_categories.yaml") -> dict[str, list[str]]:
    data = yaml.safe_load((REPO_ROOT / relative).read_text(encoding="utf-8"))
    return {c["id"]: list(c["allowed_writers"]) for c in data["categories"]}


def deployed_submit_script(layout: Path) -> Path:
    script = Path(layout) / ".leafcutter" / "scripts" / "feedback" / "submit_feedback.py"
    assert script.is_file(), f"the shared layout has no deployed submit_feedback.py at {script}"
    return script


def submit_deployed(
    layout: Path, scratch: Path, phase: str, category: str, sink: Path, ticket: str = "GE-122e-2",
) -> subprocess.CompletedProcess:
    """Drive the DEPLOYED submit_feedback.py as a subprocess against an isolated tmp sink (``--jsonl``)."""
    tmpdir = scratch / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(tmpdir), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-B", str(deployed_submit_script(layout)), "--ticket", ticket, "--phase", phase,
         "--category", category, "--note", "INF-100c-5-v probe", "--jsonl", str(sink)],
        capture_output=True, text=True, cwd=str(scratch), timeout=60, check=False, env=env,
    )


def read_records(sink: Path) -> list[dict]:
    return [json.loads(ln) for ln in sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
