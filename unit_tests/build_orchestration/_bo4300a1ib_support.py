"""Shared support for test_bo_4300a_1_ib.py (BO-4300a-1-ib).

The subject is the DEPLOYED text of the entry skills/commands: the shared
reference layout produced by build.py (read-only), never the templates/ source.

DECLARED RULES (one place each):
    * ENTRY_SURFACES -- every deployed entry skill/command the record lists.
    * MUST_PUBLISH -- the entries that can know their work identity up front, so
      each must publish the one maker command (build-feature and finalize-feature
      leave the workspace to the workflow's own verbatim dispatch, BO-4300a-1-ia).
    * PUBLISHED_RE -- what counts as a published maker command: a line that runs
      ``worktree.py ensure``.
    * A published command must name the maker by an ABSOLUTE path (or a
      placeholder standing for one), never cwd-relative, and be ONE simple
      command (no ``&&``, ``||``, ``;``, pipe or ``$(...)``).
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import World, build_world, git_ok
from ._bo4300a1ia_support import affirmative

TICKET_REL = "tickets/TICKET-20260927-ib-demo.md"
TICKET_BYTES = b"---\nstatus: todo\n---\n# ib demo ticket\nunique-marker-4300a1ib\n"

# (kind of surface, name)
ENTRY_SURFACES = (
    ("commands", "build-feature"),
    ("commands", "fast-lane-build"),
    ("commands", "finalize-feature"),
    ("commands", "plan-feature"),
    ("commands", "quick-fix"),
    ("skills", "build-single-ticket"),
    ("skills", "feature"),
    ("skills", "plan-feature"),
    ("skills", "quick-fix"),
)
MUST_PUBLISH = (
    ("commands", "fast-lane-build"),
    ("commands", "plan-feature"),
    ("commands", "quick-fix"),
    ("skills", "build-single-ticket"),
    ("skills", "feature"),
    ("skills", "plan-feature"),
    ("skills", "quick-fix"),
)

PUBLISHED_RE = re.compile(
    r"python3?\s+[\"']?(?P<prog>\S*worktree\.py)[\"']?\s+ensure\b(?P<rest>[^`\n]*)")
PLACEHOLDER_RE = re.compile(r"[<$\{]")
COMPOUND_RE = re.compile(r"&&|\|\||;|\||\$\(")
DASH_C_COMMIT_RE = re.compile(r"git\s+(?:-[Cc]\s+\S+\s+)+commit\b")


def deployed_root() -> Path:
    return Path(get_or_produce_shared_layout())


def surface_path(kind: str, name: str) -> Path:
    base = deployed_root() / ".claude" / kind
    return base / name / "SKILL.md" if kind == "skills" else base / f"{name}.md"


def surface_text(kind: str, name: str) -> str:
    path = surface_path(kind, name)
    assert path.is_file(), f"deployed entry surface missing: {path}"
    return path.read_text(encoding="utf-8")


def deployed_maker() -> Path:
    return deployed_root() / ".leafcutter" / "scripts" / "worktree.py"


def published_commands(text: str) -> list[dict]:
    """Every maker command the text publishes, with its program token and args."""
    found = []
    for line in affirmative(text).splitlines():
        match = PUBLISHED_RE.search(line)
        if match:
            found.append({"line": line, "cmd": match.group(0),
                          "prog": match.group("prog"),
                          "rest": match.group("rest").strip()})
    return found


def is_absolute_or_placeholder(prog: str) -> bool:
    return prog.startswith(("/", "~")) or bool(re.match(r"[A-Za-z]:[\\/]", prog)) \
        or bool(PLACEHOLDER_RE.match(prog))


def is_one_simple_command(command: dict) -> bool:
    """The command text, and the text just before it on its line, chain nothing."""
    before = command["line"].split(command["cmd"], 1)[0]
    return not COMPOUND_RE.search(before + command["cmd"])


def new_world_with_ticket() -> tuple[World, Path]:
    world = build_world(deployed_maker().parent)
    seed2 = world.base / "seed2"
    git_ok(world.base, world.env, "clone", str(world.hub), str(seed2))
    target = seed2 / TICKET_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(TICKET_BYTES)
    git_ok(seed2, world.env, "add", "-A")
    git_ok(seed2, world.env, "commit", "-m", "add ib demo ticket")
    git_ok(seed2, world.env, "push", "origin", "HEAD:main")
    git_ok(world.project, world.env, "pull", "--ff-only", "origin", "main")
    return world, world.project / TICKET_REL


def run_published(world: World, command: dict, slug: str, ticket: Path):
    """Run the published command AS WRITTEN: the same flags, the placeholders
    filled with this world's values, the maker being the deployed one.
    Returns (completed process, parsed stdout or None, argv)."""
    tokens = shlex.split(command["rest"])
    fill = {"--kind": "ticket", "--slug": slug, "--ticket": str(ticket),
            "--repo-root": str(world.project)}
    argv: list[str] = []
    skip = False
    for i, tok in enumerate(tokens):
        if skip:
            skip = False
            continue
        if tok in fill and i + 1 < len(tokens):
            value = tokens[i + 1]
            argv += [tok, fill[tok] if PLACEHOLDER_RE.search(value) else value]
            skip = True
        else:
            argv.append(tok)
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(deployed_maker()), "ensure", *argv],
        cwd=str(world.project), env=world.env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=300, check=False)
    try:
        payload = json.loads(done.stdout)
    except ValueError:
        payload = None
    return done, payload, argv
