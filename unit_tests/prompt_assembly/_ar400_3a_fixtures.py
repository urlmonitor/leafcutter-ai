"""Shared helpers for the AR-400 slice-3a reference-gate tests (TDD red phase).

ASSUMED PRODUCTION CONTRACT (the coder implements exactly this; every assertion is phrased
against what the REAL entry points print or return, never against a helper name):

  * The registry validator (``python scripts/registry_validator.py`` / ``validate_agent_registry``)
    and the build (``build.py`` / ``build._validate_all``) report ONE finding line per recognised
    instruction that names an ability the specialist cannot use. Each finding line names the
    subject (specialist id or guide file), the ability text, the repo-relative file and the
    1-based line, and carries exactly one fault-kind phrase (matched case-insensitively):

        ability does not exist            (AR-400a-1, exists nowhere)
        ability exists but is not granted (AR-400b-1, not in the specialist's OWN ``skills:``)
        differs only in case              (AR-400b-2-v, text as written + canonical id named)
        names an agent, not an ability    (AR-400b-2-vi, a specialist id used as an ability)

  * An "ungranted" finding states what the own declaration grants (its ability ids, or
    "nothing"), so both sides of the mismatch sit on one line (AR-400b-1).
  * Findings print as ``ERROR: <line>`` from the validator CLI and as ``  - <line>`` from the
    commit hook; ``normalise`` strips both so the same finding compares equal across doors.

Fixtures: frontmatter bytes come from ``yaml.safe_dump`` and registry records are deep copies of
a real record (see ``_ar_400a_1_support``); the slice is a REAL copy of ``templates/`` + ``config/``.
"""

from __future__ import annotations

import copy
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402

REPO_ROOT: Path = H.REPO_ROOT
NONEXIST = "ability does not exist"
UNGRANTED = "ability exists but is not granted"
CASE = "differs only in case"
AGENT = "names an agent, not an ability"
KINDS = (NONEXIST, UNGRANTED, CASE, AGENT)


def agent_rel(name: str) -> str:
    return f"templates/agents/{name}.md"


def grant_entries(grants) -> list[dict]:
    """Grant ids (always-mode) or ready-made entry dicts (e.g. with ``provided_by``) -> entries."""
    return [g if isinstance(g, dict) else {"skill_id": g, "mode": "always"} for g in grants]


SELF_DESCRIPTION = {  # the fields a FULL build requires of every template (validator runs need none)
    "behavioral_patterns": [{"name": "Stop-and-Ask", "trigger": "out-of-scope action",
                             "behavior": "Halt immediately.", "related_agent": None}],
    "pre_flight_reads": [{"required": True, "source": "ticket_path"}],
    "inputs": [],
    "outputs": [{"name": "completion_report", "type": "structured_response", "description": "Sign-off comment"}],
    "mutates": [{"name": "none", "surface": "none", "description": "Read-only agent"}],
}


def plant(root: Path, name: str, body: list[str], *, grants: tuple = (),
          spawn: tuple[str, ...] = (), at_line: int | None = None,
          registry_grants: tuple | None = None, described: bool = False) -> Path:
    """Plant one specialist whose body is ``body`` (one entry per physical line).

    ``at_line`` puts ``body[0]`` on that 1-based line (filler before it). ``registry_grants``
    overrides the derived registry copy's abilities (default: same as the declaration).
    A non-empty ``spawn`` is written to the frontmatter ``spawn_allowlist`` AND the registry, with
    the children's ``spawned_by`` kept symmetric and the ``Agent`` tool granted (AR-200b-3).
    ``described`` adds the self-description fields a real ``build.py`` run demands."""
    tools = "Bash, Read, Skill" + (", Agent" if spawn else "")
    fm: dict = {"name": name, "description": f"{name} planted specialist", "tools": tools,
                "model": "sonnet", "produces": "analysis"}
    if spawn:
        fm["spawn_allowlist"] = list(spawn)
    fm["skills"] = grant_entries(grants)
    if described:
        fm.update(copy.deepcopy(SELF_DESCRIPTION))
    lines = ("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n").splitlines()
    if at_line is not None:
        assert len(lines) < at_line, f"frontmatter already reaches line {len(lines)}"
        lines += [H.FILLER] * (at_line - 1 - len(lines))
    lines += list(body)
    path = root / agent_rel(name)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _register(root, name, grants if registry_grants is None else registry_grants, spawn)
    return path


def _register(root: Path, name: str, grants: tuple, spawn: tuple[str, ...]) -> None:
    data = H._registry(root)
    rec = copy.deepcopy(next(a for a in data["agents"] if a["id"] == "product-owner"))
    rec.update({"id": name, "name": name, "tier": "utility", "template_path": agent_rel(name),
                "spawn_allowlist": list(spawn), "spawned_by": []})
    rec["skills_invoked"] = grant_entries(grants)
    rec.pop("skills_used", None)
    for other in data["agents"]:
        if other["id"] in spawn and name not in other.get("spawned_by", []):
            other.setdefault("spawned_by", []).append(name)
    data["agents"] = [a for a in data["agents"] if a["id"] != name] + [rec]
    H._write_registry(root, data)


def planted_skills(root: Path, *ids: str) -> None:
    for sid in ids:
        H.plant_skill(root, sid)


def line_of(path: Path, text: str) -> int:
    """1-based line of the first physical line equal to ``text`` (asserts it is there)."""
    found = [n for n, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if ln == text]
    assert found, f"{path.name} has no line equal to {text!r}"
    return found[0]


def swap(path: Path, old: str, new: str) -> None:
    """Replace ``old`` by ``new`` once, asserting the file really changed (no vacuous edit)."""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{path.name} does not contain {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def add_template_grant(root: Path, name: str, skill_id: str) -> None:
    """Add a grant to the specialist's OWN frontmatter only; the derived registry copy is left stale."""
    path = root / agent_rel(name)
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    head = yaml.safe_load(text[3:end])
    head["skills"] = list(head.get("skills") or []) + [{"skill_id": skill_id, "mode": "always"}]
    path.write_text("---\n" + yaml.safe_dump(head, sort_keys=False) + text[end + 1:], encoding="utf-8")


def edit_registry(root: Path, name: str, **fields) -> None:
    data = H._registry(root)
    next(a for a in data["agents"] if a["id"] == name).update(fields)
    H._write_registry(root, data)


def normalise(line: str) -> str:
    """A finding line without the door's own prefix (``ERROR:`` / ``  - ``)."""
    return re.sub(r"^\s*(?:ERROR:\s*|-\s+)", "", line).strip()


def findings(out: str) -> list[str]:
    """Every output line carrying a fault-kind phrase, normalised, in print order."""
    return [normalise(ln) for ln in out.splitlines() if any(k in ln.lower() for k in KINDS)]


def of_kind(out: str, kind: str, ability: str | None = None, subject: str | None = None) -> list[str]:
    return [f for f in findings(out)
            if kind in f.lower() and (ability is None or ability in f) and (subject is None or subject in f)]


def about(out: str, subject: str) -> list[str]:
    return [f for f in findings(out) if subject in f]


def names(entry: str, ability: str) -> bool:
    """``ability`` appears as a whole token (not inside a longer id)."""
    return re.search(rf"(?<![\w-]){re.escape(ability)}(?![\w-])", entry) is not None


@functools.lru_cache(maxsize=1)
def real_cli() -> tuple[int, str]:
    """The real validator CLI over the checked-out package (one run per process)."""
    return H.cli(REPO_ROOT)


def slice_cli(build) -> tuple[int, str]:
    """Make a fresh slice, let ``build(root)`` mutate it, run the CLI -> (exit, output)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = H.make_slice(tmp)
        build(root)
        return H.cli(root)


def deploy_hook_from_layout(layout: Path, root: Path) -> Path:
    """Copy the DEPLOYED commit_guardian directory of a built ``layout`` into ``root`` at the depth a
    consumer has it (``.leafcutter/scripts/commit_guardian``), and make ``root`` a package root the
    hook can resolve (a git repo with a ``.build_manifest.json`` whose ``package_root`` is "")."""
    from _ar_300c_support import output_root_name

    src = layout / output_root_name(layout) / "scripts" / "commit_guardian"
    assert (src / "check_agent_registry.py").is_file(), f"hook not deployed under {src}"
    # The slice symlinks every other top-level entry of the real tree: sever the two we write to,
    # or the copy / manifest below would land in the REAL worktree.
    for name in (".leafcutter", ".build_manifest.json"):
        link = root / name
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
    dest = root / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    (root / ".build_manifest.json").write_text(json.dumps({"package_root": ""}), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    return dest / "check_agent_registry.py"


def stage_registry(root: Path) -> None:
    """Stage the registry so the hook's scope (registry / schema / agent template staged) is hit."""
    subprocess.run(["git", "add", "config/agent_registry.json"], cwd=str(root), check=True)


def drop_grant(root: Path, agent: str, skill_id: str) -> None:
    """Remove ONE conditional grant block from an agent's own frontmatter (the registry is untouched)."""
    path = root / agent_rel(agent)
    text = path.read_text(encoding="utf-8")
    new = re.sub(rf"- skill_id: {re.escape(skill_id)}\n  mode: conditional\n  condition: [^\n]*\n", "", text, count=1)
    assert new != text, f"{agent}'s {skill_id} grant block not found to revert"
    path.write_text(new, encoding="utf-8")


def _revert(root: Path, instance: str) -> None:
    """Undo ONE 2026-10-12 instance fix on the copy, leaving everything else as shipped."""
    agents = root / "templates" / "agents"
    if instance == "research-agent":
        drop_grant(root, "research-agent", "knowledge-query")
    elif instance == "python-coder":
        swap(agents / "python-coder.md", "Resolve and load the `signoff` skill", "Resolve and load the sign-off skill")
    elif instance == "architecture-diagram-author":
        swap(agents / "architecture-diagram-author.md", "## Step 1 — Load the `write-c4-diagram` Skill",
             "## Step 1 — Load the Write-C4-Diagram Skill")
    elif instance == "sql-coder":
        swap(agents / "sql-coder.md", "also hand the query\nscaffolding to the `sql-query` sub-agent via the `Agent` tool",
             "also use the `sql-query` skill if available to scaffold\nthe query")
    else:
        assert False, f"unknown instance {instance}"


@functools.lru_cache(maxsize=None)
def reverted_cli(instance: str) -> str:
    """Validator CLI output over a copy of the real tree with ONLY ``instance``'s fix reverted."""
    return slice_cli(lambda root: _revert(root, instance))[1]
