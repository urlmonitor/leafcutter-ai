"""
MODULE: scripts/commit_guardian/_reachability_inventory.py
GOAL: Single shared seam for the whole runtime-reachability guard family
    (BO-2900): reading/classifying recorded exemptions (BO-2900d-1), reading
    what a command surface actually registers (BO-2900b-1), and collecting
    what automation actually invokes (BO-2900b-1 forwards, BO-2900c backwards,
    BO-2900b-3 hardens the collector itself).
BUSINESS CONTEXT: Every direction of this guard family is only as good as
    three primitives, and each must be defined exactly once or two directions
    can silently disagree about the same fact:
      - "is this exempt?" -- BO-2900d-1 requires code/capabilities with no
        runtime way in of their own to pass only on a recorded, reasoned
        exemption, never by naming convention; BO-2900d-2 requires every
        exemption in force to be listed with its reason on every guard run.
      - "what does this surface register?" -- BO-2900b-1 requires the answer
        to come from the BUILT command surface (its own argparse parser),
        never a source-text scan, so conditional/table-driven registration is
        read correctly in both directions a naive scan gets wrong.
      - "what does this automation actually invoke?" -- BO-2900b-1 (forwards)
        and BO-2900c (backwards) both need "an automation script really runs
        the surface with this capability" to mean the same thing, or a
        registered-but-uncalled false negative in one direction becomes an
        uncalled-but-registered false alarm in the other. BO-2900b-3 owns
        hardening this same function against JS command construction, decoy
        text (comments/messages/variable names) and the rename-invariance
        property -- see that AC; this module defines the ONE function it
        extends, never a second collector.
ARCHITECTURE: Six public symbols, no other module may re-implement any of them
    (:class:`Invocation` and :func:`collected_invocations` are implemented in
    the sibling module _reachability_invocation_collector.py and re-exported
    here verbatim -- a file-size split, not a second collector; see that
    module's own docstring):
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
        Invocation
            NamedTuple(script: str, line: int, surface: str, capability: str)
            -- one real, executed invocation of a capability against a
            surface, per the config_schema_fragment both BO-2900b-1 and
            BO-2900b-3 declare for it.
        registered_capabilities(parser) -> set[str]
            Reads argparse's own ``_SubParsersAction.choices`` off an already
            BUILT ``argparse.ArgumentParser`` -- never source text. A
            capability registered inside a branch that is false at build time
            is invisible; one registered through a loop over a table is still
            found, because both are resolved by actually building the parser,
            not by scanning for ``add_parser(`` calls.
        collected_invocations(script_paths) -> list[Invocation]
            AST-based (never substring/regex-over-raw-text) scan of Python
            automation scripts for real ``subprocess.run``/``call``/
            ``check_call``/``check_output``/``Popen`` calls whose argv names a
            surface script, taking the very next positional token as the
            capability. ROLLOUT NOTE (BO-2900b-1): only ``.py`` automation
            scripts are recognised; a ``.js``/``.yaml``/other script
            contributes no invocations here (not an error -- see
            debugging/test_judge/callers.py's own documented limit, "one hop,
            Python direct calls only; JS/YAML/CI invocations need their own
            handling"). This repository's real automation
            (templates/workflows-js/fast-lane-ship.js) is JavaScript;
            BO-2900b-3 is the follow-on AC that extends THIS function (not a
            second collector) to recognise its template-literal command
            strings, resist comment/message/variable-name decoys, and satisfy
            the rename-invariance property. Until BO-2900b-3 lands,
            check_reachability.py's own caller-side default (see that
            module's docstring) treats "no automation scripts were supplied"
            as "nothing to check yet", never as "nothing is called" -- so this
            gap does not, on its own, turn every real capability into a false
            refusal.

    All I/O (file reads) is wrapped per the Error Handling Policy (Rule 1);
    unreadable/unparseable individual files are logged and skipped rather
    than aborting the whole scan, since one bad automation script must not
    hide a genuine finding about every other one.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from _ac_store_locator import ensure_ac_store_on_syspath

ensure_ac_store_on_syspath()
from yaml_safe_loader import get_safe_yaml_loader

# BO-2900b-1/BO-2900b-3/BO-2900c seam: Invocation and collected_invocations()
# are implemented in the sibling module (file-size split, NOT a second
# collector -- see that module's docstring and this module's ARCHITECTURE
# note above) and re-exported here so ``from _reachability_inventory import
# collected_invocations`` (the seam's declared public import path in every
# consuming AC) keeps working unchanged.
from _reachability_invocation_collector import (  # noqa: F401 -- re-export
    Invocation,
    collected_invocations,
)

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
        raise ReachabilityRegistryError(  # noqa: TRY003
            f"cannot read reachability exemption registry {registry_path}: {exc}"
        ) from exc
    try:
        data = yaml.load(raw, Loader=get_safe_yaml_loader())
    except yaml.YAMLError as exc:
        raise ReachabilityRegistryError(  # noqa: TRY003
            f"cannot parse reachability exemption registry {registry_path}: {exc}"
        ) from exc
    if data is None:
        return []
    if not isinstance(data, dict):
        raise ReachabilityRegistryError(  # noqa: TRY003
            f"reachability exemption registry {registry_path} must be a YAML "
            f"mapping with a top-level 'exemptions' list"
        )
    entries = data.get("exemptions", [])
    if not isinstance(entries, list):
        raise ReachabilityRegistryError(  # noqa: TRY003
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


# ---------------------------------------------------------------------------
# BO-2900b-1 / BO-2900b-3 / BO-2900c: registered-capability and
# real-invocation inventory (see module docstring for the full contract).
# ---------------------------------------------------------------------------


def registered_capabilities(parser: argparse.ArgumentParser) -> set[str]:
    """Return the capability names a BUILT argparse parser actually registers.

    Reads ``argparse._SubParsersAction.choices`` directly off *parser* --
    argparse exposes no public API for this, and it is the only reading that
    cannot be fooled by source text: a capability registered inside a branch
    that is false when the parser is built is never added to ``choices`` in
    the first place, and one registered through a loop over a table is
    resolved identically to a literal ``add_parser(...)`` call, because both
    go through the same ``add_parser`` machinery at build time.

    Args:
        parser: An already-built ``argparse.ArgumentParser`` (the caller is
            responsible for calling the surface's own parser-builder function
            -- this function never imports or builds anything itself).

    Returns:
        The set of subcommand names registered on *parser*, across every
        ``add_subparsers()`` group it defines (ordinarily exactly one).
    """
    names: set[str] = set()
    for action in parser._actions:  # noqa: SLF001 -- no public API; see docstring.
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            names |= set(action.choices.keys())
    return names
