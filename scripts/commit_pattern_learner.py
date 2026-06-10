"""
commit_pattern_learner — AC BO-1100d / BO-1100e: Unfamiliar commit shapes are
analysed and learned over time with targeted history filtering.

MODULE: scripts/commit_pattern_learner.py
GOAL: Record staged-file "shapes" that hit the UNKNOWN fallback (no pattern
      matched), accumulate observations in a persistent JSONL store, and
      propose a new routing rule for config/commit_message_patterns.json after
      the same shape recurs 10 or more times.

BUSINESS CONTEXT:
    AC BO-1100d — when staged files do not match any known routing pattern,
    the system records the unmatched shape (the set of file extensions and
    path-prefix patterns seen in the staged set). After 10 occurrences of the
    same shape, a new routing rule is proposed for addition to the
    configuration. The system gets smarter with use without requiring manual
    rule authoring.

    AC BO-1100e — when analysing whether a shape recurs, the system uses a
    targeted history filter (``filter_history_by_shape``) rather than reading
    the full git log. The filter narrows git log output to commits that touched
    structurally similar paths (same directory prefixes and file extensions),
    and caps the result at MAX_HISTORY_COMMITS (100) entries. This keeps
    analysis latency and token cost bounded even in repositories with thousands
    of commits.

ARCHITECTURE:
    * A "shape" is a frozenset of normalised tokens extracted from the staged
      file paths (file extensions and top-level directory names). Shapes are
      serialised to a canonical sorted tuple so they can be used as JSON keys.
    * Observations are appended to a JSONL file:
          config/unknown_shape_observations.jsonl
      One record per observation, with ISO-8601 timestamp and shape tokens.
    * After every write, the module counts how many times the same shape has
      appeared. When the count reaches PROPOSAL_THRESHOLD (10) a proposal dict
      is returned to the caller. The caller decides whether to write the
      proposal to config/commit_message_patterns.json — this module never
      auto-writes config.
    * The classification logic from commit_classifier.py is NOT re-used for
      the shape extraction to avoid a circular dependency; shapes are derived
      directly from file paths.
    * ``filter_history_by_shape`` uses ``git log --format=%H%n%s --
      <pathspecs>`` to retrieve only commits touching matching paths. It
      never reads the full history; the ``--max-count`` flag enforces the
      upper bound.

Used by:
  - templates/agents/commit.md (Step 2: after UNKNOWN fallback fires)
  - unit_tests/test_commit_pattern_learner.py
  - unit_tests/test_history_filter.py
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

#: Number of times a shape must recur before a proposal is generated.
PROPOSAL_THRESHOLD: int = 10

#: Maximum number of commits examined when filtering git history by shape.
#: Keeps analysis latency and token cost bounded even in large repositories.
MAX_HISTORY_COMMITS: int = 100

#: Default path to the observation log (JSONL).
#: Resolved relative to this module so the code works from any CWD.
_DEFAULT_OBS_PATH: Path = (
    Path(__file__).resolve().parent.parent / "config" / "unknown_shape_observations.jsonl"
)

#: Default path to the patterns config (read-only here; callers write it).
_DEFAULT_PATTERNS_PATH: Path = (
    Path(__file__).resolve().parent.parent / "config" / "commit_message_patterns.json"
)


# ---------------------------------------------------------------------------
# Shape extraction
# ---------------------------------------------------------------------------


def _normalise_token(raw: str) -> str:
    """Return a normalised, lower-cased form of a token.

    Strips leading dots from extensions, lowercases, and collapses
    non-alphanumeric chars to underscores.
    """
    raw = raw.lstrip(".")
    raw = raw.lower()
    return re.sub(r"[^a-z0-9_]", "_", raw)


def extract_shape(staged_paths: Sequence[str]) -> tuple[str, ...]:
    """Derive a canonical shape tuple from a set of staged file paths.

    A shape is the **sorted, deduplicated** set of normalised tokens extracted
    from the staged files.  Two kinds of tokens are collected:

    * **Top-level directory name** — the first component of the path, if the
      path contains at least one ``/``.  Example: ``scripts/build.py``
      contributes ``"scripts"``.
    * **File extension** — the suffix of the filename (including the leading
      dot).  Example: ``scripts/build.py`` contributes ``"py"``.

    Tokens are normalised with ``_normalise_token``.  The result is sorted
    alphabetically so the same logical shape always maps to the same tuple
    regardless of the order in which paths are provided.

    Parameters
    ----------
    staged_paths:
        Iterable of file paths as returned by ``git diff --cached --name-only``.

    Returns
    -------
    A sorted tuple of normalised token strings.  An empty tuple is returned
    when ``staged_paths`` is empty or all paths produce no tokens.
    """
    tokens: set[str] = set()
    for path in staged_paths:
        parts = path.replace("\\", "/").split("/")

        # Top-level directory token (only when path has a directory component).
        if len(parts) > 1:
            top_dir = _normalise_token(parts[0])
            if top_dir:
                tokens.add(f"dir:{top_dir}")

        # Extension token.
        filename = parts[-1]
        dot_idx = filename.rfind(".")
        if dot_idx > 0:
            ext = _normalise_token(filename[dot_idx:])
            if ext:
                tokens.add(f"ext:{ext}")

    return tuple(sorted(tokens))


# ---------------------------------------------------------------------------
# History filter (AC BO-1100e)
# ---------------------------------------------------------------------------


def _build_git_pathspecs(shape: tuple[str, ...]) -> list[str]:
    """Derive git log pathspec arguments from a shape tuple.

    Each token in ``shape`` contributes one or two pathspec arguments:

    * ``dir:<name>`` tokens become ``<name>/`` (a directory prefix glob).
    * ``ext:<suffix>`` tokens become ``*.<suffix>`` (a file extension glob).

    These arguments are used with ``git log -- <pathspecs>`` so that git
    filters its commit walk to only commits that touched matching paths.

    Parameters
    ----------
    shape:
        Shape tuple as returned by ``extract_shape``.

    Returns
    -------
    List of pathspec strings suitable for passing after ``--`` in a git
    command.  Returns an empty list when the shape is empty (caller falls
    back to unfiltered history or skips the git call).
    """
    pathspecs: list[str] = []
    for token in shape:
        if token.startswith("dir:"):
            dir_name = token[len("dir:"):]
            if dir_name:
                pathspecs.append(f"{dir_name}/")
        elif token.startswith("ext:"):
            ext_name = token[len("ext:"):]
            if ext_name:
                pathspecs.append(f"*.{ext_name}")
    return pathspecs


def filter_history_by_shape(
    shape: tuple[str, ...],
    repo_root: Path | None = None,
    max_commits: int = MAX_HISTORY_COMMITS,
) -> list[dict[str, str]]:
    """Return git commits whose file changes are structurally similar to ``shape``.

    AC BO-1100e — the specialist only reads relevant history, not thousands
    of commits.  This function narrows ``git log`` output to commits that
    touched paths matching the shape's directory and extension tokens,
    then caps the result at ``max_commits`` entries so token cost stays
    bounded regardless of repository history depth.

    Algorithm
    ---------
    1. Derive pathspec arguments from the shape tokens via
       ``_build_git_pathspecs``.
    2. Run ``git log --max-count=<max_commits> --format=%H%n%s --
       <pathspecs>`` in the repository root (resolved from this module's
       location when ``repo_root`` is not provided).
    3. Parse the output into a list of ``{"hash": ..., "subject": ...}``
       dicts and return it.

    If the shape is empty (no tokens), or if git is unavailable, or if
    the command returns a non-zero exit code, an empty list is returned and
    the error is logged at WARNING level.  Callers must handle the empty-list
    case gracefully.

    Parameters
    ----------
    shape:
        Shape tuple as returned by ``extract_shape``.  An empty tuple
        causes an immediate return of ``[]`` (no pathspecs to filter by).
    repo_root:
        Explicit path to the repository root.  Defaults to the parent of
        the ``scripts/`` directory (i.e. the repo root when this module
        lives at ``scripts/commit_pattern_learner.py``).
    max_commits:
        Maximum number of matching commits to return.  Defaults to
        ``MAX_HISTORY_COMMITS`` (100).  Lower values reduce latency and
        token cost; higher values improve pattern accuracy for low-frequency
        shapes.

    Returns
    -------
    List of dicts, each with keys ``"hash"`` (full SHA-1) and
    ``"subject"`` (first commit-message line).  Empty list on error or
    when no commits match.
    """
    if max_commits < 1:
        msg = f"max_commits must be a positive integer, got {max_commits}"
        raise ValueError(msg)

    if not shape:
        return []

    pathspecs = _build_git_pathspecs(shape)
    if not pathspecs:
        return []

    root = repo_root if repo_root is not None else Path(__file__).resolve().parent.parent

    cmd = [
        "git",
        "-C",
        str(root),
        "log",
        f"--max-count={max_commits}",
        "--format=%H%n%s",
        "--",
        *pathspecs,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        logger.warning("git executable not found — history filter unavailable: %s", exc)
        return []
    except subprocess.TimeoutExpired as exc:
        logger.warning("git log timed out after 30 s — returning empty history: %s", exc)
        return []
    except OSError as exc:
        logger.warning("git log subprocess failed: %s", exc)
        return []

    if result.returncode != 0:
        logger.warning(
            "git log exited %d for shape %s: %s",
            result.returncode,
            shape,
            result.stderr.strip(),
        )
        return []

    commits: list[dict[str, str]] = []
    lines = result.stdout.splitlines()
    # git log --format=%H%n%s outputs two lines per commit: hash then subject.
    it = iter(lines)
    for commit_hash in it:
        commit_hash = commit_hash.strip()
        if not commit_hash:
            continue
        try:
            subject = next(it).strip()
        except StopIteration:
            subject = ""
        if commit_hash:
            commits.append({"hash": commit_hash, "subject": subject})

    return commits


# ---------------------------------------------------------------------------
# Observation store
# ---------------------------------------------------------------------------


def record_unknown_shape(
    staged_paths: Sequence[str],
    obs_path: Path | None = None,
) -> tuple[str, ...]:
    """Append an observation for an UNKNOWN-class staged-file set.

    Extracts the shape from ``staged_paths`` and appends a JSON record to
    the JSONL observation store.  The record format is::

        {"timestamp": "<ISO8601>", "shape": ["token1", "token2", ...]}

    Parameters
    ----------
    staged_paths:
        Iterable of file paths that hit the UNKNOWN fallback.
    obs_path:
        Optional explicit path to the JSONL observation store.
        Defaults to ``config/unknown_shape_observations.jsonl``.

    Returns
    -------
    The shape tuple that was recorded, so callers can pass it directly to
    ``count_shape_occurrences`` or ``maybe_propose_rule``.
    """
    path = obs_path if obs_path is not None else _DEFAULT_OBS_PATH
    shape = extract_shape(staged_paths)

    record = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "shape": list(shape),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        # Log the failure but do NOT re-raise — observation store write
        # failures must not crash the commit workflow (AC BO-1100d-5).
        logger.warning("Failed to write to observation store %s: %s", path, exc)

    return shape


def count_shape_occurrences(
    shape: tuple[str, ...],
    obs_path: Path | None = None,
) -> int:
    """Count how many times ``shape`` has been recorded in the observation store.

    Reads the JSONL store and counts records whose ``shape`` list matches
    the provided tuple (order-insensitive: both are sorted before comparison).

    Parameters
    ----------
    shape:
        Shape tuple as returned by ``extract_shape`` or ``record_unknown_shape``.
    obs_path:
        Optional explicit path to the JSONL store.

    Returns
    -------
    Number of matching records, or 0 if the store does not exist.
    """
    path = obs_path if obs_path is not None else _DEFAULT_OBS_PATH

    if not path.exists():
        return 0

    target = sorted(shape)
    count = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed line in observation store %s: %s", path, exc
                    )
                    continue
                if sorted(record.get("shape", [])) == target:
                    count += 1
    except OSError as exc:
        # Log the failure but return 0 — a read failure is treated as zero
        # observations so the caller can continue safely (AC BO-1100d-5).
        logger.warning("Failed to read observation store %s: %s", path, exc)
        return 0

    return count


# ---------------------------------------------------------------------------
# Rule proposal
# ---------------------------------------------------------------------------


def propose_rule(
    shape: tuple[str, ...],
    history: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """Generate a proposed routing-rule dict for an unrecognised shape.

    The proposal is a dict ready to be written as a new entry in
    ``config/commit_message_patterns.json``.  The suggested key is a
    human-readable slug derived from the most prominent tokens in the shape;
    the suggested template follows the project's ``{detail}`` convention.

    This function NEVER writes to any file.  The caller is responsible for
    deciding whether to apply the proposal.

    Parameters
    ----------
    shape:
        Shape tuple as returned by ``extract_shape``.
    history:
        Optional list of relevant git commits (dicts with ``"hash"`` and
        ``"subject"`` keys) as returned by ``filter_history_by_shape()``.
        Passed through for callers that want to inspect the history alongside
        the proposal; not used for key generation in the current implementation.

    Returns
    -------
    A dict with two keys:

    ``"group_key"``
        A snake_case string suitable for use as a new ``FileGroup`` key and
        as a key in ``commit_message_patterns.json``.

    ``"template"``
        The suggested commit-message template string (uses ``{detail}``).
    """
    # Build a group key from the most prominent tokens.
    ext_tokens = [t.removeprefix("ext:") for t in shape if t.startswith("ext:")]
    dir_tokens = [t.removeprefix("dir:") for t in shape if t.startswith("dir:")]

    # Prefer directory tokens for naming, fall back to extensions.
    key_parts = dir_tokens[:2] if dir_tokens else ext_tokens[:2]
    if not key_parts:
        group_key = "unknown_shape"
    else:
        group_key = "_".join(key_parts)

    # Ensure the key is a valid Python identifier / JSON key.
    group_key = re.sub(r"[^a-z0-9_]", "_", group_key).strip("_")
    if not group_key:
        group_key = "unknown_shape"

    template = f"chore({group_key}): {{detail}}"

    return {
        "group_key": group_key,
        "template": template,
    }


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def maybe_propose_rule(
    staged_paths: Sequence[str],
    obs_path: Path | None = None,
    threshold: int = PROPOSAL_THRESHOLD,
    classification_was_unknown: bool = True,
) -> dict[str, str] | None:
    """Record an UNKNOWN observation and return a rule proposal when threshold is met.

    This is the **primary entry point** for the commit agent.  Call it whenever
    ``classify_staged_files()`` returns ``specific_pattern_matched=False`` (i.e.
    the UNKNOWN fallback fired).

    Steps:
    1. Guard — when ``classification_was_unknown=False`` the shape was already
       handled by a known rule; skip recording entirely and return ``None``.
    2. Record the observation in the JSONL store.  OSError is caught, logged,
       and swallowed so a write failure never crashes the commit workflow
       (AC BO-1100d-5).
    3. Count total occurrences of the shape.
    4. If ``count >= threshold``, call ``filter_history_by_shape(shape)`` to
       retrieve relevant git history (AC BO-1100e-4), then return
       ``propose_rule(shape, history=...)``.
    5. Otherwise return ``None``.

    Parameters
    ----------
    staged_paths:
        Iterable of file paths that hit the UNKNOWN fallback.
    obs_path:
        Optional explicit path to the JSONL observation store.
    threshold:
        Number of occurrences required before a proposal is generated.
        Defaults to ``PROPOSAL_THRESHOLD`` (10).
    classification_was_unknown:
        When ``False``, the staged files were already matched by a known
        routing rule; the function returns ``None`` immediately without
        writing to the observation store (AC BO-1100d-6).  Defaults to
        ``True`` for backward compatibility.

    Returns
    -------
    A proposal dict (see ``propose_rule``) when the threshold is reached,
    or ``None`` when the shape has not yet accumulated enough observations,
    or ``None`` when ``classification_was_unknown=False``.
    """
    # AC BO-1100d-6 — known shapes must not pollute the observation store.
    if not classification_was_unknown:
        return None

    # AC BO-1100d-5 — write failure must not propagate to caller.
    try:
        shape = record_unknown_shape(staged_paths, obs_path=obs_path)
    except OSError as exc:
        logger.warning(
            "Observation store write failed; skipping learning pipeline: %s", exc
        )
        return None

    count = count_shape_occurrences(shape, obs_path=obs_path)
    if count >= threshold:
        # AC BO-1100e-4 — filter relevant history before generating the proposal.
        history = filter_history_by_shape(shape)
        return propose_rule(shape, history=history)
    return None
