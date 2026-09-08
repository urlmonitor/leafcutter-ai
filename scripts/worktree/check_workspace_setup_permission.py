#!/usr/bin/env python3
"""
MODULE: check_workspace_setup_permission
GOAL: Executable pre-flight that answers "may the configured workspace-setup
    agent run repository-mutating shell commands?" by reading
    config/agent_registry.json locally -- never by dispatching an agent to
    read it.

BUSINESS CONTEXT: The plan-feature workflow's Pre-Stage-0 step dispatches
    the isolated-workspace setup (fetch, branch-create, `git worktree add`
    via setup_ticket_worktree.py). That step must only ever run on an agent
    whose registered charter (config/agent_registry.json) grants
    `permits_shell: true`. The workflow used to establish that fact by
    dispatching a status-checker agent to run a shell command and return the
    registry's raw contents -- a network round-trip taken solely to read a
    static local file. A transport hiccup on that ONE dispatch
    (KI-ACD-009 cause 2: "[resolve-workspace-setup-permission] failed: API
    Error: Connection lost mid-response") closed the mandated entry point
    and was, in the run's own output, indistinguishable from a genuine
    mis-assignment.

    ACD-2100b-5 removes that round-trip. The E2 workflow engine (ADR-030)
    contextifies a workflow script's body with exactly the injected globals
    agent, parallel, pipeline, phase, log, args, workflow, and budget -- no
    module loader and no filesystem primitive of any kind (canonical
    statement: unit_tests/_workflow_engine_harness.py docstring, "ENGINE
    FIDELITY" section) -- so the workflow body itself physically cannot read
    this file. This script exists so the plan-feature SKILL, which runs in
    the main agent loop with real Bash/Read access, can do the local read
    BEFORE the workflow is invoked, and pass the resulting verdict into the
    workflow through `args.workspace_setup_permission` -- the only injected
    global that carries caller-supplied data. Precedent for a skill-invoked
    pre-flight script on this same surface: scripts/ac_store/scan_ac_orphans.py,
    invoked from templates/skills/plan-feature/SKILL.md's own sec-PRR.

ARCHITECTURE: Pure stdlib. Resolves the repository root the run is actually
    operating on the SAME repository-anchored way ACD-2100a-1 and
    ACD-2100a-3 already established for this workflow (git-common-dir
    based, worktree-aware) -- never a second, independent, cwd-relative
    resolution -- so this pre-flight reaches the project's real registry
    even when invoked from inside a linked git worktree that holds no
    `.leafcutter/` of its own. Reads
    `<repo_root>/.leafcutter/config/agent_registry.json`, looks up the
    `--agent-id` entry, and prints exactly one JSON object to stdout:
    `{"permits": bool, "outcome": <str>, ...}`. `outcome` is one of
    "granted", "read_failure", "parse_failure", "agent_not_found",
    "no_entries_collection", "permission_denied" -- kept distinguishable
    from one another (never collapsed to a single boolean) so the workflow
    can render the same specific reports ACD-2100b-1 through -3 require.
    The verdict is a pure function of the registry's on-disk contents: it
    never branches on whether any agent-dispatch transport is available, so
    "skip the check when dispatch is unavailable" cannot re-enter through
    this surface. Always exits 0 with a verdict object on stdout, even when
    the verdict denies permission or the registry could not be read/parsed
    -- a non-zero exit is reserved for a totally malformed invocation
    (e.g. unparseable CLI arguments), never for a well-formed denial.

    Beyond `permits`/`outcome`/`agent_id`/`location`, the verdict carries
    outcome-specific detail so the caller's report can state more than the
    bare enum value (ACD-2100b-1 AC-2, ACD-2100b-2 AC-4, ACD-2100b-3-i AC-1
    -- closing information-loss gaps between what `_load_registry()` and
    `_resolve_agent_outcome()` observe and what previously only reached
    `logger.warning()`):
      - "read_failure": `reason` (a human-readable sentence distinguishing
        "no file at that location" from "permission refused" -- the two
        different OSError causes) and `detail` (the raw exception text).
      - "parse_failure": `reason`, plus the underlying
        `json.JSONDecodeError`'s own `position` / `line` / `column` and
        `detail`.
      - "no_entries_collection": `agents_type` (the malformed value's
        Python type name) and, when it is a JSON scalar, `agents_value`
        (the value itself).
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_AGENT_ID = "worktree-agent"
REGISTRY_RELATIVE_PATH = Path(".leafcutter") / "config" / "agent_registry.json"
GIT_COMMON_DIR_TIMEOUT_SECONDS = 10


def _git_common_dir(candidate_dir: Path) -> str | None:
    """Return ``git rev-parse --git-common-dir``'s stdout for ``candidate_dir``.

    Returns None when the directory is not inside a git repository, or when
    the ``git`` invocation itself fails for any reason. This is external
    I/O (a subprocess call), so any failure is logged at WARNING per the
    repository error-handling policy; callers treat None as "not a repo
    here" and continue probing, exactly as
    templates/workflows-js/plan-feature.js's own
    ``_buildRepoRootResolutionSnippet()`` does.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate_dir), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=GIT_COMMON_DIR_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning(
            "git rev-parse --git-common-dir failed for %s: %s", candidate_dir, exc
        )
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def _repo_root_from_common_dir(base_dir: Path, common_dir_output: str) -> Path:
    """Resolve ``git-common-dir``'s (possibly relative) output to the
    repository root (its parent directory), anchored at ``base_dir`` if the
    output itself is relative.
    """
    common_path = Path(common_dir_output)
    if not common_path.is_absolute():
        common_path = (base_dir / common_path).resolve()
    return common_path.parent


def _probe_children_for_repo_root(probe_base: Path) -> Path | None:
    """Return the repo root of the first immediate, non-hidden child
    directory of ``probe_base`` that is itself a git repository (sorted for
    determinism), or None if none is.

    Mirrors templates/workflows-js/plan-feature.js's
    ``_buildRepoRootResolutionSnippet()`` child-probe fallback (its `*/`
    shell glob, which likewise never matches hidden directories).
    """
    try:
        candidates = sorted(
            p for p in probe_base.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
    except OSError as exc:
        logger.warning("Could not list %s while resolving the repo root: %s", probe_base, exc)
        return None
    for candidate in candidates:
        common_dir = _git_common_dir(candidate)
        if common_dir:
            return _repo_root_from_common_dir(candidate, common_dir)
    return None


def resolve_repo_root(start_dir: Path) -> Path | None:
    """Resolve the repository root this process is actually operating on,
    worktree-aware, the SAME way ACD-2100a-1 / ACD-2100a-3 already
    established for this workflow -- never a second, independent,
    cwd-relative resolution (it_requirements: "the registry-location
    semantics must not fork").

    Resolution order:
      1. ``git rev-parse --git-common-dir``'s parent directory from
         ``start_dir`` itself -- the same answer whether ``start_dir`` is
         the main checkout or a linked worktree of it, since all worktrees
         of a repository share one ``.git`` directory.
      2. The immediate (non-hidden) children of ``start_dir``, each probed
         the same way (the ADR-001 self-hosting layout: ``start_dir`` is
         the untracked workspace parent, and the repository lives one
         level down).
      3. The immediate (non-hidden) children of ``start_dir``'s own parent
         (i.e. ``start_dir``'s siblings), probed the same way (``start_dir``
         is itself a directory with no filesystem relationship to the
         repository, but shares a workspace parent with it).

    Returns None if none of the above resolves -- callers must fail closed
    rather than fall back to a cwd-relative guess that could silently
    select the wrong physical registry.
    """
    common_dir = _git_common_dir(start_dir)
    if common_dir:
        return _repo_root_from_common_dir(start_dir, common_dir)

    child_result = _probe_children_for_repo_root(start_dir)
    if child_result is not None:
        return child_result

    return _probe_children_for_repo_root(start_dir.parent)


def _load_registry(registry_path: Path) -> tuple[object | None, dict[str, object] | None]:
    """Read and parse the agent registry at ``registry_path``.

    Returns ``(registry_json, failure)`` where ``failure`` is None on
    success, or a dict the caller merges directly into the verdict on
    failure. ``failure`` always carries ``outcome`` ("read_failure" or
    "parse_failure") plus a human-readable ``reason`` and a raw ``detail``
    string -- never just the bare outcome name, which is all a
    ``logger.warning()`` call alone would surface to the caller (ACD-2100b-1
    AC-2, ACD-2100b-2 AC-4: the verdict, not stderr, is what the workflow can
    report from).

    The read failure is split into ``FileNotFoundError`` and
    ``PermissionError`` (both `OSError` subclasses) specifically so "no file
    at this location" and "permission refused to open it" -- two different
    remedies -- produce two different ``reason`` values rather than
    collapsing into a single "read_failure" with no other distinguishing
    field (ACD-2100b-1 AC-2). This is external I/O (a file read and a JSON
    parse), so every failure path here is a named exception type logged at
    WARNING, never a bare or silently swallowed except (repository
    error-handling policy).
    """
    try:
        raw_text = registry_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        logger.warning("Could not read agent registry at %s: %s", registry_path, exc)
        return None, {
            "outcome": "read_failure",
            "reason": "No file exists at the resolved registry location.",
            "detail": str(exc),
        }
    except PermissionError as exc:
        logger.warning("Could not read agent registry at %s: %s", registry_path, exc)
        return None, {
            "outcome": "read_failure",
            "reason": (
                "The process was denied permission to read the resolved "
                "registry location."
            ),
            "detail": str(exc),
        }
    except OSError as exc:
        logger.warning("Could not read agent registry at %s: %s", registry_path, exc)
        return None, {
            "outcome": "read_failure",
            "reason": "The registry could not be read.",
            "detail": str(exc),
        }
    try:
        return json.loads(raw_text), None
    except json.JSONDecodeError as exc:
        logger.warning(
            "Agent registry at %s did not parse as JSON: %s", registry_path, exc
        )
        return None, {
            "outcome": "parse_failure",
            "reason": (
                f"JSON interpretation failed at line {exc.lineno}, column "
                f"{exc.colno} (character offset {exc.pos})."
            ),
            "position": exc.pos,
            "line": exc.lineno,
            "column": exc.colno,
            "detail": str(exc),
        }


def _resolve_agent_outcome(registry_json: object, agent_id: str) -> tuple[str, dict[str, object]]:
    """Resolve ``agent_id``'s entry in the registry's ``agents`` collection
    into one of three distinct, representable outcomes -- never collapsing
    any of them into another (mirrors templates/workflows-js/
    plan-feature.js's retired ``_resolveWorkspaceSetupAgentEntryState()``,
    minus its now-local "permitted"/"granted" case, which this function's
    caller derives directly from the same lookup):

      - "granted"              entry present, permits_shell is True.
      - "permission_denied"    entry present, permits_shell is not True
                                (missing field or explicit False).
      - "agent_not_found"      ``agents`` is a real list, but no entry in it
                                has this id -- "not listed", never a
                                permission verdict about a nonexistent entry.
      - "no_entries_collection" ``registry_json["agents"]`` is not a list at
                                all (missing key, wrong type) -- a distinct
                                fact from "agent_not_found", never folded
                                into it (ACD-2100b-3-i).

    Returns ``(outcome, extra)`` where ``extra`` is a dict of additional
    verdict fields the caller merges in. It is only ever populated for
    "no_entries_collection", where it names the malformed value's type
    (``agents_type``) and, when the value itself is a JSON scalar, the value
    itself (``agents_value``) -- so a report can say what was actually found
    in the agent-entries collection's place instead of discarding it once
    ``isinstance(agents, list)`` is known False (ACD-2100b-3-i AC-1). Every
    other outcome returns an empty ``extra`` dict.

    Pure function: no I/O, no external calls -- exceptions are never caught
    here (repository error-handling policy Rule 4).
    """
    agents = registry_json.get("agents") if isinstance(registry_json, dict) else None
    if not isinstance(agents, list):
        extra: dict[str, object] = {"agents_type": type(agents).__name__}
        if agents is None or isinstance(agents, (bool, int, float, str)):
            extra["agents_value"] = agents
        return "no_entries_collection", extra
    match = next(
        (entry for entry in agents if isinstance(entry, dict) and entry.get("id") == agent_id),
        None,
    )
    if match is None:
        return "agent_not_found", {}
    return ("granted" if match.get("permits_shell") is True else "permission_denied"), {}


def build_verdict(repo_root: Path | None, agent_id: str) -> dict:
    """Build the pre-flight's verdict object for ``agent_id``.

    A pure function of ``repo_root`` and the registry's on-disk contents at
    the moment it is called -- it makes no agent dispatch and no network
    call, and nothing in it branches on whether any dispatch transport is
    available, so the verdict is identical whichever is true
    (it_requirements: "skip the check when dispatch is unavailable ... is
    explicitly forbidden").
    """
    if repo_root is None:
        return {
            "permits": False,
            "outcome": "read_failure",
            "agent_id": agent_id,
            "reason": "No repository could be resolved from the current directory.",
        }

    registry_path = repo_root / REGISTRY_RELATIVE_PATH
    registry_json, load_failure = _load_registry(registry_path)
    if load_failure is not None:
        verdict: dict[str, object] = {
            "permits": False,
            "agent_id": agent_id,
            "location": str(registry_path),
        }
        verdict.update(load_failure)
        return verdict

    outcome, agent_extra = _resolve_agent_outcome(registry_json, agent_id)
    verdict = {
        "permits": outcome == "granted",
        "outcome": outcome,
        "agent_id": agent_id,
        "location": str(registry_path),
    }
    verdict.update(agent_extra)
    return verdict


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. No ``--registry-path`` override is offered:
    the registry location is always resolved repository-anchored (see
    resolve_repo_root()) so this pre-flight can never fork from
    ACD-2100a-1 / ACD-2100a-3's shared resolution semantics.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Emit the workspace-setup permission verdict for --agent-id, "
            "read locally from the repository-anchored agent registry."
        )
    )
    parser.add_argument(
        "--agent-id",
        default=DEFAULT_AGENT_ID,
        help=(
            "Agent id to look up in config/agent_registry.json's `agents` "
            f"collection (default: {DEFAULT_AGENT_ID!r})."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse args, resolve the verdict, print it as JSON.

    Always returns 0 -- see the module ARCHITECTURE note. A non-zero exit
    is reserved for argparse itself rejecting malformed CLI arguments.
    """
    parsed_args = _build_arg_parser().parse_args(argv)
    repo_root = resolve_repo_root(Path.cwd())
    verdict = build_verdict(repo_root, parsed_args.agent_id)
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-09-07 14:00 [python-coder]: Created this pre-flight script. Moves the
#   plan-feature workflow's workspace-setup permission check out of
#   templates/workflows-js/plan-feature.js (whose E2 engine sandbox has no
#   filesystem primitive, ADR-030) and into a real script the plan-feature
#   skill runs directly, so the registry read no longer requires an agent
#   dispatch round-trip. (#EPIC-StartingNewWorkTheProperWayAlways/12)
# - 2026-09-08 [python-coder]: Closed four information-loss gaps between what
#   _load_registry()/_resolve_agent_outcome() observe at the point of failure
#   and what the returned verdict actually carries (previously the detail was
#   passed to logger.warning() and discarded): (1) ACD-2100b-1 AC-2 -- an
#   absent registry and a permission-refused registry now carry different
#   `reason` text instead of colliding on outcome="read_failure" alone;
#   (2) ACD-2100b-2 AC-4 -- a parse_failure verdict now carries the
#   json.JSONDecodeError's own position/line/column; (3) ACD-2100b-3-i AC-1 --
#   a no_entries_collection verdict now names the malformed value's type
#   (agents_type) and, when scalar, the value itself (agents_value). Also
#   updated templates/workflows-js/plan-feature.js's outcomeMessages so the
#   read_failure report renders the verdict's location/reason (previously a
#   single static string, byte-identical for both Given conditions) and so
#   the permission_denied report names the `permits_shell` field literally
#   (ACD-2100b-3 AC-4; confirmed against the real, deployed
#   config/agent_registry.json before naming it). All four production
#   changes are additive fields alongside the existing six-value `outcome`
#   enum -- no outcome value was renamed or collapsed.
