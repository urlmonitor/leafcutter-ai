"""
MODULE: scripts/commit_guardian/_reachability_inventory.py
GOAL: Single shared seam for reading and classifying recorded reachability
    exemptions from config/reachability_exemptions.yaml.
BUSINESS CONTEXT: BO-2900d-1 requires that code with no runtime way in of its
    own can only pass the reachability guard on a recorded, reasoned
    exemption -- never by naming convention. BO-2900d-2 requires every
    exemption currently in force to be listed with its reason (and a stated
    total) on every guard run. Both features must read the SAME registry the
    SAME way, or the guard's refusal and its own reviewable inventory could
    silently disagree about what "exempt" means (BO-2900d-1's own
    constraint: "the registry loader lives in the shared seam ... so there
    is exactly one reader; a second parser will drift").
ARCHITECTURE: Three public functions, no other module may re-parse the
    registry file:
        load_exemptions(registry_path) -> list[dict]
            Reads config/reachability_exemptions.yaml. A missing file is
            zero exemptions (fail-open: absence is the ordinary "nothing
            recorded yet" state, not an error). A present-but-unparseable
            file, or an `exemptions` key that is not a list, raises
            ReachabilityRegistryError (fail-closed, names the file) so a
            corrupt registry is never silently read as "no exemptions" or
            "everything is exempt".
        exemptions_in_force(exemptions) -> list[dict]
            Filters to entries whose `reason` is a non-empty, non-whitespace
            string. An entry recorded with a blank reason is present in the
            registry but grants nothing (BO-2900d-1-i's "reasonless" state)
            and is excluded here so BO-2900d-2's "in force" total never
            counts it.
        is_exempt(item, exemptions) -> bool
            Exact string-equality match of `item` against an in-force
            exemption only -- no globs, prefixes, or convention-based
            matching (name, extension, and containing folder confer
            nothing; see BO-2900d-1's third Gherkin scenario).

    All I/O (the registry file read) is wrapped per the Error Handling
    Policy (Rule 1); the classification helpers below it are pure and carry
    no try/except (Rule 4).
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Registry file path, relative to the project root, per BO-2900d-1's
# it_requirements config_schema_fragment.
REGISTRY_RELATIVE_PATH = Path("config") / "reachability_exemptions.yaml"


class ReachabilityRegistryError(Exception):
    """Raised when the exemption registry exists but cannot be trusted.

    Covers a file that is not valid YAML, or whose top-level shape is not a
    mapping with a list-valued ``exemptions`` key. Deliberately fail-closed
    (never silently treated as zero exemptions) so a corrupt registry cannot
    be mistaken for an empty, legitimate one.
    """


def load_exemptions(registry_path: Path) -> list[dict]:
    """Load recorded reachability exemptions from *registry_path*.

    Args:
        registry_path: Path to ``config/reachability_exemptions.yaml``.

    Returns:
        List of exemption dicts as recorded in the registry (each carrying,
        at minimum, ``item``, ``kind``, ``reason``, ``recorded``, and
        ``recorded_by`` per BO-2900d-1's schema). An absent registry file
        returns an empty list. Non-dict entries in the ``exemptions`` list
        are silently dropped (malformed individual entries, not a malformed
        file).

    Raises:
        ReachabilityRegistryError: the file exists but is not valid YAML, or
            its top-level shape is not a mapping, or its ``exemptions`` key
            is present but not a list.
    """
    if not registry_path.exists():
        return []
    try:
        raw = registry_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReachabilityRegistryError(
            f"cannot read reachability exemption registry {registry_path}: {exc}"
        ) from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ReachabilityRegistryError(
            f"cannot parse reachability exemption registry {registry_path}: {exc}"
        ) from exc
    if data is None:
        return []
    if not isinstance(data, dict):
        raise ReachabilityRegistryError(
            f"reachability exemption registry {registry_path} must be a YAML "
            f"mapping with a top-level 'exemptions' list"
        )
    entries = data.get("exemptions", [])
    if not isinstance(entries, list):
        raise ReachabilityRegistryError(
            f"reachability exemption registry {registry_path}: 'exemptions' "
            f"must be a list"
        )
    return [entry for entry in entries if isinstance(entry, dict)]


def _has_reason(entry: dict) -> bool:
    """True when *entry*'s ``reason`` field is a non-empty, non-whitespace string."""
    reason = entry.get("reason")
    return isinstance(reason, str) and reason.strip() != ""


def exemptions_in_force(exemptions: list[dict]) -> list[dict]:
    """Return the subset of *exemptions* that actually grant a pass.

    An entry recorded with an empty or whitespace-only ``reason`` is present
    in the registry but grants nothing (BO-2900d-1-i) and is excluded here so
    the "in force" count (BO-2900d-2) never includes it.

    Args:
        exemptions: Raw entries as returned by :func:`load_exemptions`.

    Returns:
        The subset of *exemptions* whose ``reason`` is non-empty.
    """
    return [entry for entry in exemptions if _has_reason(entry)]


def is_exempt(item: str, exemptions: list[dict]) -> bool:
    """True iff *item* exactly matches an in-force exemption's ``item`` field.

    Matching is exact string equality only -- no globs, prefixes, or
    convention-based matching. A unit sharing an exempted unit's name, file
    extension, or containing folder gains nothing from that resemblance;
    only an exact, recorded ``item`` string with a non-empty reason grants a
    pass (BO-2900d-1's third Gherkin scenario).

    Args:
        item: The exact repo-relative path (or ``surface:capability`` id)
            being checked.
        exemptions: Raw entries as returned by :func:`load_exemptions`.

    Returns:
        ``True`` iff an in-force entry's ``item`` equals *item* exactly.
    """
    return any(entry.get("item") == item for entry in exemptions_in_force(exemptions))
