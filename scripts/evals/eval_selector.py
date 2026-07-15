"""
MODULE: eval_selector.py
GOAL: Decide WHICH agent evals a change affects, and enforce that every affected
    agent has a FRESH eval result. Implements the trigger-selector of TQ-200b-3
    and the missing/stale-is-a-hard-failure gate of TQ-200b-4.

BUSINESS CONTEXT: Each agent in scripts/evals/agent_eval_config.json declares a
    `triggers` list of repo-relative globs covering its dependency closure (its
    prompt template, the shared instructions/schemas it loads, its eval set, and
    the shared harness + config). A change is AFFECTS an agent when at least one
    changed file matches one of that agent's trigger globs. Only affected evals
    need to re-run (cost), but EVERY affected eval must be proven fresh
    (completeness) — a missing or stale result is a HARD FAILURE, never a silent
    pass (mirrors TQ-200a-1's coverage-gap rule).

ARCHITECTURE: Single importable module + CLI.
    - Default action: print the affected/unaffected split as JSON, exit 0.
    - `--check`: for every affected agent require a FRESH result at
      scripts/evals/results/<agent>.json. FRESH = the result's recorded
      `trigger_shas` map (repo-relative path -> sha256 of the file's bytes)
      EXACTLY equals the current resolved trigger files + hashes. A trigger file
      added, removed, or changed since the result was written makes it STALE; an
      absent result is MISSING. Exit 0 iff every affected agent is fresh, else
      exit 3, reporting every offender (deterministic, sorted).
    - Freshness input SHAs are stamped into each result by run_agent_eval.py via
      resolve_trigger_shas() (this module is the single source of truth for how
      trigger globs resolve to files + hashes, so runner and gate always agree).

Exit Codes:
    0 - Success. Default action always exits 0; --check exits 0 when every
        affected agent is fresh (or nothing is affected).
    2 - Usage / config / git error (bad config, unresolvable diff-base ref).
    3 - GATE FAILURE: an affected agent has a missing or stale result.

Usage:
    python scripts/evals/eval_selector.py --changed-files a/b.py c/d.md
    python scripts/evals/eval_selector.py --diff-base origin/main
    python scripts/evals/eval_selector.py --check --diff-base origin/main
"""

from __future__ import annotations

import argparse
import fnmatch
import glob as globmod
import hashlib
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("eval_selector")


# ---------------------------------------------------------------------------
# Typed exceptions (Error Handling Policy: wrap external I/O, log + raise typed)
# ---------------------------------------------------------------------------
class EvalSelectorError(Exception):
    """Base class for all selector errors."""


class SelectorConfigError(EvalSelectorError):
    """Raised when the eval config is missing or malformed."""


class GitDiffError(EvalSelectorError):
    """Raised when the git diff for --diff-base cannot be computed."""


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
def find_repo_root() -> Path:
    """Return the repo root (this file lives at <root>/scripts/evals/)."""
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Config loading (external I/O — wrapped per policy)
# ---------------------------------------------------------------------------
def load_config(config_path: Path) -> dict[str, Any]:
    """Load the eval config JSON. Raises SelectorConfigError on any I/O/parse error."""
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.exception("Cannot read eval config %s", config_path)
        msg = f"Cannot read eval config {config_path}"
        raise SelectorConfigError(msg) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.exception("Eval config %s is not valid JSON", config_path)
        msg = f"Eval config {config_path} is not valid JSON"
        raise SelectorConfigError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"Eval config {config_path} is not a JSON object"
        raise SelectorConfigError(msg)
    return parsed


def agent_triggers(config: dict[str, Any]) -> dict[str, list[str]]:
    """Map each configured agent to its list of trigger globs. Pure function.

    Raises SelectorConfigError when the 'agents' object or an agent's 'triggers'
    list is absent/malformed — a missing trigger manifest must fail loudly, never
    silently treat an agent as un-triggerable.
    """
    agents = config.get("agents")
    if not isinstance(agents, dict):
        msg = "Config has no 'agents' object"
        raise SelectorConfigError(msg)
    triggers: dict[str, list[str]] = {}
    for name, entry in agents.items():
        if not isinstance(entry, dict):
            msg = f"Agent '{name}' entry is not an object"
            raise SelectorConfigError(msg)
        globs = entry.get("triggers")
        if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
            msg = f"Agent '{name}' has no valid 'triggers' list"
            raise SelectorConfigError(msg)
        triggers[name] = list(globs)
    return triggers


# ---------------------------------------------------------------------------
# Glob matching (pure)
# ---------------------------------------------------------------------------
def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a repo-relative glob into an anchored regex. Pure function.

    Segment-aware semantics:
      - `**` matches any characters, INCLUDING path separators (recursive).
      - `*`  matches any characters EXCEPT a path separator (one segment).
      - `?`  matches a single non-separator character.
    All other characters are matched literally.
    """
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        char = pattern[i]
        if char == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def path_matches_glob(path: str, pattern: str) -> bool:
    """True when a repo-relative path matches a trigger glob. Pure function."""
    norm = path.replace("\\", "/").lstrip("./")
    if glob_to_regex(pattern).match(norm):
        return True
    # A directory-recursive pattern ('.../**') also matches the directory prefix
    # itself; fnmatch is a permissive fallback for exotic patterns.
    return fnmatch.fnmatch(norm, pattern)


def matched_globs(changed_files: list[str], globs: list[str]) -> list[str]:
    """Return the subset of `globs` that match at least one changed file. Pure.

    Order follows the declared trigger order; duplicates are removed.
    """
    hits: list[str] = []
    for pattern in globs:
        if pattern in hits:
            continue
        if any(path_matches_glob(f, pattern) for f in changed_files):
            hits.append(pattern)
    return hits


def compute_affected(
    changed_files: list[str], triggers: dict[str, list[str]]
) -> dict[str, Any]:
    """Compute the affected/unaffected split for a change. Pure function.

    Returns {"affected": [...sorted], "unaffected": [...sorted],
             "matched": {agent: [glob...]}} where an agent is AFFECTED when any
    changed file matches any of its trigger globs.
    """
    affected: list[str] = []
    unaffected: list[str] = []
    matched: dict[str, list[str]] = {}
    for agent in sorted(triggers):
        hits = matched_globs(changed_files, triggers[agent])
        if hits:
            affected.append(agent)
            matched[agent] = hits
        else:
            unaffected.append(agent)
    return {"affected": affected, "unaffected": unaffected, "matched": matched}


# ---------------------------------------------------------------------------
# Trigger resolution + hashing (external I/O — the SSOT the runner also uses)
# ---------------------------------------------------------------------------
def resolve_trigger_files(repo_root: Path, globs: list[str]) -> list[str]:
    """Resolve trigger globs to the sorted set of repo-relative file paths. I/O.

    A trailing '/**' (or any '**') resolves recursively to the files beneath it.
    Only regular files are returned (directories are dropped). Deterministic.
    """
    found: set[str] = set()
    for pattern in globs:
        abs_pattern = str(repo_root / pattern)
        for hit in globmod.glob(abs_pattern, recursive=True):
            hit_path = Path(hit)
            try:
                is_file = hit_path.is_file()
            except OSError as exc:
                logger.warning("Cannot stat %s: %s", hit_path, exc)
                continue
            if is_file:
                found.add(hit_path.relative_to(repo_root).as_posix())
    return sorted(found)


def _sha256_file(path: Path) -> str:
    """Return the sha256 hex of a file's bytes. I/O boundary (log + typed raise)."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        logger.exception("Cannot read trigger file %s", path)
        msg = f"Cannot read trigger file {path}"
        raise EvalSelectorError(msg) from exc
    return hashlib.sha256(data).hexdigest()


def resolve_trigger_shas(repo_root: Path, globs: list[str]) -> dict[str, str]:
    """Map each resolved trigger file (repo-relative posix path) to its sha256.

    Single source of truth for freshness: run_agent_eval.py stamps this into each
    result, and the --check gate re-derives it from the working tree to compare.
    """
    shas: dict[str, str] = {}
    for rel in resolve_trigger_files(repo_root, globs):
        shas[rel] = _sha256_file(repo_root / rel)
    return shas


# ---------------------------------------------------------------------------
# Freshness (pure) + result reading (I/O)
# ---------------------------------------------------------------------------
def freshness(current: dict[str, str], recorded: dict[str, str] | None) -> str:
    """Classify a result's freshness. Pure function.

    Returns 'missing' when there is no recorded result, 'fresh' when the recorded
    trigger_shas exactly equal the current resolved set + hashes, else 'stale'.
    An added, removed, or changed trigger file all yield 'stale'.
    """
    if recorded is None:
        return "missing"
    return "fresh" if recorded == current else "stale"


def read_recorded_shas(results_dir: Path, agent: str) -> dict[str, str] | None:
    """Return the trigger_shas recorded in results/<agent>.json, or None if the
    result file is absent. I/O boundary.

    A present-but-unreadable or SHA-less result is treated as no proof (None),
    so the gate reports it as MISSING rather than silently passing.
    """
    result_path = results_dir / f"{agent}.json"
    if not result_path.exists():
        return None
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Cannot read/parse result %s: %s", result_path, exc)
        return None
    shas = payload.get("trigger_shas") if isinstance(payload, dict) else None
    if not isinstance(shas, dict):
        logger.warning("Result %s has no trigger_shas map", result_path)
        return None
    return {str(k): str(v) for k, v in shas.items()}


def check_freshness(
    repo_root: Path,
    results_dir: Path,
    affected: list[str],
    triggers: dict[str, list[str]],
) -> tuple[int, dict[str, str]]:
    """Gate every affected agent's result. Returns (exit_code, {agent: status}).

    exit_code is 3 when ANY affected agent is missing or stale, else 0. Every
    affected agent is enumerated deterministically and all offenders reported.
    """
    status: dict[str, str] = {}
    ok = True
    for agent in sorted(affected):
        current = resolve_trigger_shas(repo_root, triggers[agent])
        recorded = read_recorded_shas(results_dir, agent)
        state = freshness(current, recorded)
        status[agent] = state
        if state != "fresh":
            ok = False
    return (0 if ok else 3), status


# ---------------------------------------------------------------------------
# Changed-file derivation from git (external I/O — wrapped per policy)
# ---------------------------------------------------------------------------
def _git_lines(repo_root: Path, args: list[str]) -> list[str]:
    """Run a git command and return its non-empty stdout lines. I/O boundary."""
    cmd = ["git", "-C", str(repo_root), *args]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as exc:
        logger.exception("git %s failed", " ".join(args))
        msg = f"git {' '.join(args)} failed: {(exc.stderr or '').strip()[:300]}"
        raise GitDiffError(msg) from exc
    except OSError as exc:
        logger.exception("git could not be launched")
        msg = "git could not be launched"
        raise GitDiffError(msg) from exc
    return [ln.strip() for ln in completed.stdout.splitlines() if ln.strip()]


def changed_files_from_git(repo_root: Path, diff_base: str) -> list[str]:
    """Repo-relative changed files vs `diff_base`: committed (base...HEAD) UNION
    staged+unstaged working-tree changes (diff vs HEAD). I/O boundary.
    """
    committed = _git_lines(repo_root, ["diff", "--name-only", f"{diff_base}...HEAD"])
    working = _git_lines(repo_root, ["diff", "--name-only", "HEAD"])
    return sorted(set(committed) | set(working))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select which agent evals a change affects, and gate their freshness."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--changed-files",
        nargs="+",
        metavar="PATH",
        help="Repo-relative changed file paths.",
    )
    source.add_argument(
        "--diff-base",
        metavar="GITREF",
        help="Compute changed files as `git diff base...HEAD` plus staged+unstaged.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Gate: require a FRESH result for every affected agent (exit 3 on missing/stale).",
    )
    parser.add_argument("--config", default=None, help="Path to agent_eval_config.json.")
    parser.add_argument("--repo-root", default=None, help="Repo root (default: inferred).")
    parser.add_argument("--results-dir", default=None, help="Directory of results/<agent>.json.")
    return parser


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Resolve repo_root, config_path, results_dir from args + defaults. Pure-ish."""
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root()
    config_path = (
        Path(args.config) if args.config else repo_root / "scripts/evals/agent_eval_config.json"
    )
    results_dir = (
        Path(args.results_dir) if args.results_dir else repo_root / "scripts/evals/results"
    )
    return repo_root, config_path, results_dir


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    repo_root, config_path, results_dir = _resolve_paths(args)

    try:
        config = load_config(config_path)
        triggers = agent_triggers(config)
    except SelectorConfigError:
        logger.exception("Config error")
        return 2

    if args.changed_files is not None:
        changed = sorted({f.replace("\\", "/").lstrip("./") for f in args.changed_files})
    else:
        try:
            changed = changed_files_from_git(repo_root, args.diff_base)
        except GitDiffError:
            logger.exception("Could not compute changed files from git")
            return 2

    split = compute_affected(changed, triggers)

    if not args.check:
        print(json.dumps(split, indent=2))
        return 0

    exit_code, status = check_freshness(repo_root, results_dir, split["affected"], triggers)
    for agent in split["unaffected"]:
        logger.info("SKIP %s: unaffected by this change", agent)
    output = {
        "affected": split["affected"],
        "unaffected": split["unaffected"],
        "matched": split["matched"],
        "status": status,
    }
    print(json.dumps(output, indent=2))
    if exit_code != 0:
        offenders = sorted(a for a, s in status.items() if s != "fresh")
        logger.error("Eval freshness gate FAILED for: %s", offenders)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
