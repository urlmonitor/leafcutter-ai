"""
commit_pattern_learner — AC BO-1100d: Unfamiliar commit shapes are analysed
and learned over time.

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

Used by:
  - templates/agents/commit.md (Step 2: after UNKNOWN fallback fires)
  - unit_tests/test_commit_pattern_learner.py
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

#: Number of times a shape must recur before a proposal is generated.
PROPOSAL_THRESHOLD: int = 10

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
        logger.warning("Failed to write to observation store %s: %s", path, exc)
        raise

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
        logger.warning("Failed to read observation store %s: %s", path, exc)
        raise

    return count


# ---------------------------------------------------------------------------
# Rule proposal
# ---------------------------------------------------------------------------


def propose_rule(shape: tuple[str, ...]) -> dict[str, str]:
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
) -> dict[str, str] | None:
    """Record an UNKNOWN observation and return a rule proposal when threshold is met.

    This is the **primary entry point** for the commit agent.  Call it whenever
    ``classify_staged_files()`` returns ``specific_pattern_matched=False`` (i.e.
    the UNKNOWN fallback fired).

    Steps:
    1. Record the observation.
    2. Count total occurrences of the shape.
    3. If ``count >= threshold``, return ``propose_rule(shape)``; else return ``None``.

    Parameters
    ----------
    staged_paths:
        Iterable of file paths that hit the UNKNOWN fallback.
    obs_path:
        Optional explicit path to the JSONL observation store.
    threshold:
        Number of occurrences required before a proposal is generated.
        Defaults to ``PROPOSAL_THRESHOLD`` (10).

    Returns
    -------
    A proposal dict (see ``propose_rule``) when the threshold is reached,
    or ``None`` when the shape has not yet accumulated enough observations.
    """
    shape = record_unknown_shape(staged_paths, obs_path=obs_path)
    count = count_shape_occurrences(shape, obs_path=obs_path)
    if count >= threshold:
        return propose_rule(shape)
    return None
